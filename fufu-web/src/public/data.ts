import type { Article } from '../hooks/useArticles';

export type PublicArticle = Pick<
  Article,
  | 'id'
  | 'source_id'
  | 'title'
  | 'url'
  | 'content'
  | 'summary'
  | 'author'
  | 'published_at'
  | 'fetched_at'
  | 'image_url'
  | 'tags'
  | 'source_name'
  | 'source_folder'
> & { view_count: number };

export type HotPeriod = 'day' | 'week' | 'month';
export type SinceFilter = 'all' | '24h' | '7d' | '30d';

export interface NewsSnapshot {
  version: number;
  generated_at: string;
  articles: PublicArticle[];
  categories: { name: string; count: number }[];
  hot: Record<HotPeriod, number[]>;
  hot_keywords: string[];
}

export interface ArticleQuery {
  page?: number;
  pageSize?: number;
  category?: string;
  since?: SinceFilter;
  query?: string;
}

export interface ArticleQueryResult {
  articles: PublicArticle[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

const EMPTY_SNAPSHOT: NewsSnapshot = {
  version: 1,
  generated_at: '',
  articles: [],
  categories: [],
  hot: { day: [], week: [], month: [] },
  hot_keywords: [],
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function nullableText(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}

function normalizeArticle(value: unknown): PublicArticle | null {
  const record = asRecord(value);
  if (!record) return null;
  const id = Number(record.id);
  if (!Number.isInteger(id) || id <= 0) return null;

  return {
    id,
    source_id: Number(record.source_id) || 0,
    title: asText(record.title) || '无标题',
    url: asText(record.url),
    content: nullableText(record.content),
    summary: nullableText(record.summary),
    author: nullableText(record.author),
    published_at: nullableText(record.published_at),
    fetched_at: asText(record.fetched_at),
    image_url: nullableText(record.image_url),
    tags: Array.isArray(record.tags)
      ? record.tags.filter((tag): tag is string => typeof tag === 'string')
      : [],
    source_name: asText(record.source_name) || '未知来源',
    source_folder: asText(record.source_folder) || '未分类',
    view_count: Math.max(0, Number(record.view_count) || 0),
  };
}

function normalizeHot(value: unknown): Record<HotPeriod, number[]> {
  const record = asRecord(value);
  const normalizeIds = (ids: unknown) =>
    Array.isArray(ids)
      ? ids
          .map(Number)
          .filter((id) => Number.isInteger(id) && id > 0)
      : [];
  return {
    day: normalizeIds(record?.day),
    week: normalizeIds(record?.week),
    month: normalizeIds(record?.month),
  };
}

export function normalizeSnapshot(value: unknown): NewsSnapshot {
  const record = asRecord(value);
  if (!record) return { ...EMPTY_SNAPSHOT, hot: { ...EMPTY_SNAPSHOT.hot } };

  return {
    version: Number(record.version) || 1,
    generated_at: asText(record.generated_at),
    articles: Array.isArray(record.articles)
      ? record.articles
          .map(normalizeArticle)
          .filter((article): article is PublicArticle => article !== null)
      : [],
    categories: Array.isArray(record.categories)
      ? record.categories.flatMap((category) => {
          const item = asRecord(category);
          const name = asText(item?.name);
          return name ? [{ name, count: Math.max(0, Number(item?.count) || 0) }] : [];
        })
      : [],
    hot: normalizeHot(record.hot),
    hot_keywords: Array.isArray(record.hot_keywords)
      ? record.hot_keywords.filter((word): word is string => typeof word === 'string')
      : [],
  };
}

function articleTime(article: PublicArticle): number {
  const time = Date.parse(article.published_at || article.fetched_at);
  return Number.isFinite(time) ? time : 0;
}

function byNewest(a: PublicArticle, b: PublicArticle): number {
  return articleTime(b) - articleTime(a) || b.id - a.id;
}

function normalizeSearchText(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase();
}

export function queryArticles(
  snapshot: NewsSnapshot,
  options: ArticleQuery = {},
): ArticleQueryResult {
  const pageSize = Math.min(50, Math.max(1, Math.trunc(options.pageSize || 12)));
  const category = options.category && options.category !== 'all' ? options.category : '';
  const query = normalizeSearchText(options.query?.trim() || '');
  const terms = query.split(/\s+/).filter(Boolean);
  const since = options.since || 'all';
  const generatedTime = Date.parse(snapshot.generated_at);
  const latestTime = Math.max(0, ...snapshot.articles.map(articleTime));
  const referenceTime = Number.isFinite(generatedTime) ? generatedTime : latestTime;
  const durations: Record<Exclude<SinceFilter, 'all'>, number> = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
  };
  const cutoff = since === 'all' ? 0 : referenceTime - durations[since];

  const articles = snapshot.articles
    .filter((article) => !category || article.source_folder === category)
    .filter((article) => since === 'all' || articleTime(article) >= cutoff)
    .filter((article) => {
      if (!terms.length) return true;
      const haystack = normalizeSearchText(
        [
          article.title,
          article.summary || '',
          article.content?.replace(/<[^>]*>/g, ' ') || '',
          article.author || '',
          article.source_name || '',
          article.source_folder || '',
          ...article.tags,
        ].join(' '),
      );
      return terms.every((term) => haystack.includes(term));
    })
    .sort(byNewest);

  const total = articles.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const requestedPage = Number.isFinite(options.page) ? Math.trunc(options.page!) : 1;
  const page = Math.min(totalPages, Math.max(1, requestedPage));
  const start = (page - 1) * pageSize;

  return {
    articles: articles.slice(start, start + pageSize),
    total,
    page,
    pageSize,
    totalPages,
  };
}

export function getArticle(snapshot: NewsSnapshot, id: number): PublicArticle | undefined {
  if (!Number.isInteger(id) || id <= 0) return undefined;
  return snapshot.articles.find((article) => article.id === id);
}

export function getHotArticles(
  snapshot: NewsSnapshot,
  period: HotPeriod,
): PublicArticle[] {
  return snapshot.hot[period]
    .map((id) => getArticle(snapshot, id))
    .filter((article): article is PublicArticle => article !== undefined);
}

let snapshotPromise: Promise<NewsSnapshot> | null = null;

/** 快照只加载一次；失败时允许下一次操作重试。 */
export function loadNewsSnapshot(): Promise<NewsSnapshot> {
  if (!snapshotPromise) {
    const baseUrl = import.meta.env.BASE_URL || '/';
    snapshotPromise = fetch(`${baseUrl}data/news.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`新闻快照加载失败（${response.status}）`);
        return response.json() as Promise<unknown>;
      })
      .then(normalizeSnapshot)
      .catch((error: unknown) => {
        snapshotPromise = null;
        throw error;
      });
  }
  return snapshotPromise;
}
