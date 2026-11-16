# fufu新闻完整网站与公网部署实施计划

## Context

现有项目已经是 React 18 + TypeScript + Vite + Tailwind 前端与 FastAPI + SQLite 后端，具备文章、分类、排行榜和搜索能力，数据库中亦有真实新闻。当前托管能力不支持 Python 动态服务，因此保留本地全栈版本，同时增加可独立部署的公网只读资讯版。公网版不依赖 localhost、API 密钥或外部后端，使用随站点发布的新闻快照；内容更新通过重新导出快照并重新部署完成。

## 实施步骤

1. **生成公开新闻数据**
   - 在 `fufu-server/scripts/export_static_snapshot.py` 使用 Python 标准库只读查询现有 SQLite，导出最新文章并补齐日/周/月热榜文章，限制快照体积。
   - 输出到 `fufu-web/public/data/news.json`，包含文章、分类统计、热榜、热搜词和生成时间；排除令牌、个人设置、收藏/已读状态、日志及 IP 等隐私数据。
   - 保留原始来源和原文链接；数据库为空时才使用明确的编辑示例内容，不伪造实时热点。

2. **增加独立公网只读外壳**
   - 在 `fufu-web/src/main.tsx` 根据 `VITE_STATIC_MODE` 加载公网入口，现有 `App.tsx` 与本地全栈行为保持不变。
   - 新增 `src/public/PublicApp.tsx`、数据适配模块及必要页面组件，只提供首页、文章详情、分类导航、热门推荐/热榜、搜索与 404，不加载登录、自检、AI、收藏、评论或阅读上报逻辑。
   - 数据适配层一次性加载并缓存快照，提供分页、分类/时间筛选、详情查询、关键词搜索和热榜数据；所有空数据、无效 ID、加载失败都有可读界面。
   - 复用 `Article` 类型、`sanitizeHtml`、`seo.ts`、Tailwind 设计令牌和通用分享组件，不复制本地版的账户与互动功能。

3. **完成专业响应式界面与 SEO**
   - 延续初音青绿/浅粉品牌，采用清晰的新闻编辑排版：顶部品牌与搜索入口、重点新闻、分类筛选、文章列表、热榜侧栏及移动端底部/抽屉导航。
   - 保证 375px、768px、1440px 布局，提供语义化标题、键盘焦点、触控目标、减少动态效果偏好及主流浏览器兼容目标。
   - 在 `index.html` 补齐 description、robots、canonical、Open Graph/Twitter 基础标签，使用现有 SEO 工具更新详情标题和摘要；增加 robots.txt 与基础 sitemap。
   - 公网静态模式使用 HashRouter，确保详情和搜索结果在静态托管上刷新、分享后仍可打开。

4. **生产构建与文档**
   - 在 `fufu-web/package.json` 增加快照导出说明对应的 `build:static`，通过 `.env.static` 启用静态模式；构建仍执行 TypeScript 检查，保留普通 `npm run build` 的原有用途。
   - 调整 Vite 生产构建为合理的浏览器目标并关闭公开产物 sourcemap，保持开发代理和现有构建目录不变。
   - 更新 `说明.txt`，写明本地全栈启动、公网静态构建、快照更新、部署访问地址、功能差异及常见问题，不写入任何真实密钥。

5. **部署公网静态站点**
   - 本地执行生产构建，将 `fufu-web/dist` 作为 StaticWeb 产物；检查 `index.html`、文件数量/体积以及不含 `.env`、凭证和 localhost 请求。
   - 使用部署插件 CLI 创建或复用与当前工作区匹配的 Site，按用户要求设置公开访问，创建 Deployment 并等待成功终态。
   - 刷新站点截图，调用部署卡片工具展示最终 Site；交付真实公网 URL、Site/Deployment ID 和可见性，不预先编造域名。

## 关键文件

- `fufu-web/src/main.tsx`：按构建模式选择入口。
- `fufu-web/src/public/PublicApp.tsx`、`src/public/data.ts`、`src/public/pages/*`：公网路由、数据查询与只读页面。
- `fufu-web/src/hooks/useArticles.ts`：仅复用现有 `Article` 类型，不改本地请求行为。
- `fufu-web/src/lib/sanitize.ts`、`src/lib/seo.ts`：复用正文消毒与动态元信息。
- `fufu-server/scripts/export_static_snapshot.py`：可重复执行的新闻快照导出。
- `fufu-web/public/data/news.json`、`robots.txt`、`sitemap.xml`：公开数据与搜索爬虫基础文件。
- `fufu-web/package.json`、`.env.static`、`vite.config.ts`、`index.html`：静态构建和基础 SEO。
- `说明.txt`：使用、构建、更新和部署说明。

## 验证

1. 运行快照导出，抽查文章字段、分类、榜单、正文消毒、来源链接及隐私字段排除。
2. 运行前端类型检查、ESLint、普通生产构建和静态生产构建；修复本次改动引入的问题。
3. 在不启动 FastAPI 的情况下预览静态产物，验证首页分页、全部分类、热榜切换、关键词/空搜索、详情、无效 ID、返回与分享链接；确认没有 `/api` 或 localhost 网络请求。
4. 用浏览器检查 375/768/1440px、键盘操作、控制台错误、页面标题和基础元标签，并回归本地全栈首页可启动。
5. 部署后访问公网首页及至少一个详情、分类和搜索链接，确认公开可访问、刷新正常、HTTPS 有效，再把真实地址写入 `说明.txt` 并交付。

## 交付边界

交付完整现有全栈源码、新增公网静态源码与新闻快照、生产构建、公网访问地址和使用说明。公网版是快照驱动的只读资讯站，不包含实时 RSS 抓取、账户、收藏、评论或 AI；这些能力继续由本地 FastAPI 全栈版提供。静态 SPA 具备基础 SEO 与社交元信息，但不承诺服务端渲染级别的独立详情页收录。
