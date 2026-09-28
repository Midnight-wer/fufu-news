/**
 * 预加载 Hook — 缓存优先渲染 + 后台静默更新
 *
 * 流程:
 * 1. 页面加载 → 优先读 IndexedDB → 立即渲染（秒开）
 * 2. 后台请求 API → 对比差异 → 合并更新
 * 3. 有新内容时显示刷新提示
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { cacheGet, cacheUpsert, type ArticleCache } from '../lib/cache-db';
import client from '../api/client';

interface PreloadState {
  articles: ArticleCache[];
  loading: boolean;
  fromCache: boolean;
  hasNew: boolean;
}

export function usePreload(pageSize = 30) {
  const [state, setState] = useState<PreloadState>({
    articles: [],
    loading: true,
    fromCache: true,
    hasNew: false,
  });
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    if (!navigator.onLine) {
      const cached = await cacheGet({ limit: pageSize });
      if (mountedRef.current) {
        setState({ articles: cached, loading: false, fromCache: true, hasNew: false });
      }
      return;
    }

    // 1. 先渲染缓存
    const cached = await cacheGet({ limit: pageSize });
    if (mountedRef.current && cached.length > 0) {
      setState({ articles: cached, loading: false, fromCache: true, hasNew: false });
    }

    // 2. 后台请求 API
    try {
      const { data } = await client.get('/articles', {
        params: { page: 1, page_size: pageSize, sort: 'latest', since: '7d' },
      });
      const apiArticles: ArticleCache[] = (data?.articles || []).map(
        (a: Record<string, unknown>) => ({
          title: String(a.title || ''),
          summary: String(a.summary || ''),
          source: String(a.source_name || a.source || ''),
          sourceId: Number(a.source_id || 0),
          category: String(a.source_folder || ''),
          url: String(a.url || `/articles/${a.id}`),
          publishedAt: String(a.published_at || a.fetched_at || ''),
          cachedAt: Date.now(),
          id: Number(a.id),
        }),
      );

      // 3. 对比差异
      const cachedUrls = new Set(cached.map((c) => c.url));
      const newArticles = apiArticles.filter((a) => !cachedUrls.has(a.url));
      const hasNew = newArticles.length > 0;

      // 4. 合并写入 IndexedDB
      if (apiArticles.length > 0) {
        await cacheUpsert(apiArticles);
      }

      if (mountedRef.current) {
        setState({
          articles: apiArticles,
          loading: false,
          fromCache: !hasNew && cached.length > 0,
          hasNew,
        });
      }
    } catch (err) {
      // API 失败 → 保持缓存数据（未登录或网络异常均正常降级）
      console.warn('[usePreload] API 请求失败，使用缓存:', err instanceof Error ? err.message : err)
      const fallback = await cacheGet({ limit: pageSize });
      if (mountedRef.current) {
        setState({ articles: fallback, loading: false, fromCache: true, hasNew: false });
      }
    }
  }, [pageSize]);

  useEffect(() => {
    mountedRef.current = true;
    refresh();
    return () => { mountedRef.current = false; };
  }, [refresh]);

  return { ...state, refresh };
}
