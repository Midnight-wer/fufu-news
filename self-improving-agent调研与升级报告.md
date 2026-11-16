# self-improving-agent 业界方案调研与 fufu新闻 迭代升级报告

> 目标：检索 GitHub 上 self-improving-agent 相关开源实现，提炼业界核心模式，
> 对照 fufu新闻 现状，给出差距分析与分阶段落地路线图，指导后续代码迭代。
> 调研时间：2026-09-28 · 来源：GitHub API（gh / GitHub MCP）+ 官方 README。

---

## 一、业界代表性开源方案

| 项目 | Stars | 定位 | 一句话核心 |
|---|---|---|---|
| [letta-ai/letta](https://github.com/letta-ai/letta) | 24.9k | 有状态 agent 平台 | AI with advanced memory that can **learn and self-improve over time** |
| [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) | 21.3k | 自我改进 RLM 编码 agent | 长时自治任务 + 从执行结果学习 |
| [aden-hive/hive](https://github.com/aden-hive/hive) | 11.1k | 生产级多 agent harness | 多 agent 协作 + 人类在环 + 自我改进 |
| [MervinPraison/PraisonAI](https://github.com/MervinPraison/PraisonAI) | 9.1k | 24/7 AI 劳动力 | 内建 memory + RAG + 自改进 agent |
| [greyhaven-ai/autocontext](https://github.com/greyhaven-ai/autocontext) | 1.3k | 递归自改进 harness | **Goal → Evaluate → Keep/Discard** 循环 + 门控提升 |
| [facebookresearch/HyperAgents](https://github.com/facebookresearch/HyperAgents) | 2.7k | 自指涉自改进 agent | 为任意可计算任务优化自身 |
| [Asymptote-Labs/agent-beacon](https://github.com/Asymptote-Labs/agent-beacon) | 1.6k | 跨 harness 记忆层 | 自我改进的 agent 记忆/知识库 |
| [OS-Copilot/OS-Copilot](https://github.com/OS-Copilot/OS-Copilot) | 1.8k | 具身对话 agent | 从交互反馈中自我改进 |

> 其余高频出现（供扩展参考）：Leeroo-AI/kapso（长时 agent、从每次经验学习）、
> EverMind-AI/Raven（递归自改进 RSI）、sirius（多 agent 自举推理）、
> A-EVO-Lab/a-evolve（agentic evolution）。

---

## 二、业界「自我改进」的三大共性支柱

把上述项目剥开，所有「self-improving」能力都可归为三条相互咬合的机制：

### 支柱 1：记忆层（Memory Layer）—— 让经验跨会话沉淀
- **letta**：分级记忆（in-context / **recall memory** / **archival memory**），
  memory blocks 随对话**自更新**，agent 状态可持久化到云端、跨设备续用。
- **agent-beacon**：专门的跨 harness「记忆层」，把知识从单次对话中剥离出来长期复用。
- **autocontext**：`knowledge/<scenario>/playbook.md` + `hints.md` + `context_bundles`，
  **文件系统优先**，所有经验可 inspect / diff / replay。
- 要点：记忆不是日志，而是**可检索、可复用、可审计**的结构化经验。

### 支柱 2：反馈闭环（Feedback Loop）—— 用真实信号反哺行为
- **OS-Copilot**：从用户交互结果学习，失败/成功都转化为下次行动的约束。
- **prime-agent / kapso**：任务执行结果（通过/失败）回流，修正后续策略。
- 要点：必须存在「行为 → 结果 → 评价 → 修正行为」的闭环，否则只是无记忆的一次性调用。

### 支柱 3：自我优化（Self-optimization）—— 从历史中学习而非每次从零开始
- **autocontext** 最典型：`Goal → Evaluate → Keep useful lessons / Discard dead ends`，
  下一轮从沉淀的 traces/reports/playbooks 出发，而非冷启动。
- **门控提升（promotion-gated）**：新经验先作「不可变候选」，经配对试验验证后才进入 serving；
  **fail-closed**（验证不了就拒绝），防止垃圾经验污染系统。
- **消融归因（attribution）**：区分「相关」与「因果」，避免把编辑量相关性误当因果。

> 一句话：**业界不是"模型自己变强"，而是"系统记住经验、用反馈校正、把有效经验门控沉淀"**。
> 这套机制可以完全不依赖模型微调，落地在普通应用层。

---

## 三、fufu新闻 现状诊断

### 3.1 现有 AI/智能组件盘点

| 组件 | 职责 | 是否有记忆 | 是否有反馈闭环 | 是否自优化 |
|---|---|---|---|---|
| `app/services/ai.py` | 摘要 / 打标 / 深度摘要（LLM 调用） | ❌ 无状态 | ❌ 失败仅告警日志 | ❌ 每次冷启动 |
| `app/services/recommender.py` | 多策略混合推荐 | ❌ 权重写死 | ❌ 权重是常量 | ❌ 常量不会变 |
| `app/services/stats.py` | 热度分 / 趋势 | ⚠️ 有热度回写 | ⚠️ 只计浏览/评论/收藏 | ❌ 公式权重写死 |
| `app/models/history.py` | 阅读历史 | ✅ read_duration 存在 | ✅ 已采集 | ❌ 未反向利用 |

### 3.2 差距（Gap）—— 对照三大支柱

1. **缺记忆层**：`ai.py` 每次调用独立，解析失败的模式、prompt 的反复试错、
   标签映射的纠错都没有沉淀，下次照样踩坑。
2. **缺反馈闭环**：项目**已经采集了最宝贵的隐式反馈信号**——
   `read_duration`（阅读时长，最强的兴趣信号）、收藏、评论、点击，
   但 `recommender.py` 的五项权重（0.35/0.20/0.25/0.10/0.10）是写死的，
   反馈信号**没有回流**到推荐策略。
3. **缺自我优化**：没有「评估 → 保留有效 / 丢弃无效」的机制，
   推荐质量和 AI 生成质量无法随使用而提升。

### 3.3 关键判断

> 本项目**没有独立的 "agent" 组件**，不应生搬 letta/autocontext 的重型框架
> （那样会破坏现有 FastAPI + React 分层架构）。正确做法是：
> **把业界三支柱「翻译」成项目已有的两个智能组件（AI 大脑 + 推荐引擎）的轻量增强**，
> 用 SQLite 持久化经验 + 已有反馈信号，实现「记忆 + 反馈 + 自优化」闭环。

---

## 四、落地路线图（按优先级）

| 阶段 | 内容 | 对应支柱 | 业界参照 | 风险 |
|---|---|---|---|---|
| **P1** | 推荐引擎自学习：策略权重与标签兴趣按真实反馈动态调整 | 反馈闭环 + 自优化 | letta / OS-Copilot | 中（涉及评分算法） |
| **P2** | 经验记忆存储层：轻量经验库，沉淀 prompt 微调 / 失败模式 / 标签修正 / 调参轨迹 | 记忆层 | autocontext / agent-beacon | 低（纯新增） |
| **P3** | AI 生成质检闭环：解析失败、空结果自动降级重试并沉淀经验 | 反馈闭环 + 记忆 | autocontext fail-closed | 低（增强 ai.py） |
| **P4** | 统一验证与交付：ruff / pytest / 前端 build / 浏览器走查 + 交付报告 | — | — | 低 |

### 设计原则（从 autocontext 借鉴）

1. **文件系统/DB 优先**：经验落 SQLite 表，可审计、可回滚（本项目用 ORM，天然满足）。
2. **门控提升**：新经验先试运行，效果好才提升为长期策略，避免污染。
3. **Fail-closed + 兜底**：任何学习机制失效时，回退到现有写死常量/无记忆行为，**绝不让升级引入回归**。
4. **可关停**：每个能力都有开关，可一键退化为当前行为（回滚安全）。

### 关键反馈信号（已有，无需新增采集）

| 信号 | 来源 | 语义 | 用途 |
|---|---|---|---|
| `read_duration` | `ReadHistory` | 阅读时长秒数 | 最强的兴趣正反馈 |
| 收藏 `is_favorite` | `Article` | 强正反馈 | 提升内容权重 |
| 评论 | `ArticleStats.comment_count` | 强正反馈 | 提升互动权重 |
| 点击 `view_count` | `ArticleStats` | 弱正反馈 | 趋势权重 |

---

## 五、结论

业界 self-improving-agent 的本质是**「记忆 + 反馈 + 门控自优化」三支柱**，
而非模型层面的自我进化。fufu新闻 已有反馈信号采集基础，缺的是「记忆层」与
「反馈回流 + 门控沉淀」这一层。本次迭代按 P1→P4 落地，把三个支柱以轻量、
可关停、可回滚的方式嵌入现有 AI 大脑与推荐引擎，即可在不引入重型框架、
不破坏现有分层的前提下，实现 agent 能力的实质升级。

（详细实现见后续各阶段任务：推荐引擎自学习 → 经验记忆层 → AI 质检闭环 → 统一验证交付。）
