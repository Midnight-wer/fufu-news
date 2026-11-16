import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import { unwrapOr, unwrapList } from '../api/unwrap';
import { cacheGet, cacheUpsert, type ArticleCache } from '../lib/cache-db';

/** 统一的空列表兜底 */
export { EMPTY_ARTICLES_RESPONSE };

export interface DeepSummary {
  one_liner?: string;
  key_data?: { label: string; value: string }[];
  core_points?: string[];
  background?: string;
  reactions?: { support?: string; oppose?: string; neutral?: string };
  generated_at?: string;
  _parse_error?: boolean;
}

export interface Article {
  id: number;
  source_id: number;
  title: string;
  url: string;
  content: string | null;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  fetched_at: string;
  image_url: string | null;
  is_read: boolean;
  is_favorite: boolean;
  is_later: boolean;
  read_progress: number;
  tags: string[];
  source_name?: string;
  source_folder?: string;
  deep_summary?: DeepSummary | null;
}

export interface ArticlesResponse {
  articles: Article[];
  total: number;
  page: number;
  page_size: number;
  /** 本次结果来自本地 IndexedDB 缓存（后端不可达时的降级） */
  fromCache?: boolean;
}

const EMPTY_ARTICLES_RESPONSE: ArticlesResponse = {
  articles: [],
  total: 0,
  page: 1,
  page_size: 20,
};

/**
 * 文章列表接口目前是**裸返回**（ArticleListResponse，不带 code/data 信封）。
 * unwrapOr 对裸对象是恒等变换，所以今天的行为与改造前完全一致；
 * 但它同时兼容「后端将来改成信封」的情况，届时前端无需再动。
 */
function normalizeArticles(raw: unknown): ArticlesResponse {
  const v = unwrapOr<unknown>(raw, null);
  if (v && typeof v === 'object' && !Array.isArray(v) && 'articles' in v) {
    const r = v as ArticlesResponse;
    return { ...r, articles: unwrapList<Article>(r.articles) };
  }
  return EMPTY_ARTICLES_RESPONSE;
}

/** 后端文章 → IndexedDB 缓存记录 */
function toCache(a: Article): ArticleCache | null {
  if (!a?.title) return null;
  return {
    id: a.id,
    title: a.title,
    summary: (a.summary || '').replace(/<[^>]+>/g, '').slice(0, 500),
    source: a.source_name || '',
    sourceId: a.source_id,
    category: a.source_folder || '',
    url: a.url || `/articles/${a.id}`,
    publishedAt: a.published_at || a.fetched_at || '',
    cachedAt: Date.now(),
  };
}

/**
 * 把一批文章写进 IndexedDB。
 * 这是"离线可读"能真正成立的前提 —— 之前 cache-db 写好了却没人调用，
 * 顶部横幅一直在宣称"仅展示缓存数据"，但缓存永远是空的。
 */
function persistToCache(list: Article[]): void {
  try {
    const rows = list.map(toCache).filter((x): x is ArticleCache => x !== null);
    if (rows.length > 0) void cacheUpsert(rows).catch(() => undefined);
  } catch {
    /* 缓存写入失败不影响主流程 */
  }
}

/** 后端不可达时的本地兜底 */
async function readFromCache(pageSize: number): Promise<ArticlesResponse> {
  try {
    const rows = await cacheGet({ limit: pageSize });
    const articles = rows.map((c, i) => ({
      id: c.id ?? -(i + 1),
      source_id: c.sourceId,
      title: c.title,
      url: c.url,
      content: null,
      summary: c.summary,
      author: null,
      published_at: c.publishedAt,
      fetched_at: c.publishedAt,
      image_url: null,
      is_read: false,
      is_favorite: false,
      is_later: false,
      read_progress: 0,
      tags: [],
      source_name: c.source,
      source_folder: c.category,
    })) as unknown as Article[];
    return {
      articles,
      total: articles.length,
      page: 1,
      page_size: pageSize,
      fromCache: true,
    };
  } catch {
    return { ...EMPTY_ARTICLES_RESPONSE, fromCache: true };
  }
}

export function useArticles(
  page = 1,
  pageSize = 20,
  sort: 'latest' | 'random' = 'random',
  since: string = '7d',
  category: string = 'all',
) {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', page, pageSize, sort, since, category],
    queryFn: async () => {
      try {
        const { data } = await client.get('/articles', {
          params: {
            page,
            page_size: pageSize,
            sort,
            since,
            // 'all' 由前端翻译为「不传」，交给后端省掉一次无谓的过滤
            ...(category && category !== 'all' ? { category } : {}),
          },
        });
        const res = normalizeArticles(data);
        persistToCache(res.articles);
        return res;
      } catch (err) {
        // 后端挂了 / 断网 → 用本地缓存顶上，让顶部的离线横幅说的是实话
        console.warn(
          '[useArticles] 接口失败，回退本地缓存:',
          err instanceof Error ? err.message : err,
        );
        return readFromCache(pageSize);
      }
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

export function useArticle(id: number | null) {
  return useQuery<Article>({
    queryKey: ['article', id],
    queryFn: async () => {
      const { data } = await client.get(`/articles/${id}`);
      return unwrapOr<Article>(data, null as unknown as Article);
    },
    enabled: !!id,
  });
}

export function useFavorites(page = 1, pageSize = 20) {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', 'favorites', page, pageSize],
    queryFn: async () => {
      const { data } = await client.get('/articles', {
        params: { is_favorite: true, page, page_size: pageSize },
      });
      return normalizeArticles(data);
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

export function useLater(page = 1, pageSize = 20) {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', 'later', page, pageSize],
    queryFn: async () => {
      const { data } = await client.get('/articles', {
        params: { is_later: true, page, page_size: pageSize },
      });
      return normalizeArticles(data);
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

/**
 * 更新阅读进度。
 * 后端 article.read_progress 字段一直存在且 PATCH 支持，
 * 但前端从没调用过，导致刷新后进度永远归零。
 */
export function useUpdateReadProgress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, progress }: { id: number; progress: number }) => {
      await client.patch(`/articles/${id}`, {
        read_progress: Math.max(0, Math.min(1, progress)),
      });
    },
    // 频繁调用，不在这里 invalidate，避免滚动时反复重拉列表
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article'] });
    },
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, value }: { id: number; value: boolean }) => {
      await client.patch(`/articles/${id}`, { is_favorite: value });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

export function useToggleLater() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, value }: { id: number; value: boolean }) => {
      await client.patch(`/articles/${id}`, { is_later: value });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await client.patch(`/articles/${id}`, { is_read: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}
