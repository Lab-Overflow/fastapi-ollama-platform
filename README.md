# FastAPI + Ollama Platform

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688.svg)](https://fastapi.tiangolo.com/)
[![Production Ready](https://img.shields.io/badge/status-production--ready-success.svg)](#)

一个 **面向生产、可商用** 的本地大模型服务端。一套代码即覆盖企业里 80% 的 LLM 业务场景：
多轮流式对话、知识库 RAG 问答、结构化抽取 / 函数调用——全部运行在私有网络内，
不产生任何第三方 token 费用，也不让业务数据离开机房。

| 业务能力 | 路由 | 说明 |
| --- | --- | --- |
| 多轮对话 · 流式输出 | `POST /chat`, `POST /chat/stream` | SSE 流式 token、带 `session_id` 的会话记忆 |
| 知识库 RAG 问答 | `POST /rag/ingest`, `POST /rag/query` | 文本分块 → 向量 → 余弦召回 → 带引用生成 |
| 结构化抽取 · 函数调用 | `POST /extract` | 基于 JSON Schema 的强约束输出（简历 / 合同 / 工单） |
| 运维接口 | `GET /health`, `GET /models` | 健康检查 + 本地模型清单 |

所有请求走 **异步 + 并发信号量** 保护，默认为单卡 24 GB GPU 上运行 7B–8B 模型做过容量测算，
不会把推理后端打爆。

---

## 1. 架构总览

```
 ┌────────────────┐   HTTPS/SSE    ┌────────────────────────────┐
 │  Client / SDK  │ ─────────────▶ │       FastAPI Gateway      │
 └────────────────┘                │  (async · semaphore guard) │
                                   ├──────────┬─────────────────┤
                                   │ /chat    │  /rag           │
                                   │ /extract │  /health /models│
                                   └────┬─────┴───────┬─────────┘
                                        │             │
                                        ▼             ▼
                                 ┌────────────┐ ┌─────────────┐
                                 │  Ollama    │ │ Vector Store│
                                 │ (AsyncCli) │ │ (pluggable) │
                                 └────────────┘ └─────────────┘
```

所有上游 I/O 调用均为 `async`，配合 `asyncio.Semaphore` 对 GPU 做并发闸闸，保证
在固定硬件上延迟与吞吐都是可预测、可容量规划的。

## 2. 代码结构

```
FastAPI+Ollama/
├── app/
│   ├── main.py              # FastAPI 入口 · lifespan 绑定资源
│   ├── config.py            # pydantic-settings · .env 驱动
│   ├── schemas.py           # 请求 / 响应模型
│   ├── deps.py              # 依赖注入: Ollama / Session / RAG
│   ├── ollama_client.py     # AsyncClient 封装 · 信号量
│   ├── session.py           # 会话记忆 (接口化，可替换 Redis)
│   ├── rag/
│   │   ├── store.py         # 向量存储接口 (可替换 Qdrant / Milvus)
│   │   └── pipeline.py      # chunk → embed → retrieve → prompt
│   └── routers/
│       ├── chat.py · rag.py · extract.py · health.py
├── tests/test_smoke.py
├── scripts/quickstart.sh
├── Dockerfile · docker-compose.yml
├── requirements.txt · .env.example
└── LICENSE (Apache 2.0)
```

## 3. 快速启动

### 本机模式

```bash
# 1) 启动 Ollama 并拉模型
ollama serve &
ollama pull qwen3:8b
ollama pull nomic-embed-text

# 2) 启动服务
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 `http://localhost:8000/docs` 查看交互式 OpenAPI 文档。

### Docker Compose 一键部署

```bash
docker compose up -d
docker exec -it ollama ollama pull qwen3:8b
docker exec -it ollama ollama pull nomic-embed-text
```

## 4. 调用示例

### 流式对话 (SSE)

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "tenant-a:user-001",
    "messages": [{"role": "user", "content": "用三句话解释 RAG"}]
  }'
```

### 知识库 RAG

```bash
curl -X POST http://localhost:8000/rag/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "documents": [
      {"id": "policy-01", "text": "公司年假政策：入职满 1 年享 5 天..."}
    ]
  }'

curl -X POST http://localhost:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "入职一年有几天年假?", "top_k": 3}'
```

### 结构化抽取 (简历 / 合同 / 工单)

```bash
curl -X POST http://localhost:8000/extract \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "张三, 28 岁, 手机 13800000000, 北京市朝阳区, 应聘后端工程师",
    "schema": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "age":  {"type": "integer"},
        "phone":{"type": "string"},
        "city": {"type": "string"},
        "role": {"type": "string"}
      },
      "required": ["name", "phone"]
    }
  }'
```

## 5. 生产特性

| 特性 | 实现 |
| --- | --- |
| 异步 I/O | 全链路 `async`，基于 `ollama.AsyncClient`，不阻塞 worker |
| 并发控制 | `asyncio.Semaphore(MAX_CONCURRENCY)` 对 GPU 做闸门 |
| 流式响应 | `sse-starlette` 原生 SSE，可直接对接前端 / 移动端 |
| 会话一致性 | `SessionStore` 接口化，默认内存实现，可替换 Redis / Postgres |
| 向量检索 | `VectorStore` 接口化，默认 numpy 余弦；生产侧可替换 Qdrant / Milvus |
| 结构化输出 | 使用 Ollama `format=<JSON Schema>`，模型直接输出符合 schema 的 JSON |
| 引用可追溯 | `/rag/query` 返回 `citations`，前端可渲染引用气泡 |
| 容器化 | 多阶段 Dockerfile + Compose，可直接部署到 k8s |
| 配置外置 | `pydantic-settings` + `.env`，零代码切换模型 / 后端地址 |
| CORS | 内置中间件，默认放开，可按环境收紧 |

## 6. 可扩展性

架构核心是"三个可替换接口 + 一个 lifespan"——要把单机原型升级为多租户 SaaS，只需改 `lifespan` 的依赖装配：

| 组件 | 默认实现 | 生产可替换 |
| --- | --- | --- |
| 会话存储 | `SessionStore` (内存) | Redis Cluster / Postgres |
| 向量存储 | `InMemoryVectorStore` (numpy) | Qdrant / Milvus / pgvector |
| 推理后端 | 单机 Ollama | Ollama 集群 / vLLM / TGI / 云端 OpenAI-兼容网关 |
| 鉴权 | — | 在 `main.py` 追加 API-Key / OAuth2 依赖 |
| 观测 | FastAPI 默认日志 | OpenTelemetry + Prometheus + Loki |
| 反代 | — | Nginx / Caddy（注意关 `proxy_buffering` 保活 SSE） |

同一套路由与 schema 可以无缝从单机部署演进到多机房多租户部署。

---

## 7. 模型选型建议 (2026)

> 选型口径：Ollama 官方 registry + 公开 benchmark；硬件按常见自建 GPU 给出参考。

### 7.1 对话 / Agent 主力模型（含 function calling）

| 模型 | 尺寸 | 推荐场景 | 显存 (Q4_K_M) | 备注 |
| --- | --- | --- | --- | --- |
| **Qwen3 8B** | 8B | 通用对话、工具调用、中文强 | ~6 GB | 8B 档位工具调用稳定性最好，中文默认首选 |
| **Gemma 4** | 12B | 结构化抽取 / 函数调用 | ~8 GB | 原生训练带 tool-calling，英文场景更强 |
| **Llama 3.3 8B-Instruct** | 8B | 英文指令跟随 | ~6 GB | 指令风格稳定，适合作为备选 |
| **Qwen3 32B** | 32B | 复杂推理、长上下文 Agent | ~20 GB | 24 GB 卡可跑；多步工具编排场景 |
| **Qwen3-Coder 32B** | 32B | 代码 Agent / DevOps / Text2SQL | ~20 GB | 工具调用精度高 |
| **Llama 3.3 70B** | 70B | 高质量 RAG Generator | 多卡 / 48 GB+ | 128K 上下文、幻觉低 |

### 7.2 Embedding（RAG / 记忆）

| 模型 | 维度 | 语种 | 备注 |
| --- | --- | --- | --- |
| **nomic-embed-text** | 768 | 英文为主 | 默认 baseline，274 MB，最长 8192 tokens |
| **bge-m3** | 1024 | 多语 / 中英 | 中文 RAG 首选，支持稠密 + 稀疏 + multi-vec |
| **Qwen3-embedding 0.6B / 4B** | 1024 / 2560 | 多语 | MTEB 头部，适合高召回要求的企业 KB |
| **mxbai-embed-large** | 1024 | 英文 | 英文 benchmark 强，延迟略高 |

### 7.3 选型决策树

```
中文为主 ────────────► 生成: Qwen3 8B / 32B     召回: bge-m3
英文为主 ────────────► 生成: Llama 3.3 / Gemma 4 召回: nomic-embed-text
Agent / Tool calling ► 首选 Qwen3 8B；高难度上 Qwen3 32B / Gemma 4
代码 / Text2SQL ─────► Qwen3-Coder 32B
低配笔记本 (8 GB) ───► Qwen3 4B + nomic-embed-text
高配工作站 (24 GB) ──► Qwen3 8B + bge-m3 + 可选 32B 作复杂推理
离线隐私优先 ─────────► 全链路本地 Ollama，不走任何云端 embedding
```

### 7.4 模型切换

编辑 `.env`:

```env
CHAT_MODEL=qwen3:32b           # 换更强 Agent 模型
EMBED_MODEL=bge-m3             # 换中文 embedding
EXTRACT_MODEL=gemma3:12b       # 结构化抽取专用
```

或者按请求覆盖：

```json
POST /chat
{"model": "qwen3:32b", "messages": [...] }
```

---

## 8. 测试

```bash
pytest -q
```

默认冒烟测试不依赖真实 Ollama（仅校验路由注册 / 健康检查）。端到端测试需本机 `ollama serve`
运行且模型已拉取。

## 9. 路线图

- [ ] API-Key / OAuth2 多租户鉴权中间件
- [ ] Redis 会话存储驱动
- [ ] Qdrant / Milvus 向量存储驱动
- [ ] OpenTelemetry 接入 + Grafana 面板
- [ ] LangGraph / MCP Agent 编排示例
- [ ] 推理后端灰度（Ollama / vLLM / 云端兼容网关）

---

## License

Licensed under the [Apache License, Version 2.0](./LICENSE).
