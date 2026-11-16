import client from './client';
import { unwrapOr } from './unwrap';

export interface RankingItem {
  rank: number;
  article_id: number;
  title: string;
  source_name: string;
  image_url?: string;
  hot_score: number;
  view_count: number;
  comment_count: number;
  collect_count: number;
  trend?: 'up' | 'down' | 'same' | 'new';
  hot_label?: '爆' | '热' | '新';
}

export interface RankingResponse {
  items: RankingItem[];
  updated_at: string;
}

/** 空榜兜底：后端异常或暂无数据时用，避免页面拿到 undefined 后崩溃 */
export const EMPTY_RANKING: RankingResponse = {
  items: [],
  updated_at: new Date().toISOString(),
};

/**
 * 获取排行榜。
 *
 * 修复（P0 — 热榜永远空白）：
 * 原先这里直接 `return data`，而后端 `success()` 返回的是
 * `{ code: 200, data: { items, updated_at }, message: "ok" }` 信封，
 * 于是拿到的 RankingResponse.items 恒为 undefined，
 * 排行榜页与首页「今日热榜」小部件永远显示不出来。
 * 现在统一走 unwrap 解包。
 */
export async function fetchDailyRanking(limit = 10): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/daily', { params: { limit } });
  return unwrapOr<RankingResponse>(data, EMPTY_RANKING);
}

export async function fetchWeeklyRanking(limit = 15): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/weekly', { params: { limit } });
  return unwrapOr<RankingResponse>(data, EMPTY_RANKING);
}

export async function fetchMonthlyRanking(limit = 20): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/monthly', { params: { limit } });
  return unwrapOr<RankingResponse>(data, EMPTY_RANKING);
}

export async function recordHit(articleId: number): Promise<void> {
  await client.post(`/ranking/hit/${articleId}`);
}
