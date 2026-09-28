/**
 * SEO 元标签工具
 * 用于动态设置 Open Graph / Twitter Card 等社交分享预览标签
 * 由于是 React SPA，使用 DOM 操作而非 react-helmet
 */

const META_PREFIX = 'fufu-seo-';

interface SEOMeta {
  title: string;
  description: string;
  image?: string;
  url?: string;
  type?: string;
  siteName?: string;
}

const DEFAULT_SITE_NAME = 'fufu新闻';
const DEFAULT_DESCRIPTION = '甜系二次元风格的新闻阅读器 — 初音未来主题 · RSS 聚合 · AI 摘要 · 深度解读';
const DEFAULT_IMAGE = ''; // 可替换为默认 OG 图 URL

/**
 * 设置或更新 <meta> 标签
 */
function setMeta(property: string, content: string, useName = false): void {
  const attr = useName ? 'name' : 'property';
  const selector = `meta[${attr}="${property}"]`;

  let el = document.querySelector(selector) as HTMLMetaElement | null;

  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, property);
    el.setAttribute('data-seo', META_PREFIX);
    document.head.appendChild(el);
  }

  el.setAttribute('content', content);
}

/**
 * 设置 Open Graph 标签
 */
function setOG(property: string, content: string): void {
  setMeta(`og:${property}`, content);
}

/**
 * 设置 Twitter Card 标签
 */
function setTwitter(name: string, content: string): void {
  setMeta(`twitter:${name}`, content, true);
}

/**
 * 设置页面标题
 */
export function setDocumentTitle(title: string): void {
  const fullTitle = title ? `${title} - ${DEFAULT_SITE_NAME}` : DEFAULT_SITE_NAME;
  document.title = fullTitle;
}

/**
 * 设置文章的 SEO 元数据（用于社交分享预览）
 */
export function setArticleSEO(meta: SEOMeta): void {
  const title = meta.title || DEFAULT_SITE_NAME;
  const description = meta.description || DEFAULT_DESCRIPTION;
  const url = meta.url || window.location.href;
  const image = meta.image || DEFAULT_IMAGE;
  const siteName = meta.siteName || DEFAULT_SITE_NAME;

  // 页面标题
  setDocumentTitle(title);

  // Open Graph
  setOG('title', title);
  setOG('description', description);
  setOG('url', url);
  setOG('type', meta.type || 'article');
  setOG('site_name', siteName);
  if (image) {
    setOG('image', image);
    setOG('image:width', '1200');
    setOG('image:height', '630');
  }

  // Twitter Card
  setTwitter('card', image ? 'summary_large_image' : 'summary');
  setTwitter('title', title);
  setTwitter('description', description);
  if (image) {
    setTwitter('image', image);
  }
}

/**
 * 重置为默认 SEO（用于首页等非文章页面）
 */
export function resetSEO(): void {
  setDocumentTitle('');
  setOG('title', DEFAULT_SITE_NAME);
  setOG('description', DEFAULT_DESCRIPTION);
  setOG('url', window.location.origin);
  setOG('type', 'website');
  setOG('site_name', DEFAULT_SITE_NAME);

  setTwitter('card', 'summary');
  setTwitter('title', DEFAULT_SITE_NAME);
  setTwitter('description', DEFAULT_DESCRIPTION);

  // 清除特定文章的图片
  setOG('image', DEFAULT_IMAGE);
  setTwitter('image', DEFAULT_IMAGE);
}

/**
 * 清理所有由 seo 工具创建的 meta 标签
 */
export function cleanupSEO(): void {
  const tags = document.querySelectorAll(`meta[data-seo="${META_PREFIX}"]`);
  tags.forEach((tag) => tag.remove());
}
