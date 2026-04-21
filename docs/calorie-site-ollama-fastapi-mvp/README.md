# Calorie-Calculator 业务 MVP README（Ollama + FastAPI）

## 1. 选择的真实业务场景

基于你网站现状，最适合先做的 MVP 不是“泛聊天”，而是：

**Pro 精准摄入估算（Agent Intake）后端化**

即：用户输入自然语言餐食描述 -> FastAPI 调 Ollama 做结构化解析 -> 用确定性规则算总热量 -> 回填到你现有 `agent_intake` 方案。

## 2. 为什么这个场景可以直接落地

你站点已经有完整“接入点”，不用重做产品流程：

- `js/calorie_calculator.js` 已有 `agent_intake` 选项与回填逻辑。
- `js/pro_access.js` 已监听 `postMessage` (`agent-calories` / `agent-calories-total`) 并同步 `cc-agent-intake`。
- `pro-plan.html` 已有 `iframe` 工作区（`/agent/index.html`）和 Pro 锁定机制。

这意味着你只需补齐“Agent 计算后端”，主站交互几乎不动。

## 3. MVP 目标（两周内可交付）

- 输入：一段餐食自然语言（例："午餐吃了 150g 鸡胸肉、1 碗米饭、半杯酸奶"）
- 输出：
  - 结构化食材列表
  - 每项估算热量
  - 总热量 `total_kcal`
  - 未识别项 `unmatched_items`
  - 置信度与说明
- 前端回填：通过你现有 `postMessage` 机制回填 `cc-agent-intake`

## 4. 技术架构

```text
/agent/index.html (现有工作区)
  -> POST /agent/intake/estimate (FastAPI)
      -> Ollama (结构化抽取)
      -> 本地确定性热量计算 (foods 表 + 份量换算)
  <- 返回 total_kcal + 细项
  -> window.parent.postMessage({ type: 'agent-calories-total', calories: total_kcal }, '*')
```

## 5. API 设计（第一版）

### 5.1 `POST /agent/intake/estimate`

Request:

```json
{
  "locale": "en",
  "text": "Lunch: 150g chicken breast, 1 bowl rice, 1/2 cup yogurt",
  "meal_type": "lunch",
  "user_profile": {
    "weight_kg": 70,
    "goal": "fat_loss"
  }
}
```

Response:

```json
{
  "total_kcal": 547,
  "items": [
    {
      "food_id": "proteins_chicken_cooked",
      "food_name": "Chicken, cooked",
      "servings": 2.65,
      "kcal": 360
    },
    {
      "food_id": "common_meals_snacks_rice",
      "food_name": "Rice",
      "servings": 1.0,
      "kcal": 206
    },
    {
      "food_id": "beverages_dairy_yogurt_low_fat",
      "food_name": "Yogurt (low-fat)",
      "servings": 0.5,
      "kcal": 77
    }
  ],
  "unmatched_items": [],
  "confidence": 0.86,
  "notes": [
    "Portion assumptions applied for bowl/cup conversions."
  ]
}
```

### 5.2 `GET /agent/catalog/foods`

用于前端做自动补全，直接复用你现有 food 数据集。

### 5.3 `POST /agent/intake/verify`（可选，MVP+1）

对模型抽取结果做二次校验（异常份量、重复项、单位冲突）。

## 6. 模型与职责切分（防幻觉关键）

- **Ollama 模型职责**：只做“餐食文本 -> 结构化食材与份量”抽取。
- **确定性代码职责**：热量计算必须走规则，不直接信模型给的 kcal。

建议默认模型：
- `qwen3:8b` 或 `qwen2.5-7b`（中文/英文混合输入都较稳）

## 7. 与你现有网站的接入改动

最小改动路径：

1. 在 `/agent/index.html` 对应脚本里调用 FastAPI `POST /agent/intake/estimate`。
2. 拿到 `total_kcal` 后发送：

```js
window.parent.postMessage({ type: 'agent-calories-total', calories: totalKcal }, '*');
```

3. `index.html` 主计算器无需改核心逻辑（你已实现回填与再计算触发）。

## 8. 安全与业务边界

- 这是营养估算工具，不是医疗诊断。
- 对孕妇、慢病、用药人群输出固定提示：建议专业医生/营养师复核。
- 记录抽取假设（单位换算、烹饪损耗），保证可追溯。

## 9. 里程碑

1. Day 1-2：FastAPI 路由 + schema + Ollama 结构化抽取原型。
2. Day 3-4：份量换算与确定性计算模块。
3. Day 5：与 `/agent/index.html` 打通回填。
4. Day 6-7：误差测试 + 置信度策略 + 提示词加固。

## 10. 后续扩展（不进入首期 MVP）

- FAQ RAG（用你现有 `/api/faq-articles` 数据做问答证据化）
- 评论风控（垃圾/攻击性评论分类）
- 用户周度摄入趋势分析与个性化提醒

## 11. 你的当前状态与替换目标

你当前线上使用的是 `OpenAI gpt-5-nano`。建议替换路径如下：

1. 先替换 Pro 场景中的“餐食结构化抽取”这一个点，不一次性替换全站。
2. 本机主机先连续运行 24 小时做稳定性验证（不关机）。
3. 验证通过后，再做云端迁移（AWS 为主，Cloudflare/Vercel 承担前端与边缘层）。

这样风险最小，且不会影响你现有主站其余功能。

## 12. 第一阶段：本机 24 小时稳定运行（必须先做）

### 12.1 启动方式（建议）

使用你当前仓库已有的 `docker-compose.yml`，它已包含：

- `restart: unless-stopped`（容器异常自动拉起）
- `ollama` 与 `api` 服务分离

```bash
docker compose up -d --build
docker exec -it ollama ollama pull qwen3:8b
docker exec -it ollama ollama pull nomic-embed-text
```

### 12.2 24h 观测指标（最少）

- API 可用率（`/health` 成功率）
- 端到端成功率（`/chat` 或未来 `/agent/intake/estimate`）
- p95 延迟
- 失败类型分布（超时 / 5xx / 模型不可用）

可直接运行仓库脚本做 burn-in：

```bash
bash scripts/soak_24h.sh
```

### 12.3 通过标准（建议）

- 24 小时内可用率 >= 99%
- 无连续 5 分钟不可用
- 无 Ollama 进程崩溃或模型丢失
- 端到端成功率 >= 98%

## 13. 第二阶段：云端迁移路线

### 13.1 AWS 全量迁移（推荐主路径）

推荐用于“模型也要上云并长期运行”的情况：

- `FastAPI + Ollama` 部署在 AWS（常见为 EC2 GPU 实例）
- 前端站点仍可在你现有静态托管体系
- API 网关做鉴权、限流、日志

优点：对 Ollama 最友好，长期运行稳定，可控性高。  
缺点：需要管理 GPU 成本和运维。

### 13.2 Cloudflare / Vercel 承担边缘层（推荐组合）

Cloudflare/Vercel 更适合：

- 前端静态资源与边缘缓存
- 轻量 API 网关、鉴权、路由编排
- 近用户地区接入

不建议把 Ollama 模型进程直接作为 Workers/Functions 的核心承载。更稳的方式是：

`Cloudflare/Vercel(边缘) -> FastAPI(AWS) -> Ollama(AWS)`

## 14. 第三阶段：灰度与回滚策略

建议在替换 `gpt-5-nano` 时保留双通道：

- 主通道：`Ollama + FastAPI`
- 兜底通道：`gpt-5-nano`（仅在本地通道失败时触发）

灰度步骤：

1. 10% 流量走新链路，观察 24h
2. 30% 流量继续观察
3. 100% 切换后保留云兜底至少 7 天

回滚条件（任一满足立即回滚）：

- 连续 5 分钟错误率 > 5%
- 关键路径 p95 延迟超阈值
- 模型输出质量明显下降（人工抽样不合格）

## 15. 模型执行可视化窗口（已实现）

为便于验证“用户 query -> 模型理解 -> 输出结果”的全链路，当前项目已提供：

- `GET /ui/chat`：浏览器可视化对话窗口
- `POST /chat/sessions`：创建新会话
- `GET /chat/sessions/{session_id}`：加载历史会话

说明：
- 前端默认走 `POST /chat/stream`，可实时看到 token 输出。
- 会话历史会写入 `data/sessions/*.jsonl`，实现 MVP 级“初步记忆”。
