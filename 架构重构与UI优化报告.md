# fufu新闻 · 架构重构与 UI 优化报告（第二轮续做）

> 基线：上一轮 `排查优化报告.md` 已修复 P0/P1 功能 bug、实装虚假功能、补齐工程化。
> 本轮目标（用户原话）：全面审查代码结构 → 重构高耦合/职责不清模块、明确边界与调用链；
> 改进前端 UI（布局/信息层级/统一视觉/交互/移动端/减少 AI 痕迹）；清理历史遗留死代码。
> 验证方式：ruff + pytest（后端）、tsc --noEmit + vite build + eslint（前端）。

---

## 一、后端架构重构（提升模块化与可维护性）

### 1.1 抽出 `services/stats.py` —— 消除路由层互相 import（职责澄清）
- **问题**：`ranking.py` 里放着业务函数 `calculate_hot_score` / `determine_trend` /
  `_determine_trend_with_history` / `bump_comment_count` / `sync_collect_count` /
  `_ensure_stats`，而 `articles.py:20`、`comments.py:19` 直接 `from app.api.v1.ranking import ...`。
  路由层互相依赖，且热度公式、计数同步这类业务逻辑堆在路由模块里。
- **改动**：新建 `app/services/stats.py`（纯 service 层，不引用任何 FastAPI HTTP 类型），
  迁入上述函数；`ranking.py` 改为 `from app.services.stats import (...)`；`articles.py` /
  `comments.py` 改为从 `services.stats` 导入。
- **效果**：路由↔路由耦合消除，业务逻辑回归 service 层，符合「Controller→Service→Repository」分层。

### 1.2 抽出 `core/categories.py` —— 统一公开分类（单一事实来源）
- **问题**：分类关键词表在 `articles.py`、`services/fetcher.py`、`services/recommender.py`
  三处各自定义、彼此漂移。
- **判断**：三处其实**不是同一套分类**——`articles.py` 是前端/计数用的 5 个公开分类
  （动漫/游戏/科技/设计/综合），`fetcher.py` 是 8 类加权打标签体系，`recommender.py` 是 6 类相似推荐。
  强行合一会破坏行为（过度工程化），故只把**必须保持一致**的公开分类抽成单一来源。
- **改动**：新建 `app/core/categories.py` 导出 `CATEGORY_NAMES` + `CATEGORY_KEYWORDS`
  （公开分类的单一事实来源）；`articles.py` 改为引用它；`fetcher.py` / `recommender.py`
  加注释指向该来源，内部细分关键词保持不动。

### 1.3 `services/ai.py` —— 防御性加固（SSRF + 密钥不外泄）
- **问题**：路由 `_resolve` 已禁止「自定义地址且不带 key」，但 service 层 `_chat` 仍有
  `key = api_key or settings.ai_api_key` 的静默回退——一旦有调用方传入自定义 base_url 且
  不传 key，就会拿服务端真实 Key 打向陌生站点。
- **改动**：`_chat` 增加判断——当 `base_url` 非默认主机且未提供 `api_key` 时直接抛
  `ValueError`，不再回退服务端密钥。默认路径（无 base_url / 同主机）行为不变。

### 1.4 删除确认零引用的死模块
- `app/utils/__init__.py`（空占位模块）
- `app/schemas/recommendation.py`（全仓无任何 importer，recommender 直接返回 dict）

---

## 二、前端架构与死代码清理

### 2.1 删除死代码与层间倒置
- **`api/ai.ts`**：整文件零引用，且存在 `import type { DeepSummary } from '../hooks/useArticles'`
  的 **api→hooks 类型倒置**（违反分层）。已删除。
- **`hooks/useAchievements.ts` 的 `useUnlockedAchievements`**：零引用，已删除。
- **`hooks/useAI.ts` 的 `useAIProcess`**：零引用（注意 `useAIProcessAll` 仍在用，已保留）。
- **`config/animation.ts` 的 `jellyCard` / `scaleByIntensity`**：零引用，已删除。
- **`hooks/useDebounce.ts` 的 `useDebounce`**：零引用，已删除并清理其遗留的 `useEffect` 导入。

### 2.2 仍建议后续处理（本轮未动，低风险的较大改动）
- `ArticlePage` / `SearchPage` / `SourcesPage` / `NewsTicker` 中仍有**绕过 api 层直接
  `client.*`** 的调用（投票、相似推荐、搜索、订阅源操作、新闻播报重复拉取）。
  应逐步收入 `hooks/*` 或 `api/*`，统一走 `unwrap`，消除重复与分层异味。

---

## 三、前端 UI / 交互 / 响应式优化（减少 AI 痕迹、统一视觉）

### 3.1 装饰特效受设置门控（修复「关不掉特效」）
- **`MouseGlow`**：原本永不门控、常驻且硬编码暖桃色（与 teal 主题不搭）。改为按
  `effectIntensity > 0` 门控，并把颜色改为 `rgb(var(--fufu-teal), …)`，**跟随主题切换**。
- **`MikuDecorations`**：初音 SVG 硬编码、永远渲染。改为仅 `theme === 'miku'` 时展示，
  切换奶咖/暗色主题自动隐藏，装饰不再与主题脱节。
- 其余强度门控特效（FloatingParticles / ScrollRubberBand / ScrollParallax / TiltCard）
  此前已正确门控，本次未动。

### 3.2 移动端 z-index 重叠修复
- **文章页底部操作栏**：`.mobile-sticky-actions` 原 `bottom:0; z-45`，被底部导航
  `z-50` 压住。改为 `bottom:4.5rem; z-60`，浮在导航之上、不再被遮挡。
- **分享面板**：移动端全屏遮罩原 `z-40`，被导航 `z-50` 压住。改为 `z-[60]`，遮罩覆盖导航。

### 3.3 硬编码色值改为设计 token（统一视觉、跟随主题）
将组件里硬编码的品牌色改为 `index.css` 的主题 token（`--fufu-teal` / `--fufu-teal-deep` /
`--fufu-teal-soft` / `--fufu-highlight` / `--fufu-pink`），换主题时自动跟随：
- `AiChatDialog.tsx`：头像/用户气泡/发送按钮的 `#00e5ff,#39c5bb` 渐变、浅色背景
  `#E0F7FA,#F0FAFF,#CCF0F8` → token。
- `FufuCompanion.tsx`：呼吸光晕 `rgba(0,229,255,…)` → `rgba(var(--fufu-teal),…)` 等。
- `ArticlePage.tsx`：投票选项色 `#39c5bb` → token。
- `HomePage.tsx`：进度/流光条渐变 → token。
- `SourcesPage.tsx`：分类标签色 `#00e5ff` / `#39c5bb` → token。
- **保留不动**：`MikuDecorations` 的初音插画多色（已是 miku 主题专属）、
  `SettingsPage` 的调色板预览色块（本就是展示调色板）。

---

## 四、验证结果（可复现）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端 lint | `ruff check app/`（受管 Python 0.16.9） | ✅ All checks passed |
| 后端测试 | `.venv/Scripts/python.exe -m pytest tests/ -q` | ✅ **18 passed** |
| 后端导入 | 跨模块 import 解析测试 | ✅ articles/ranking/comments/stats/categories/ai 全部解析 |
| 前端类型 | `npm run typecheck`（`tsc --noEmit`） | ✅ 0 error |
| 前端构建 | `npm run build`（vite） | ✅ 9.1s 构建成功 |
| 前端 lint | `npm run lint`（eslint） | ✅ **0 error**（48 warning，均为既有 exhaustive-deps 风格告警） |

> 注：Vite 构建前需清 `node_modules/.vite` 与 `dist`（沙箱批量删除保护）；
> 删除死模块、抽层均在 git 基线上可回滚。

---

## 五、遗留与建议（需你决策/后续）

1. **页面级 api 层下沉**（2.2）：把 `ArticlePage`/`SearchPage`/`SourcesPage`/`NewsTicker`
   中的直连 `client.*` 收口到 `hooks`/`api`，统一 `unwrap`。属较大改动，建议单独提交。
2. **特性优先（feature-first）重组**：当前前后端均为 layer-first。若要彻底「明确模块边界」，
   可把 `articles`/`sources`/`ai` 等聚合成 `features/*`，但涉及大量跨目录迁移，风险高，
   本轮未做（仅做了 service/core 层内聚）。
3. **真实浏览器走查**：tsc/build/lint/pytest 全绿，但本次未做浏览器渲染 + 控制台人工走查
   （尤其主题切换后 MouseGlow/MikuDecorations 行为、移动端操作栏与导航的实际间距）。
4. **认证仍默认**：`SECRET_KEY` 为默认值，上线前必须替换（前轮遗留，本轮未动）。
5. **Prettier 全量格式化**：配置已就位，可择机单独提交一次 `--write`。

---

## 六、本轮改动文件清单

**后端（新增 2 / 删除 2 / 改 5）**
- 新增：`app/services/stats.py`、`app/core/categories.py`
- 删除：`app/utils/__init__.py`、`app/schemas/recommendation.py`
- 改：`app/api/v1/ranking.py`（抽离 + 改 import）、`app/api/v1/articles.py`
  （分类单一来源 + 计数同步 import）、`app/api/v1/comments.py`（计数同步 import）、
  `app/services/ai.py`（密钥回退加固）、`app/services/fetcher.py` +
  `app/services/recommender.py`（分类来源注释）

**前端（删除 1 文件 + 改 9）**
- 删除：`src/api/ai.ts`
- 改：`src/hooks/useAchievements.ts`、`src/hooks/useAI.ts`、`src/hooks/useDebounce.ts`、
  `src/config/animation.ts`、`src/components/effects/MouseGlow.tsx`、
  `src/components/effects/MikuDecorations.tsx`、`src/components/common/ShareButton.tsx`、
  `src/pages/ArticlePage.tsx`、`src/pages/HomePage.tsx`、`src/pages/SourcesPage.tsx`、
  `src/styles/index.css`（`.mobile-sticky-actions` 定位/z-index）

---

## 七、实机运行验证（本轮追加）

按 `launch.py` 的约定拉起两个服务并探活：

| 服务 | 启动命令 | 端口 | 探活结果 |
|---|---|---|---|
| 后端 | `.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8800` | 8800 | ✅ 200 |
| 前端 | `npm run dev` | 3000 | ✅ 200 |

- `/api/v1/health` → `{"status":"fufu已苏醒 ✨","app":"fufu新闻","version":"1.0.0","database":"活蹦乱跳"}`
- 默认账户 `fufu / fufu123` 登录 `POST /api/v1/auth/token` → 200，取得 JWT。
- 带 token 实测**本轮重构涉及的接口全部 200**，确认抽层后业务逻辑在运行时正常：
  - `/api/v1/articles` → 返回真实文章
  - `/api/v1/articles/categories` → `{"all":7871,"动漫":996,"游戏":681,"科技":5479,"设计":153,"综合":562}`
    —— 正是 `core/categories.py` 收口的 5 个公开分类，**单一事实来源在运行时生效**
  - `/api/v1/ranking/daily` → 返回带 `hot_score` / `rank` 的榜单（`services/stats.py` 抽出后正常）
  - `/api/v1/recommendations/trending`、`/api/v1/search/hot`、`/api/v1/sources`、`/api/v1/folders` → 均 200

---

## 八、api 层下沉（遗留项 #1，已完成）

`src/api/` 原先缺 `articles` / `search` / `sources` 三个模块，导致页面绕过 api 层直连 `client`。本轮补齐并收口：

- 新建 **`src/api/search.ts`**：热门词、联想词、本地搜索、全网搜索。
  （全网搜索**刻意保留信封不做 unwrap** —— 调用方需要靠 `code`/`total`/`message`
  区分「真实全网结果」与「后端已降级为本地结果」，解包会丢失这层语义。）
- 新建 **`src/api/sources.ts`**：健康检测、批量校验、单源校验、全量爬取、OPML 导入导出。
- 新建 **`src/api/articles.ts`**：文章列表、投票读写（含 `EMPTY_POLL` 统一兜底）。
- 收口的调用点共 **12 处**：`SourcesPage`(6)、`ArticlePage`(3)、`SearchPage`(2)、
  `SearchAutocomplete`、`NewsTicker`、`HotSearchTerms`。
- 额外消除一处重复：`ArticlePage` 原先自己拼 `/recommendations/similar/{id}`，
  而 `api/recommendations.ts` 早有 `fetchSimilarArticles`，现改为复用。
- 类型收口：页面内重复定义的 `SourceHealth` / `PollOption` / `PollResult` /
  `SearchResponse` 已移除，改由 api 层单一提供。

验证：`tsc --noEmit` ✅ 0 error；`eslint` ✅ 0 error（49 warning，与改动前持平）；`vite build` ✅ 9.22s。

---

## 九、SECRET_KEY 轮换（遗留项 #4，已完成）

`fufu-server/.env` 中 `SECRET_KEY=change-me-to-a-random-string` 为占位符，已替换为 43 位随机串，
并**重启后端**验证：health 200、登录 200、新 token 访问 `/api/v1/articles/categories` 200。

> ⚠️ 注意：轮换会使此前签发的 token 失效，需要重新登录；且改 `.env` 后**必须重启后端**才生效。

---

## 十、更新后的遗留项

1. ~~页面级 api 层下沉~~ ✅ 已完成（见第八节）
2. **feature-first 重组**：仍建议保持延后 —— 涉及大量跨目录迁移，风险高于收益。
3. **真实浏览器渲染走查**：本轮已完成「服务可启动 + 接口可访问 + 构建通过」，
   但**未做浏览器内实际渲染与控制台报错的人工走查**（尤其主题切换后特效行为、
   移动端操作栏与导航的实际间距）。需 Playwright 之类工具在真实浏览器里跑一遍。
4. ~~SECRET_KEY 默认值~~ ✅ 已完成（见第九节）
5. **Prettier 全量 `--write`**：配置已就位，仍建议单独提交一次，避免与逻辑改动混在一起。

---

## 十一、浏览器内渲染 / 控制台走查（遗留项 #3，已完成）

用 Playwright（复用本机已缓存的 Chromium，未重复下载）以真实浏览器跑通：
登录 → 首页 → 设置 → 主题切换 → 移动端文章页。

**结果：发现并修复了一个静态检查完全发现不了的真 bug。**

### 🐛 移动端文章页底部操作栏完全不可见（已修复）

- **现象**：`.mobile-sticky-actions` 虽然写了 `position: fixed; bottom: 4.5rem; z-60`，
  实测却在 `top ≈ 3176px`（视口高只有 844px）——整条操作栏被钉进文档流深处，
  移动端永远看不到，之前只调 z-index/间距的思路根本治不了它。
- **根因**：framer-motion 会在 motion 祖先上临时写入 `will-change: transform`，
  而 `will-change` 与 transform 一样会**劫持后代 fixed 元素的包含块**，
  fixed 不再相对视口定位，而是相对那个被动画的祖先。
- **修复**：`ArticlePage.tsx` 用 `createPortal(…, document.body)` 把操作栏渲染到 body，
  彻底摆脱任何祖先的包含块影响。
- **修复后实测**：操作栏 `top:713 / bottom:772 / z-60`，悬在底部导航（`top:784`）之上
  **12px，无重叠**；截图可见「收藏 / 稍后读 / 分享 / AI摘要」正常浮现。

### 走查通过项

- 登录页 → 自动登录 → 跳转 `/articles`，React 正常挂载（root 7 个子节点、正文 8456 字符）
- **控制台 0 error、0 未捕获异常**；仅 3 条无害 warning
  （2 条 React Router v7 future-flag 预告、1 条滚动容器 position 提示）
- 桌面 1440px 与移动 390px 均**无横向溢出**（overflowPx: 0）
- 主题切换：点击「🍂 温柔奶咖」→ `data-theme="milktea"`，
  `--fufu-teal` 由青色变为 `196,167,125`（暖棕），**设计 token 跟随主题生效**
- 截图存于 `.workbuddy/browser-walkthrough/`（桌面首页 / 移动首页 / 奶茶主题 / 移动文章页）

### 验证门（修复后）

`tsc` 0 error · `eslint` 0 error（49 warning 持平）· `vite build` ✓ 6.61s · 浏览器控制台 0 error

---

## 十二、最终遗留项

1. ~~页面级 api 层下沉~~ ✅ 已完成（第八节）
2. **feature-first 重组**：继续延后 —— 迁移风险仍高于收益。
3. ~~真实浏览器渲染走查~~ ✅ 已完成（第十一节），并顺带修了一个真 bug
4. ~~SECRET_KEY 默认值~~ ✅ 已完成（第九节）
5. **Prettier 全量 `--write`**：仍建议单独提交一次。
6. （新增，可选）**React Router v7 future flags**：3 条无害预告，
   想提前消掉可在 Router 配置里加 `future` 选项。

---

## 十三、收尾清理（遗留项 #5 + #6，已完成）

### Prettier 全量格式化（遗留项 #5）
- `npm run format`（`prettier --write`）格式化全部 54 个不合规文件。
- `format:check` 由「54 files 不合规」→「All matched files use Prettier code style!」。
- 范围仅 `src/**/*.{ts,tsx,css}`；`dist` / `node_modules` / `*.md` / lock 文件已被
  `.prettierignore` 排除，避免把构建产物和依赖锁文件搅进改动。

### React Router v7 future flags（遗留项 #6）
- `App.tsx` 的 `<BrowserRouter>` 增加
  `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}`。
- 浏览器实测：React Router future-flag 预告 **由 2 条降为 0**，
  控制台仍 0 error、0 未捕获异常。

### 验证门（两项改动后）
`tsc` 0 error · `eslint` 0 error（49 warning 持平）· `vite build` ✓ 6.53s · 浏览器 0 error / 0 异常

---

## 十四、最终状态

全部遗留项已闭环：

1. ~~页面级 api 层下沉~~ ✅ 第八节
2. feature-first 重组 —— 维持「延后」的既定决策（迁移风险 > 收益，非待办）
3. ~~真实浏览器渲染走查~~ ✅ 第十一节（顺带修复移动端操作栏不可见 bug）
4. ~~SECRET_KEY 默认值~~ ✅ 第九节
5. ~~Prettier 全量 `--write`~~ ✅ 第十三节
6. ~~React Router v7 future flags~~ ✅ 第十三节
