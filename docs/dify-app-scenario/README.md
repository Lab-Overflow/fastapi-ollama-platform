# Dify 应用场景 README（Ollama + Hugging Face 替代云模型）

## 场景目标

把 Dify 工作流中当前使用的云模型节点（例如 `gpt-5-nano`）替换为本地 `Ollama + Hugging Face` 开源模型，降低调用成本并强化数据私有化。

## 关键结论（来自本轮排查）

- Dify 的验证码流程里，“生成 + 存储 + 校验”是业务逻辑层，Self-host 与 Cloud 都存在。
- Self-host 未配置 SMTP 时，验证码可能只落在 Redis（短 TTL）但不送达。
- Cloud 多出来的是通道能力：邮件厂商鉴权、域名信誉、退信/投诉处理、速率控制与送达优化。

这套结论可扩展到同类场景：
- 密码重置码、邀请链接验证、登录 2FA
- 短信 OTP（SMTP 替换为 SMS 通道）
- 风控挑战码（业务逻辑可本地化，送达链路依赖外部厂商）

## 替换方案：Dify LLM 节点从 OpenAI 到 Ollama

### 1. 准备 Hugging Face 开源模型（推荐 GGUF）

```bash
mkdir -p ./models/qwen
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF \
  qwen2.5-7b-instruct-q4_k_m.gguf \
  --local-dir ./models/qwen
```

### 2. 导入 Ollama

```bash
cat > Modelfile <<'EOF2'
FROM ./models/qwen/qwen2.5-7b-instruct-q4_k_m.gguf
PARAMETER temperature 0.2
EOF2

ollama create qwen2.5-7b-hf -f Modelfile
ollama run qwen2.5-7b-hf
```

### 3. Dify 配置改造

- 在 Dify `Model Provider` 添加 `Ollama`
- `Base URL` 指向 Ollama 服务（常见：`http://host.docker.internal:11434`）
- 模型名填 `qwen2.5-7b-hf`
- 将工作流中原 `gpt-5-nano` 节点切换为该本地模型

### 4. 是否加入 FastAPI（可选）

- 简化链路：`Dify -> Ollama`
- 增强链路：`Dify -> FastAPI -> Ollama`

增强链路适合你要做审计、限流、内容后处理、AB 灰度的情况。

## 推荐落地顺序

1. 先在 Dify 直接替换 LLM 节点，验证输出质量和延迟。
2. 再决定是否加 FastAPI 网关层（避免一开始过度工程化）。
3. 最后补 SMTP/SMS 通道，解决生产送达问题。
