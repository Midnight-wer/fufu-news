import client from './client';

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

export async function fetchDailyRanking(limit = 10): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/daily', { params: { limit } });
  return data;
}

export async function fetchWeeklyRanking(limit = 15): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/weekly', { params: { limit } });
  return data;
}

export async function fetchMonthlyRanking(limit = 20): Promise<RankingResponse> {
  const { data } = await client.get('/ranking/monthly', { params: { limit } });
  return data;
}

export async function recordHit(articleId: number): Promise<void> {
  await client.post(`/ranking/hit/${articleId}`);
}
