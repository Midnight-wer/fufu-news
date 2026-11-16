import client from './client';
import { unwrapList } from './unwrap';

/**
 * 搜索相关接口集合（热门词 / 联想词 / 本地搜索 / 全网搜索）。
 *
 * 收敛目的：原先 SearchPage / HotSearchTerms / SearchAutocomplete 各自
 * 直接 `client.get('/search/...')`，URL 与解包逻辑散落在组件里。
 * 现在统一由此模块持有路径，组件只依赖语义化函数。
 */

/** 热门搜索词。后端返回信封 { code, data: string[] }，裸数组也能兼容。 */
export async function fetchHotSearchTerms(limit = 8): Promise<string[]> {
  const { data } = await client.get('/search/hot', { params: { limit } });
  return unwrapList<string>(data);
}

/**
 * 搜索联想词。
 * 返回结构由调用方决定（不同版本后端返回字符串数组或对象数组），故用泛型，
 * 避免把组件内的 Suggestion 类型搬来搬去造成重复定义。
 */
export async function fetchSearchSuggestions<T = unknown>(
  q: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<T[]> {
  const { data } = await client.get('/search/suggest', {
    params: { q, limit },
    signal,
  });
  return unwrapList<T>(data);
}

/** 本地全文搜索（/articles/search）。同样用泛型，保持调用方既有类型不变。 */
export async function searchArticles<T = unknown>(q: string): Promise<T[]> {
  const { data } = await client.get('/articles/search', { params: { q } });
  return unwrapList<T>(data);
}

/**
 * 全网搜索响应信封。
 *
 * 注意：这里**刻意不做 unwrap** —— 调用方需要读取 code / total / message
 * 来区分「拿到真实全网结果」与「后端已降级为本地结果」两种情况，
 * 一旦解包就会丢失这层语义。
 */
export interface WebSearchEnvelope<T> {
  code: number;
  data: T[];
  total: number;
  message: string;
  source?: string;
  ddgs_available?: boolean;
  ai_pending?: boolean;
}

export async function searchWeb<T>(
  keyword: string,
  maxResults = 20,
  signal?: AbortSignal,
): Promise<WebSearchEnvelope<T>> {
  const { data } = await client.post(
    '/search/web',
    { keyword, max_results: maxResults },
    { signal, timeout: 35_000 },
  );
  return (data ?? { code: 200, data: [], total: 0, message: '' }) as WebSearchEnvelope<T>;
}
