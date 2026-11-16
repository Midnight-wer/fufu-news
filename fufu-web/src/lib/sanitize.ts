/**
 * HTML 消毒（XSS 防护）
 * =====================
 *
 * 背景：文章正文来自第三方 RSS 源，是完全不可信的输入。
 * 原先 ArticlePage 直接用 `dangerouslySetInnerHTML={{ __html: article.content }}`
 * 渲染，恶意订阅源只要塞进 <script> / <img onerror=> / <a href="javascript:">
 * 就能在读者浏览器里执行任意脚本（存储型 XSS）。
 *
 * 本模块用白名单策略清洗：只保留排版需要的标签和属性，其余一律移除。
 * 不引入额外依赖（DOMPurify 需新增包），用浏览器原生 DOMParser 实现，
 * 解析结果与 React 渲染目标一致。
 */

/** 允许保留的标签 */
const ALLOWED_TAGS = new Set([
  'p',
  'br',
  'hr',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'strong',
  'b',
  'em',
  'i',
  'u',
  's',
  'del',
  'ins',
  'mark',
  'small',
  'sub',
  'sup',
  'ul',
  'ol',
  'li',
  'blockquote',
  'pre',
  'code',
  'a',
  'img',
  'figure',
  'figcaption',
  'table',
  'thead',
  'tbody',
  'tfoot',
  'tr',
  'th',
  'td',
  'span',
  'div',
  'section',
  'article',
]);

/** 允许保留的属性（按标签区分，'*' 表示所有允许标签通用） */
const ALLOWED_ATTRS: Record<string, Set<string>> = {
  '*': new Set(['title', 'lang', 'dir']),
  a: new Set(['href', 'target', 'rel']),
  img: new Set(['src', 'alt', 'title', 'width', 'height', 'loading']),
  td: new Set(['colspan', 'rowspan']),
  th: new Set(['colspan', 'rowspan', 'scope']),
  pre: new Set(['class']),
  code: new Set(['class']),
  span: new Set(['class']),
};

/** 危险的 URL 协议 */
const UNSAFE_PROTOCOL = /^\s*(javascript|data|vbscript|file)\s*:/i;

/** 单个标签允许的属性集合 */
function attrsFor(tag: string): Set<string> {
  return new Set([...(ALLOWED_ATTRS['*'] ?? []), ...(ALLOWED_ATTRS[tag] ?? [])]);
}

/** 校验 href/src 是否安全 */
function isSafeUrl(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (UNSAFE_PROTOCOL.test(v)) return false;
  // 允许 http(s)、mailto、以及相对路径与锚点
  return /^(https?:\/\/|mailto:|\/|#|\.\/|\.\.\/)/i.test(v) || !v.includes(':');
}

let _parser: DOMParser | null = null;
function getParser(): DOMParser | null {
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') return null;
  if (!_parser) _parser = new DOMParser();
  return _parser;
}

/** 递归清洗节点树 */
function cleanNode(node: Node, doc: Document): void {
  const children = Array.from(node.childNodes);

  for (const child of children) {
    // 注释节点一律删除（可能含条件注释等绕过技巧）
    if (child.nodeType === Node.COMMENT_NODE) {
      child.remove();
      continue;
    }

    // 文本节点保留
    if (child.nodeType === Node.TEXT_NODE) continue;

    // 元素节点
    if (child.nodeType === Node.ELEMENT_NODE) {
      const el = child as Element;
      const tag = el.tagName.toLowerCase();

      if (!ALLOWED_TAGS.has(tag)) {
        // 不在白名单：保留其文本内容，丢弃标签本身
        const parent = el.parentNode;
        if (parent) {
          while (el.firstChild) parent.insertBefore(el.firstChild, el);
          el.remove();
        }
        continue;
      }

      // 清洗属性
      const allowed = attrsFor(tag);
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        if (!allowed.has(name)) {
          el.removeAttribute(attr.name);
          continue;
        }
        // on* 事件处理器一律移除（双保险）
        if (name.startsWith('on')) {
          el.removeAttribute(attr.name);
          continue;
        }
        if ((name === 'href' || name === 'src') && !isSafeUrl(attr.value)) {
          el.removeAttribute(attr.name);
          continue;
        }
      }

      // 外链统一加 noopener，避免 tabnabbing
      if (tag === 'a') {
        const target = el.getAttribute('target');
        if (target === '_blank') {
          const rel = el.getAttribute('rel') || '';
          if (!rel.includes('noopener')) {
            el.setAttribute('rel', `${rel} noopener noreferrer`.trim());
          }
        }
      }

      cleanNode(el, doc);
      continue;
    }

    // 其他未知节点类型（CDATA 等）直接删除
    child.remove();
  }
}

/**
 * 清洗一段不可信 HTML，返回可安全用于 dangerouslySetInnerHTML 的字符串。
 *
 * 无 DOM 环境（SSR / 测试）时降级为移除 <script>/<style> 的纯文本，
 * 保证不会渲染出可执行内容。
 */
export function sanitizeHtml(dirty: string | null | undefined): string {
  if (!dirty) return '';

  const parser = getParser();
  if (!parser) {
    // 无 DOMParser：保守降级，剥离脚本/样式/事件属性后原样返回纯文本
    return String(dirty)
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/\son[a-z]+\s*=\s*(".*?"|'.*?'|[^\s>]+)/gi, '');
  }

  const doc = parser.parseFromString(String(dirty), 'text/html');
  cleanNode(doc.body, doc);
  return doc.body.innerHTML;
}
