# fufu新闻 — CLAUDE.md

## 项目概览

fufu新闻（fufu news）是一个甜系二次元风格的新闻阅读器 / RSS 聚合应用。

- **后端**: Python FastAPI + SQLAlchemy (async) + SQLite + FTS5 全文搜索（端口 8800）
- **前端**: React 18 + TypeScript + Vite + Tailwind CSS（`fufu-web/`，端口 3000）
- **AI**: DeepSeek API（兼容 OpenAI 协议）— 摘要/标签/流式对话
- **主题**: 初音未来风格（青绿 `#00e5ff` + 浅粉 `#ffb6c1`）

```
fufu新闻/
├── fufu-server/          # Python 后端 (FastAPI, 端口 8800)
│   ├── app/
│   │   ├── api/v1/       # API 路由（文章/搜索/AI/源管理/成就/OPML）
│   │   ├── core/         # 配置 / 数据库 / 安全认证
│   │   ├── models/       # SQLAlchemy ORM 模型
│   │   ├── schemas/      # Pydantic 数据校验
│   │   └── services/     # 业务逻辑（抓取/搜索/AI/调度/OPML）
│   ├── .env              # 环境变量（含 API Key，已 gitignore）
│   ├── .env.example      # 环境变量模板（占位符）
│   └── requirements.txt  # Python 依赖
├── fufu-web/             # Vite + React 前端（端口 3000）
│   ├── src/
│   │   ├── api/          # API 客户端（axios 封装）
│   │   ├── components/   # React 组件
│   │   │   ├── effects/  # 视觉特效（樱花/粒子/倾斜卡/鼠标光晕）
│   │   │   ├── companion/# AI 助手组件
│   │   │   ├── layout/   # 布局（侧边栏/主布局）
│   │   │   └── common/   # 通用组件（虚拟列表/错误边界）
│   │   ├── hooks/        # 自定义 Hooks
│   │   ├── pages/        # 页面（首页/文章/搜索/收藏/设置）
│   │   ├── stores/       # Zustand 状态管理
│   │   ├── lib/          # 工具库（IndexedDB 缓存/启动自检）
│   │   ├── config/       # 动效参数配置
│   │   └── styles/       # Tailwind + 全局样式
│   ├── vite.config.ts    # Vite 配置（代理 /api → localhost:8800）
│   └── tailwind.config.js
├── data/                 # SQLite 数据库和日志
├── launch.py             # 一键启动脚本（自动建 venv + 装依赖）
├── 启动.bat              # Windows 启动入口
├── 说明.txt              # 用户使用说明
└── CLAUDE.md             # ← 本文件（AI 开发指南）
```

---

## 本项目启用的 Skills

以下 skills 在本项目中**始终生效**，Claude Code 在对话中会自动调用：

### 前端开发

| Skill | 触发场景 |
|-------|---------|
| `frontend-design` | 创建/修改 UI 组件、页面、样式时 |
| `vercel-react-best-practices` | React 组件开发、状态管理、性能优化 |
| `web-design-guidelines` | 设计系统、配色、排版、响应式布局 |

### 代码质量

| Skill | 触发场景 |
|-------|---------|
| `code-review` | 提交前审查代码 diff |
| `simplify` | 重构简化代码（等同于 /code-review --fix） |
| `improve-codebase-architecture` | 架构重构、模块解耦、领域建模 |
| `security-review` | 安全性检查（输入校验、认证、授权） |

### 后端 & API

| Skill | 触发场景 |
|-------|---------|
| `claude-api` | AI 对话/摘要/标签功能开发，DeepSeek API 调用 |
| `mcp-builder` | 需要构建 MCP 服务器时 |
| `mcp-integration` | 集成外部 MCP 服务时 |

### 开发流程

| Skill | 触发场景 |
|-------|---------|
| `verify` | 验证代码变更是否正常工作 |
| `run` | 启动前后端服务进行测试 |
| `diagnose` | 排查 bug、错误、性能问题 |
| `update-config` | 修改 settings.json 配置 |
| `fewer-permission-prompts` | 减少工具调用的权限弹窗 |

### 本项目专用 Skills（已安装到 ~/.claude/skills/）

| Skill | 用途 |
|-------|------|
| `api-debugger` | API 端点调试：CORS/代理/超时/认证 |
| `fastapi-backend-dev` | FastAPI 后端开发：端点/模型/异步/错误处理 |
| `react-frontend-fixer` | React 前端修复：状态/null guard/条件渲染 |
| `miku-ui-designer` | 初音未来 UI 设计：配色/文案/装饰/动画 |
| `search-engine-builder` | 搜索引擎构建：ddgs/AI fallback/防抖/分页 |
| `ai-integration-engineer` | AI 集成：DeepSeek/流式/摘要/标签/prompt |
| `code-review-automation` | 代码审查：bug 检测/安全检查/最佳实践 |
| `vite-dev-server-expert` | Vite 开发服务器：代理/HMR/构建/端口 |
| `sqlite-database-debugger` | SQLite 数据库：FTS5/WAL/异步查询/锁 |
| `tailwind-css-master` | Tailwind CSS：设计令牌/动画/响应式/暗黑模式 |
| `project-launcher` | 项目启动：一键启动/健康检查/依赖验证 |

### 自动化 & 维护

| Skill | 触发场景 |
|-------|---------|
| `claude-md-improver` | 改进本 CLAUDE.md 文件 |
| `claude-automation-recommender` | 推荐 hooks、MCP、plugins 配置 |
| `writing-rules` | 编写 hook 自动化规则 |
| `skill-creator` | 为项目创建自定义 skill |

---

## 开发约定

### 后端
- 所有 API 响应格式：`{ code: 200, data: [...], message: "ok" }`（失败时 `data: []`）
- 搜索接口：`GET /api/v1/search/web?q=关键词`
- AI 流式接口：`POST /api/v1/ai/chat/stream`（SSE）
- 不直接抛异常给前端，捕获后返回统一错误格式
- 关键操作加 `logging.getLogger("fufu.xxx")` 日志
- API Key 通过 `.env` 文件配置，**不在源码中硬编码**

### 前端（Vite + React 18）
- React Router v6 客户端路由，页面级 lazy loading
- Zustand 状态管理（settings/auth/companion/achievement）
- 所有列表数据使用空数组 `[]` 兜底
- `.length` / `.map` 调用前确保数据不为 undefined
- 分类体系：父分类（可折叠）+ 子分类（可筛选）
- IndexedDB 离线缓存（TTL 7 天，上限 1000 条）
- 启动自检：网络 → IndexedDB → API 连通性 → 缓存完整性

### 配色
- 主色 `#00e5ff`（青绿）→ `fufu-teal`
- 辅色 `#ffb6c1`（浅粉）→ `fufu-pink`
- 背景 `#F5FCFF` → `fufu-cream`
- 高亮 `#E0F7FA` → `fufu-highlight`
- 文字 `#3A4A50` → `fufu-text`

### 设计令牌（Tailwind）
```js
// tailwind.config.js 中定义的设计令牌
colors.fufu: {
  teal: '#00e5ff', 'teal-deep': '#39c5bb', 'teal-light': '#4df0ff',
  pink: '#ffb6c1', 'pink-light': '#ffd0d9',
  cream: '#F5FCFF', 'cream-soft': '#F0FAFF',
  text: '#3A4A50', 'text-light': '#78909C', 'text-muted': '#A0B8C0',
}
```

---

## 快速启动

```bash
# 一键启动（推荐）
python launch.py

# 或分别启动：
# 后端
cd fufu-server
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8800 --reload

# 前端
cd fufu-web
npm install
npm run dev          # Vite dev server → localhost:3000

# 或双击启动.bat 一键启动
```

---

## 分类体系说明

### 当前订阅源分布

| 分类 | 源数量 | 用途 |
|------|--------|------|
| 💻 科技 | 22+ | 科技资讯·互联网·AI前沿·编程·数码评测 |
| 🎮 游戏 | 7+ | 新游资讯·攻略测评·电竞赛事·社区 |
| 🌸 动漫二次元 | 7+ | 新番追踪·ACG资讯·B站排行·动漫新闻 |
| 🎨 设计创意 | 5+ | 设计资源·用户体验·创意工具·独立博客 |
| 🌿 科普知识 | 5+ | 科学发现·自然探索·健康生活·天文航天 |
| 📰 综合资讯 | 5+ | 社会热点·财经时事·生活消费 |

**当前共 51+ 个订阅源**（持续扩充中），每个源标注：访问方式、更新频率、内容描述。
调度器自动维护：活跃源每 5 分钟抓取，错误源指数退避重试，死源自动暂停/清理。
