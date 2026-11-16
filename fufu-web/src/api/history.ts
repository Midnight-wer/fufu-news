import client from './client';
import { unwrapOr } from './unwrap';

export interface HistoryItem {
  article_id: number;
  title: string;
  source_name: string | null;
  image_url: string | null;
  published_at: string | null;
  read_at: string;
  read_duration: number;
}

export interface HistoryResponse {
  items: HistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

const EMPTY_HISTORY_RESPONSE: HistoryResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
};

export { EMPTY_HISTORY_RESPONSE };

export async function fetchHistory(page = 1, pageSize = 20): Promise<HistoryResponse> {
  const { data } = await client.get('/history', {
    params: { page, page_size: pageSize },
  });
  // 后端是 { code, data, message } 信封，统一解包。
  // 保留形状校验：error() 返回时 data 是空数组，不能当成 HistoryResponse 用。
  const inner = unwrapOr<unknown>(data, null);
  return inner && typeof inner === 'object' && !Array.isArray(inner) && 'items' in inner
    ? (inner as HistoryResponse)
    : EMPTY_HISTORY_RESPONSE;
}

export async function recordRead(articleId: number, duration?: number): Promise<void> {
  const body: Record<string, number> = {};
  if (duration !== undefined && duration > 0) {
    body.read_duration = duration;
  }
  await client.post(`/history/${articleId}`, body);
}

export async function deleteHistoryItem(articleId: number): Promise<void> {
  await client.delete(`/history/${articleId}`);
}

export async function clearHistory(): Promise<void> {
  await client.delete('/history');
}
