import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ArrowSquareOut,
  Clock,
  Fire,
  House,
  MagnifyingGlass,
  Newspaper,
  ShareNetwork,
} from '@phosphor-icons/react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { getHotArticles, type HotPeriod, type NewsSnapshot, type PublicArticle } from './data';

export const HOT_PERIODS: { key: HotPeriod; label: string }[] = [
  { key: 'day', label: '24 小时' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
];

export function formatDate(value: string | null, withTime = false): string {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间未知';
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
  }).format(date);
}

export function formatFullDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '每日新闻 · 清晰抵达';
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(date);
}

export function SearchForm({ initialQuery = '', className = '' }: { initialQuery?: string; className?: string }) {
  const inputId = useId();
  const [query, setQuery] = useState(initialQuery);
  const navigate = useNavigate();

  useEffect(() => setQuery(initialQuery), [initialQuery]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    navigate(value ? `/search?q=${encodeURIComponent(value)}` : '/search');
  }

  return (
    <form className={`public-search ${className}`} onSubmit={submit} role="search">
      <MagnifyingGlass size={19} aria-hidden="true" />
      <label className="sr-only" htmlFor={inputId}>搜索新闻</label>
      <input
        id={inputId}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="搜索标题、来源或标签"
        autoComplete="off"
      />
      <button type="submit" aria-label="提交搜索">搜索</button>
    </form>
  );
}

export function PublicHeader({ snapshot }: { snapshot: NewsSnapshot }) {
  return (
    <header className="public-header">
      <div className="public-utility">
        <div className="public-container public-utility-inner">
          <span>FUFU NEWS · PUBLIC EDITION</span>
          <span>{formatFullDate(snapshot.generated_at)}</span>
        </div>
      </div>
      <div className="public-container public-masthead">
        <Link to="/" className="public-brand" aria-label="fufu新闻首页">
          <span className="public-brand-overline">YOUR DAILY BRIEFING</span>
          <span className="public-brand-name">fufu新闻<i>.</i></span>
        </Link>
        <p className="public-brand-note">从信息洪流里，拣出真正值得阅读的事。</p>
        <SearchForm className="public-header-search" />
      </div>
      <div className="public-nav-wrap">
        <div className="public-container public-nav-inner">
          <nav className="public-nav" aria-label="主导航">
            <NavLink to="/" end><Newspaper size={17} />首页</NavLink>
            <NavLink to="/hot"><Fire size={17} />热榜</NavLink>
            <span className="public-nav-divider" />
            {snapshot.categories.map((category) => (
              <NavLink key={category.name} to={`/category/${encodeURIComponent(category.name)}`}>
                {category.name}
              </NavLink>
            ))}
          </nav>
          <Link to="/search" className="public-mobile-search-link" aria-label="搜索新闻">
            <MagnifyingGlass size={21} />
          </Link>
          <span className="public-nav-count">已收录 {snapshot.articles.length} 篇</span>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter({ snapshot }: { snapshot: NewsSnapshot }) {
  return (
    <footer className="public-footer">
      <div className="public-container public-footer-grid">
        <div>
          <Link to="/" className="public-footer-brand">fufu新闻.</Link>
          <p>甜系视觉，严肃阅读。聚合公开来源，保留每一篇报道的原始出处。</p>
        </div>
        <div className="public-footer-links">
          <strong>快速访问</strong>
          <Link to="/">最新新闻</Link>
          <Link to="/hot">热门榜单</Link>
          <Link to="/search">站内搜索</Link>
        </div>
        <div className="public-footer-meta">
          <strong>公开快照</strong>
          <span>更新于 {formatDate(snapshot.generated_at, true)}</span>
          <span>共 {snapshot.articles.length} 篇 · {snapshot.categories.length} 个分类</span>
          <span>只读资讯版，不收集阅读行为</span>
        </div>
      </div>
      <div className="public-container public-footer-bottom">
        <span>© 2026 fufu新闻</span>
        <span>MAKE NEWS FEEL CLEAR.</span>
      </div>
    </footer>
  );
}

export function MobileNavigation() {
  return (
    <nav className="public-mobile-nav" aria-label="移动端快捷导航">
      <NavLink to="/" end><House size={21} /><span>首页</span></NavLink>
      <NavLink to="/hot"><Fire size={21} /><span>热榜</span></NavLink>
      <NavLink to="/search"><MagnifyingGlass size={21} /><span>搜索</span></NavLink>
    </nav>
  );
}

export function ArticleVisual({
  article,
  className = '',
  eager = false,
}: {
  article: PublicArticle;
  className?: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [article.image_url]);

  if (!article.image_url || failed) {
    return (
      <div className={`public-visual-fallback ${className}`} aria-hidden="true">
        <span>FUFU / {article.source_folder}</span>
        <b>NEWS<br />IN FOCUS</b>
      </div>
    );
  }

  return (
    <div className={`public-article-visual ${className}`}>
      <img
        src={article.image_url}
        alt=""
        loading={eager ? 'eager' : 'lazy'}
        fetchPriority={eager ? 'high' : 'auto'}
        decoding="async"
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export function ArticleCard({ article, rank }: { article: PublicArticle; rank?: number }) {
  return (
    <article className="public-article-card">
      {rank !== undefined && <span className="public-article-rank">{String(rank).padStart(2, '0')}</span>}
      <Link to={`/article/${article.id}`} className="public-card-image-link" tabIndex={-1} aria-hidden="true">
        <ArticleVisual article={article} />
      </Link>
      <div className="public-card-body">
        <div className="public-card-meta">
          <Link to={`/category/${encodeURIComponent(article.source_folder || '未分类')}`}>{article.source_folder}</Link>
          <span>{formatDate(article.published_at || article.fetched_at)}</span>
        </div>
        <h3><Link to={`/article/${article.id}`}>{article.title}</Link></h3>
        {article.summary && <p>{article.summary}</p>}
        <div className="public-card-source">
          <span>{article.source_name}</span>
          <Link to={`/article/${article.id}`} aria-label={`阅读：${article.title}`}>
            阅读全文 <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </article>
  );
}

export function SectionHeading({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return (
    <div className="public-section-heading">
      <div><span>{eyebrow}</span><h2>{title}</h2></div>
      {action}
    </div>
  );
}

export function HotPanel({
  snapshot,
  period,
  onPeriodChange,
  compact = true,
}: {
  snapshot: NewsSnapshot;
  period: HotPeriod;
  onPeriodChange: (period: HotPeriod) => void;
  compact?: boolean;
}) {
  const articles = useMemo(() => getHotArticles(snapshot, period), [snapshot, period]);
  return (
    <section className={`public-hot-panel ${compact ? 'is-compact' : ''}`} aria-label="热门新闻">
      <div className="public-hot-title"><Fire size={22} weight="fill" /><h2>正在热议</h2><span>HOT</span></div>
      <div className="public-period-tabs" role="tablist" aria-label="热榜时间范围">
        {HOT_PERIODS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={period === item.key}
            className={period === item.key ? 'is-active' : ''}
            onClick={() => onPeriodChange(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="public-hot-list">
        {articles.slice(0, compact ? 6 : 10).map((article, index) => (
          <Link to={`/article/${article.id}`} key={article.id}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <div><strong>{article.title}</strong><small>{article.source_name} · {formatDate(article.published_at)}</small></div>
          </Link>
        ))}
      </div>
      {!articles.length && <p className="public-hot-empty">当前时间范围暂无热榜文章。</p>}
      {compact && <Link to="/hot" className="public-hot-more">查看完整热榜 <ArrowRight size={16} /></Link>}
    </section>
  );
}

export function HotSidebar({ snapshot }: { snapshot: NewsSnapshot }) {
  const [period, setPeriod] = useState<HotPeriod>('day');
  return (
    <aside className="public-sidebar">
      <HotPanel snapshot={snapshot} period={period} onPeriodChange={setPeriod} />
      <div className="public-sidebar-note">
        <span>ABOUT FUFU</span>
        <h3>让阅读回归内容本身。</h3>
        <p>无账户、无追踪、无干扰。每一篇文章都保留来源与原文入口。</p>
        <Link to="/search">找一篇新闻 <ArrowRight size={15} /></Link>
      </div>
    </aside>
  );
}

export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  const pages = Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
    const start = Math.min(Math.max(1, page - 2), Math.max(1, totalPages - 4));
    return start + index;
  });
  return (
    <nav className="public-pagination" aria-label="文章分页">
      <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="上一页">
        <ArrowLeft size={18} /><span>上一页</span>
      </button>
      <div>
        {pages.map((value) => (
          <button
            type="button"
            key={value}
            className={value === page ? 'is-active' : ''}
            aria-current={value === page ? 'page' : undefined}
            onClick={() => onChange(value)}
          >
            {value}
          </button>
        ))}
      </div>
      <button type="button" onClick={() => onChange(page + 1)} disabled={page >= totalPages} aria-label="下一页">
        <span>下一页</span><ArrowRight size={18} />
      </button>
    </nav>
  );
}

export function EmptyState({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return (
    <div className="public-empty-state">
      <Newspaper size={38} weight="duotone" />
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  );
}

export function PublicShareButton({ article }: { article: PublicArticle }) {
  const [status, setStatus] = useState('');
  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: article.title, text: article.summary || article.title, url });
        setStatus('已分享');
      } else {
        await navigator.clipboard.writeText(url);
        setStatus('链接已复制');
      }
    } catch (error) {
      if ((error as DOMException)?.name !== 'AbortError') setStatus('请复制地址栏链接');
    }
    window.setTimeout(() => setStatus(''), 2200);
  }
  return (
    <button type="button" className="public-share-button" onClick={share}>
      <ShareNetwork size={18} />{status || '分享本文'}
    </button>
  );
}

export function OriginalLink({ article, className = '' }: { article: PublicArticle; className?: string }) {
  if (!/^https?:\/\//i.test(article.url)) return null;
  return (
    <a className={`public-original-link ${className}`} href={article.url} target="_blank" rel="noopener noreferrer">
      访问原文 <ArrowSquareOut size={17} />
    </a>
  );
}

export function LoadingScreen() {
  return (
    <div className="public-state-screen" role="status">
      <span className="public-loading-mark">f.</span>
      <p>正在整理今日新闻…</p>
    </div>
  );
}

export function ErrorScreen({ message }: { message: string }) {
  return (
    <main className="public-state-screen" role="alert">
      <span className="public-loading-mark">!</span>
      <h1>新闻暂时没有送达</h1>
      <p>{message}</p>
      <button type="button" onClick={() => window.location.reload()}>重新加载</button>
    </main>
  );
}

export function TimeLabel({ value }: { value: string | null }) {
  return <span className="public-time-label"><Clock size={14} />{formatDate(value, true)}</span>;
}
