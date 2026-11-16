import { useEffect, useMemo } from 'react';
import { ArrowLeft, ArrowRight, CalendarBlank, Fire, MagnifyingGlass, Tag } from '@phosphor-icons/react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { resetSEO, setArticleSEO } from '../lib/seo';
import { sanitizeHtml } from '../lib/sanitize';
import {
  getArticle,
  getHotArticles,
  queryArticles,
  type HotPeriod,
  type NewsSnapshot,
  type PublicArticle,
  type SinceFilter,
} from './data';
import {
  ArticleCard,
  ArticleVisual,
  EmptyState,
  HOT_PERIODS,
  HotSidebar,
  OriginalLink,
  Pagination,
  PublicShareButton,
  SearchForm,
  SectionHeading,
  TimeLabel,
  formatDate,
} from './components';

const SITE_DESCRIPTION = 'fufu新闻聚合科技、游戏、动漫等公开资讯，提供清晰的新闻列表、分类、热榜与站内搜索。';

function usePageSEO(title: string, description = SITE_DESCRIPTION) {
  useEffect(() => {
    setArticleSEO({ title, description, type: 'website', url: window.location.href });
    return () => resetSEO();
  }, [title, description]);
}

function pageNumber(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function sinceFilter(value: string | null): SinceFilter {
  return value === '24h' || value === '7d' || value === '30d' ? value : 'all';
}

function LeadStories({ articles }: { articles: PublicArticle[] }) {
  const [lead, ...secondary] = articles;
  if (!lead) return null;
  return (
    <section className="public-lead-grid" aria-label="重点新闻">
      <Link to={`/article/${lead.id}`} className="public-lead-story">
        <ArticleVisual article={lead} eager />
        <div className="public-lead-shade" />
        <div className="public-lead-content">
          <span className="public-lead-label">今日头条 · {lead.source_folder}</span>
          <h2>{lead.title}</h2>
          <p>{lead.summary}</p>
          <span className="public-lead-read">阅读全文 <ArrowRight size={18} /></span>
        </div>
      </Link>
      <div className="public-secondary-stories">
        {secondary.map((article, index) => (
          <article key={article.id} className="public-secondary-story">
            <Link to={`/article/${article.id}`} tabIndex={-1} aria-hidden="true">
              <ArticleVisual article={article} />
            </Link>
            <div>
              <span className="public-secondary-index">0{index + 2} / {article.source_folder}</span>
              <h3><Link to={`/article/${article.id}`}>{article.title}</Link></h3>
              <p>{article.summary}</p>
              <small>{article.source_name} · {formatDate(article.published_at)}</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function HomePage({ snapshot }: { snapshot: NewsSnapshot }) {
  const params = useParams();
  const category = params.category || 'all';
  const [searchParams, setSearchParams] = useSearchParams();
  const page = pageNumber(searchParams.get('page'));
  const since = sinceFilter(searchParams.get('since'));
  const result = useMemo(
    () => queryArticles(snapshot, { page, pageSize: 12, category, since }),
    [snapshot, page, category, since],
  );
  const isFrontPage = category === 'all';
  const showLead = isFrontPage && result.page === 1 && since === 'all';
  const leadArticles = showLead ? result.articles.slice(0, 3) : [];
  const listArticles = showLead ? result.articles.slice(3) : result.articles;
  const title = isFrontPage ? '首页' : `${category}频道`;
  usePageSEO(title, isFrontPage ? SITE_DESCRIPTION : `浏览 fufu新闻${category}频道的最新公开资讯。`);

  function updateFilters(nextPage: number, nextSince = since) {
    const next = new URLSearchParams();
    if (nextPage > 1) next.set('page', String(nextPage));
    if (nextSince !== 'all') next.set('since', nextSince);
    setSearchParams(next);
  }

  return (
    <>
      <section className={`public-page-intro ${isFrontPage ? 'is-home' : ''}`}>
        <div>
          <span className="public-eyebrow">{isFrontPage ? 'THE DAILY EDIT / 每日精选' : 'NEWS ARCHIVE / 分类档案'}</span>
          <h1>{isFrontPage ? <>新鲜事，<em>清晰抵达。</em></> : <>{category}<em> · 新闻</em></>}</h1>
        </div>
        <p>{isFrontPage ? '不追逐喧嚣，只呈现值得知道的变化。科技、游戏与更多世界动态，从这里开始。' : `当前收录 ${result.total} 篇${category}相关报道，按发布时间持续整理。`}</p>
      </section>

      {showLead && <LeadStories articles={leadArticles} />}

      <div className="public-content-grid">
        <main className="public-main-column">
          <div className="public-filter-bar">
            <div className="public-category-pills" aria-label="分类筛选">
              <Link to="/" className={isFrontPage ? 'is-active' : ''}>全部</Link>
              {snapshot.categories.map((item) => (
                <Link
                  key={item.name}
                  to={`/category/${encodeURIComponent(item.name)}`}
                  className={category === item.name ? 'is-active' : ''}
                >
                  {item.name}<span>{item.count}</span>
                </Link>
              ))}
            </div>
            <label className="public-since-filter">
              <CalendarBlank size={16} />
              <span className="sr-only">时间范围</span>
              <select value={since} onChange={(event) => updateFilters(1, event.target.value as SinceFilter)}>
                <option value="all">全部时间</option>
                <option value="24h">最近 24 小时</option>
                <option value="7d">最近 7 天</option>
                <option value="30d">最近 30 天</option>
              </select>
            </label>
          </div>

          {result.total === 0 ? (
            <EmptyState title="这里还没有新闻" description="试试其他分类或放宽时间范围。">
              <Link to="/" className="public-primary-link">返回全部新闻</Link>
            </EmptyState>
          ) : (
            <section className="public-news-section">
              <SectionHeading
                eyebrow={isFrontPage ? 'LATEST STORIES' : `${category.toUpperCase()} STORIES`}
                title={showLead ? '更多最新报道' : '最新报道'}
                action={<span className="public-result-count">共 {result.total} 篇</span>}
              />
              <div className="public-article-list">
                {listArticles.map((article) => <ArticleCard key={article.id} article={article} />)}
              </div>
              <Pagination page={result.page} totalPages={result.totalPages} onChange={(value) => updateFilters(value)} />
            </section>
          )}
        </main>
        <HotSidebar snapshot={snapshot} />
      </div>
    </>
  );
}

export function SearchPage({ snapshot }: { snapshot: NewsSnapshot }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = (searchParams.get('q') || '').trim();
  const page = pageNumber(searchParams.get('page'));
  const result = useMemo(
    () => queryArticles(snapshot, { query, page, pageSize: 10 }),
    [snapshot, query, page],
  );
  usePageSEO(query ? `搜索：${query}` : '站内搜索', `在 fufu新闻中检索${query || '标题、来源与标签'}。`);

  function goToPage(value: number) {
    const next = new URLSearchParams();
    if (query) next.set('q', query);
    if (value > 1) next.set('page', String(value));
    setSearchParams(next);
  }

  return (
    <>
      <section className="public-search-hero">
        <span className="public-eyebrow">SEARCH THE ARCHIVE / 全站检索</span>
        <h1>找到你关心的<em>那一条。</em></h1>
        <p>支持标题、正文、作者、来源和标签检索；多个关键词以空格分隔。</p>
        <SearchForm initialQuery={query} className="public-search-page-form" />
        {!query && snapshot.hot_keywords.length > 0 && (
          <div className="public-search-keywords">
            <span><Fire size={15} />热门搜索</span>
            {snapshot.hot_keywords.map((word) => (
              <Link key={word} to={`/search?q=${encodeURIComponent(word)}`}>{word}</Link>
            ))}
          </div>
        )}
      </section>

      <div className="public-content-grid">
        <main className="public-main-column">
          {!query ? (
            <EmptyState title="输入关键词，开始检索" description="例如“AI”“游戏”或某个新闻来源。">
              <div className="public-empty-categories">
                {snapshot.categories.map((item) => (
                  <Link key={item.name} to={`/category/${encodeURIComponent(item.name)}`}><Tag size={15} />{item.name}</Link>
                ))}
              </div>
            </EmptyState>
          ) : (
            <section className="public-news-section">
              <SectionHeading
                eyebrow="SEARCH RESULTS"
                title={`“${query}”的搜索结果`}
                action={<span className="public-result-count">找到 {result.total} 篇</span>}
              />
              {result.total ? (
                <>
                  <div className="public-article-list">
                    {result.articles.map((article) => <ArticleCard key={article.id} article={article} />)}
                  </div>
                  <Pagination page={result.page} totalPages={result.totalPages} onChange={goToPage} />
                </>
              ) : (
                <EmptyState title="没有找到匹配内容" description="检查关键词，或尝试更短、更通用的词语。">
                  <Link to="/search" className="public-primary-link">清空搜索</Link>
                </EmptyState>
              )}
            </section>
          )}
        </main>
        <HotSidebar snapshot={snapshot} />
      </div>
    </>
  );
}

export function HotPage({ snapshot }: { snapshot: NewsSnapshot }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedPeriod = searchParams.get('period');
  const period: HotPeriod = requestedPeriod === 'week' || requestedPeriod === 'month' ? requestedPeriod : 'day';
  const articles = useMemo(() => getHotArticles(snapshot, period), [snapshot, period]);
  usePageSEO('热门新闻榜', '浏览 fufu新闻 24 小时、本周和本月热门新闻。');

  return (
    <>
      <section className="public-hot-hero">
        <div>
          <span className="public-eyebrow">TRENDING NOW / 热门榜单</span>
          <h1>此刻，大家<em>都在读。</em></h1>
          <p>根据快照中的公开浏览统计与发布时间综合整理，不采集你的任何阅读行为。</p>
        </div>
        <span className="public-hot-hero-mark">HOT<br /><i>01</i></span>
      </section>
      <main className="public-hot-page-main">
        <div className="public-hot-page-tabs" role="tablist" aria-label="选择热榜">
          {HOT_PERIODS.map((item) => (
            <button
              type="button"
              role="tab"
              aria-selected={period === item.key}
              className={period === item.key ? 'is-active' : ''}
              key={item.key}
              onClick={() => setSearchParams(item.key === 'day' ? {} : { period: item.key })}
            >
              {item.label}热榜
            </button>
          ))}
        </div>
        <section>
          <SectionHeading eyebrow="TOP STORIES" title={HOT_PERIODS.find((item) => item.key === period)?.label + '热门文章'} />
          {articles.length ? (
            <div className="public-article-list public-ranked-list">
              {articles.map((article, index) => <ArticleCard key={article.id} article={article} rank={index + 1} />)}
            </div>
          ) : (
            <EmptyState title="暂无热榜数据" description="切换其他时间范围，或先浏览最新报道。">
              <Link to="/" className="public-primary-link">浏览最新新闻</Link>
            </EmptyState>
          )}
        </section>
      </main>
    </>
  );
}

export function ArticlePage({ snapshot }: { snapshot: NewsSnapshot }) {
  const params = useParams();
  const id = Number(params.id);
  const article = getArticle(snapshot, id);
  const content = useMemo(() => sanitizeHtml(article?.content), [article?.content]);
  const related = useMemo(() => {
    if (!article) return [];
    return queryArticles(snapshot, { category: article.source_folder, pageSize: 8 })
      .articles.filter((item) => item.id !== article.id)
      .slice(0, 3);
  }, [snapshot, article]);

  useEffect(() => {
    if (article) {
      setArticleSEO({
        title: article.title,
        description: article.summary || SITE_DESCRIPTION,
        image: article.image_url || undefined,
        url: window.location.href,
      });
    } else {
      setArticleSEO({ title: '文章未找到', description: '这篇新闻不在当前公开快照中。' });
    }
    return () => resetSEO();
  }, [article]);

  if (!article) {
    return (
      <main className="public-not-found">
        <span>404 / ARTICLE</span>
        <h1>这篇新闻不在当前快照里。</h1>
        <p>链接可能已失效，或文章尚未收录到本次公开版本。</p>
        <Link to="/"><ArrowLeft size={17} />返回新闻首页</Link>
      </main>
    );
  }

  return (
    <>
      <main className="public-article-page">
        <nav className="public-breadcrumbs" aria-label="面包屑">
          <Link to="/">首页</Link><span>/</span>
          <Link to={`/category/${encodeURIComponent(article.source_folder || '未分类')}`}>{article.source_folder}</Link><span>/</span>
          <span>正文</span>
        </nav>
        <article>
          <header className="public-article-header">
            <span className="public-article-category">{article.source_folder} / FUFU NEWS</span>
            <h1>{article.title}</h1>
            {article.summary && <p className="public-article-deck">{article.summary}</p>}
            <div className="public-article-byline">
              <div>
                <strong>{article.source_name}</strong>
                <span>{article.author ? `${article.author} · ` : ''}<TimeLabel value={article.published_at || article.fetched_at} /></span>
              </div>
              <div><PublicShareButton article={article} /><OriginalLink article={article} /></div>
            </div>
          </header>
          <ArticleVisual article={article} className="public-detail-visual" eager />
          <div className="public-article-body-wrap">
            <div className={`public-article-body ${content ? '' : 'is-summary-only'}`}>
              {content ? (
                <div dangerouslySetInnerHTML={{ __html: content }} />
              ) : (
                <>
                  <p>{article.summary}</p>
                  <aside className="public-summary-notice">
                    <strong>关于这篇快照</strong>
                    <p>当前公开版本仅收录了摘要。完整报道、图片与后续更新请前往原始来源阅读。</p>
                    <OriginalLink article={article} />
                  </aside>
                </>
              )}
            </div>
            <aside className="public-article-rail">
              <span>ARTICLE INFO</span>
              <dl>
                <div><dt>来源</dt><dd>{article.source_name}</dd></div>
                <div><dt>分类</dt><dd>{article.source_folder}</dd></div>
                <div><dt>发布</dt><dd>{formatDate(article.published_at || article.fetched_at, true)}</dd></div>
                {article.view_count > 0 && <div><dt>公开热度</dt><dd>{article.view_count} 次浏览</dd></div>}
              </dl>
              {article.tags.length > 0 && (
                <div className="public-article-tags">
                  {article.tags.map((tag) => <Link key={tag} to={`/search?q=${encodeURIComponent(tag)}`}>#{tag}</Link>)}
                </div>
              )}
            </aside>
          </div>
          <footer className="public-article-end">
            <span>— END —</span>
            <p>本文由「{article.source_name}」发布，fufu新闻仅作公开内容聚合与阅读整理。</p>
            <OriginalLink article={article} className="is-large" />
          </footer>
        </article>
      </main>
      {related.length > 0 && (
        <section className="public-related-section">
          <SectionHeading eyebrow="READ NEXT" title="继续阅读" />
          <div className="public-related-grid">
            {related.map((item) => (
              <article key={item.id}>
                <Link to={`/article/${item.id}`}><ArticleVisual article={item} /></Link>
                <span>{item.source_folder} · {formatDate(item.published_at)}</span>
                <h3><Link to={`/article/${item.id}`}>{item.title}</Link></h3>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

export function NotFoundPage() {
  usePageSEO('页面未找到');
  return (
    <main className="public-not-found">
      <span>404 / LOST IN NEWS</span>
      <MagnifyingGlass size={48} weight="duotone" />
      <h1>这一页，暂时没有新闻。</h1>
      <p>地址可能有误，也可能已经移动。回到首页继续阅读吧。</p>
      <Link to="/"><ArrowLeft size={17} />返回新闻首页</Link>
    </main>
  );
}
