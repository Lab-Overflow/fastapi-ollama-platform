# FastAPI + Ollama MVP

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688.svg)](https://fastapi.tiangolo.com/)

一个面向 **2026 年常见业务场景** 的本地 LLM 后端骨架：一份代码即覆盖企业里 80% 的 LLM 需求。

| 业务场景 | 路由 | 说明 |
| --- | --- | --- |
| 多轮对话 / 流式输出 | `POST /chat`, `POST /chat/stream` | SSE 流、带 `session_id` 的会话记忆 |
| 知识库问答 (RAG) | `POST /rag/ingest`, `POST /rag/query` | 文本分块 → 向量 → 余弦召回 → 生成，带引用 |
| 结构化抽取 / 函数调用 | `POST /extract` | 基于 Ollama `format=<JSON Schema>` 的强约束输出 |
| 运维接口 | `GET /health`, `GET /models` | 健康检查 + 本地模型列表 |

所有请求走 **异步 + 并发信号量** 保护，不会把单卡 GPU 打爆。

---

## 1. 目录结构

```
FastAPI+Ollama/
├── app/
│   ├── main.py              # FastAPI 入口 + lifespan
│   ├── config.py            # pydantic-settings 读取 .env
│   ├── schemas.py           # 请求 / 响应模型
│   ├── deps.py              # DI: Ollama / Session / RAG
│   ├── ollama_client.py     # AsyncClient 封装 + 信号量
│   ├── session.py           # 内存会话记忆 (可替换 Redis)
│   ├── rag/
│   │   ├── store.py         # numpy 余弦向量库 (可替换 Qdrant)
│   │   └── pipeline.py      # chunk → embed → retrieve → prompt
│   └── routers/
│       ├── chat.py
│       ├── rag.py
│       ├── extract.py
│       └── health.py
├── tests/test_smoke.py
├── scripts/quickstart.sh
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 2. 快速启动

### 本机模式

```bash
# 1) 启动 Ollama 并拉模型
ollama serve &
ollama pull qwen3:8b
ollama pull nomic-embed-text

# 2) 启动 API
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

打开 `http://localhost:8000/docs` 查看交互式 OpenAPI 文档。

### Docker Compose 一键起

```bash
docker compose up -d
# 进入 ollama 容器拉模型
docker exec -it ollama ollama pull qwen3:8b
docker exec -it ollama ollama pull nomic-embed-text
```

## 3. 调用示例

### 流式对话 (SSE)

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "demo-001",
    "messages": [{"role": "user", "content": "用三句话解释 RAG"}]
  }'
```

### RAG

```bash
# 入库
curl -X POST http://localhost:8000/rag/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "documents": [
      {"id": "policy-01", "text": "公司年假政策：入职满 1 年享 5 天..."}
    ]
  }'

# 检索问答
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

## 4. 关键设计要点

1. **并发控制**：`asyncio.Semaphore(MAX_CONCURRENCY)` 为每个上游调用加闸，单张 24 GB 卡上 7B 模型建议 2–4 并发。
2. **异步 AsyncClient**：`ollama.AsyncClient` 与 FastAPI 事件循环天然匹配，不阻塞 worker。
3. **结构化输出**：用 Ollama 0.4+ 的 `format=<JSON Schema>`，比 prompt engineering 稳定得多，模型直接输出符合 schema 的 JSON。
4. **RAG 引用透传**：`/rag/query` 返回 `citations`，前端可以直接渲染引用气泡、支持可追溯问答。
5. **可替换依赖**：`SessionStore` / `InMemoryVectorStore` 接口小且独立，生产上换成 Redis / Qdrant 只需改 `lifespan`。
6. **SSE over Nginx**：生产部署时在反代层关掉 `proxy_buffering`，否则 token 不会实时下发。

---

## 5. 模型选型建议 (2026)

> 选型口径：Ollama 官方 registry + 社区 benchmark；硬件按常见本地/小型自建 GPU 给出。

### 5.1 对话 / Agent 主力模型（function calling）

| 模型 | 尺寸 | 推荐场景 | 显存 (Q4_K_M) | 备注 |
| --- | --- | --- | --- | --- |
| **Qwen3 8B** | 8B | 通用对话、工具调用、中文强 | ~6 GB | 8B 档位工具调用稳定性最好，中文默认首选 |
| **Gemma 4** | 12B | 结构化抽取 / 函数调用 | ~8 GB | 原生训练带 tool-calling，英文场景更强 |
| **Llama 3.3 8B-Instruct** | 8B | 英文指令跟随 | ~6 GB | 指令风格稳定，适合作为备选 |
| **Qwen3 32B** | 32B | 复杂推理、长上下文 Agent | ~20 GB | 24 GB 卡可跑；多步工具编排场景 |
| **Qwen3-Coder 32B** | 32B | 代码 Agent / DevOps | ~20 GB | 工具调用精度高，适合 Text2SQL / 代码执行 |
| **Llama 3.3 70B** | 70B | 高质量 RAG Generator | 多卡 / 48 GB+ | 128K 上下文、幻觉低 |

### 5.2 Embedding（RAG / 记忆）

| 模型 | 维度 | 语种 | 备注 |
| --- | --- | --- | --- |
| **nomic-embed-text** | 768 | 英文为主 | 默认 baseline，274 MB，最长 8192 tokens |
| **bge-m3** | 1024 | 多语 / 中英 | 中文 RAG 首选，支持稠密 + 稀疏 + multi-vec |
| **Qwen3-embedding 0.6B / 4B** | 1024 / 2560 | 多语 | MTEB 头部，适合高召回要求的企业 KB |
| **mxbai-embed-large** | 1024 | 英文 | 英文 benchmark 强，延迟略高 |

### 5.3 选型决策树

```
中文为主 ────────────► 生成: Qwen3 8B / 32B   召回: bge-m3
英文为主 ────────────► 生成: Llama 3.3 / Gemma 4   召回: nomic-embed-text
Agent / Tool calling ► 首选 Qwen3 8B；高难度上 Qwen3 32B / Gemma 4
代码 / Text2SQL ─────► Qwen3-Coder 32B
低配笔记本 (8 GB) ───► Qwen3 4B + nomic-embed-text
高配工作站 (24 GB) ──► Qwen3 8B + bge-m3 + 可选 32B 作复杂推理
离线隐私优先 ─────────► 全链路本地 Ollama，不走任何云端 embedding
```

### 5.4 在本 MVP 里切换模型

编辑 `.env`:

```env
CHAT_MODEL=qwen3:32b           # 切到更强 Agent 模型
EMBED_MODEL=bge-m3             # 换中文 embedding
EXTRACT_MODEL=gemma3:12b       # 结构化抽取专用
```

或者按请求覆盖：

```json
POST /chat
{"model": "qwen3:32b", "messages": [...] }
```

---

## 6. 下一步可演进方向

- `SessionStore` → Redis / Postgres，支持水平扩展
- `InMemoryVectorStore` → Qdrant / Milvus，持久化与 HNSW
- 引入 LangGraph 做多步 Agent 编排，复用当前 `/extract` 作为 tool
- Nginx / Caddy 前置：TLS + `proxy_buffering off` 保活 SSE
- 接入 OpenTelemetry，观测 token / RT / 队列长度
- 按租户维度加 API Key 鉴权（中间件层即可）

## 7. 测试

```bash
pytest -q
```

冒烟测试不依赖真实 Ollama（仅校验路由注册 / 健康检查）。若要跑端到端测试，先确保本机 `ollama serve` 在跑且模型已拉取。

---

## License

Licensed under the [Apache License, Version 2.0](./LICENSE).
