# self-improving-agent 迭代升级 · 交付报告

> 需求：检索 GitHub 上 self-improving-agent 开源实现，参考业界方案，迭代升级项目，
> 优化 agent 能力与代码质量。
> 执行顺序（用户指定）：调研报告 → 推荐引擎自学习 → 经验记忆层 → AI 质检闭环 → 统一验证。
> 日期：2026-09-28。

---

## 一、调研结论（详见《self-improving-agent调研与升级报告.md》）

业界 self-improving-agent（letta / autocontext / OS-Copilot / agent-beacon / prime-agent）的
「自我改进」本质是**三支柱**：

1. **记忆层**：把经验结构化持久化，跨会话复用（非日志，而是可检索/可复用/可审计）
2. **反馈闭环**：用真实信号（点击/时长/收藏/纠错）反哺行为
3. **门控提升**：新经验先试运行、验证后才提升为长期策略，失败则淘汰（fail-closed）

本项目此前**没有独立 agent 组件**，`ai.py` 无状态、`recommender.py` 权重写死、已采集的
反馈信号（read_duration/收藏/评论）未反向利用。本次把三支柱**轻量嵌入**现有 AI 大脑与推荐引擎，
不引入重型框架、不破坏分层。

---

## 二、本次落地内容

### 1. 推荐引擎自学习（反馈闭环 + 自优化）

| 文件 | 改动 |
|---|---|
| `app/models/profile.py` **新增** | `UserProfile` 用户兴趣画像（user_id + tag + score + last_seen_at） |
| `app/services/learning.py` **新增** | `record_feedback`（反馈回流）/ `get_interest_weights`（兴趣读取）/ 时间衰减 |
| `app/api/v1/history.py` | `record_history` 接入 `record_feedback`，把阅读时长+收藏+标签喂给画像 |
| `app/services/recommender.py` | `_get_user_preferred_tags` 优先读画像权重，画像空时回退启发式（fail-closed） |

**效果**：推荐引擎的兴趣来源从「每次现算历史统计」升级为「持久化、可衰减、随行为演进」的画像。
用户越常读某类文章，该类权重越高；久不读则自然降温（30 天半衰期）。

### 2. 经验记忆存储层（记忆层）

| 文件 | 改动 |
|---|---|
| `app/models/experience.py` **新增** | `AgentExperience`（category + key + value JSON + score + last_used_at） |
| `app/services/memory.py` **新增** | `remember` / `recall` / `recall_all` / `reinforce` / `penalize` |

**设计**：经验按 `(category, key)` 去重，score 表可信度；命中成功加分（门控提升）、失败扣分、
低于阈值自动淘汰（fail-closed）；60 天未命中自然降温。

### 3. AI 生成质检闭环（反馈闭环 + 记忆）

| 文件 | 改动 |
|---|---|
| `app/services/ai_quality.py` **新增** | 质检纯函数 + 失败经验沉淀 + 标签二次修正 |
| `app/services/ai.py` | `process_article`（唯一有 db 的 AI 入口）接入质检闭环 |

**效果**：摘要/打标结果做质检（过短/纯符号/数量异常判低质），失败模式沉淀到记忆层；
打标结果用记忆层的 tag_fix 经验做二次修正（AI 常见误打标归一化）。

---

## 三、验证结果（可复现）

| 验证项 | 结果 |
|---|---|
| 后端 lint | ✅ `ruff check app/` All checks passed |
| 后端测试 | ✅ `pytest tests/ -q` **18 passed** |
| 后端导入 | ✅ 新模型/服务全部导入无循环依赖 |
| 质检纯函数 | ✅ 空/短/纯符号判低质，合法内容判通过 |
| 衰减函数 | ✅ 30 天衰减到 0.5（符合半衰期设计） |
| 自学习闭环（隔离内存库） | ✅ 3 标签全部写入、score>0 |
| 自学习闭环（真实端到端） | ✅ `user_profile` 写入「科技/设计/文化」score=1.5 |

> 真实端到端证据：`POST /history/8990`（read_duration=180）→
> `user_profile` 表出现 3 行 `(科技,1.5)(设计,1.5)(文化,1.5)`，印证「阅读→反馈回流→画像」链路贯通。

---

## 四、修复的 Bug

1. **`_ensure_profile` 依赖 column default 懒填充**：新建 `UserProfile` 未 flush 时
   `last_seen_at` 为 None，导致 `_decay_factor` 抛 `'NoneType' has no attribute 'tzinfo'`，
   整个 `record_feedback` 被 try 吞掉 → 只写入第一个标签、score=0。
   修复：显式赋值 `last_seen_at`，并给 `_decay_factor` 加 None 兜底。

---

## 五、设计原则（借鉴 autocontext）

- **纯 service 层**：所有新逻辑不引用 FastAPI HTTP 类型，只依赖 SQLAlchemy 会话
- **fail-closed + 可关停**：任何学习/质检异常都被吞掉并告警，绝不影响主流程；
  画像空时推荐引擎自动回退默认策略
- **门控提升**：经验 score 阈值过滤，低可信度经验不返回
- **幂等 + 有界**：score 夹紧到上限，标签数有上限，防异常值污染

---

## 六、遗留与建议

1. **画像/经验的可视化**：`user_profile` / `agent_experience` 目前仅后端可用，
   可考虑在设置页加「兴趣画像」查看/重置入口（需前端配合）。
2. **经验淘汰策略**：当前是 score 阈值 + 时间衰减，未做显式容量上限，
   长期可加「最大条数 + LRU 淘汰」。
3. **A/B 验证**：推荐自学习效果需一段时间的真实点击数据验证（可加权重学习率的线上调参）。
4. **前端无改动**：本次纯后端迭代，前端无需重新构建，接口契约未变（新增模型不影响现有 API）。

## 七、改动文件清单

**新增（5）**
- `app/models/profile.py`、`app/models/experience.py`
- `app/services/learning.py`、`app/services/memory.py`、`app/services/ai_quality.py`

**修改（4）**
- `app/models/__init__.py`（注册新模型）
- `app/services/recommender.py`（读画像权重）
- `app/services/ai.py`（接入质检闭环）
- `app/api/v1/history.py`（接入反馈回流）
