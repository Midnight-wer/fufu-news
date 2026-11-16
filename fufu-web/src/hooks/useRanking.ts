import { useQuery, useMutation } from '@tanstack/react-query';
import client from '../api/client';
import { unwrapOr } from '../api/unwrap';
import {
  fetchDailyRanking,
  fetchWeeklyRanking,
  fetchMonthlyRanking,
  recordHit,
  type RankingResponse,
} from '../api/ranking';

export type CategoryCounts = Record<string, number>;

const EMPTY_RANKING: RankingResponse = {
  items: [],
  updated_at: new Date().toISOString(),
};

export function useDailyRanking(limit = 10) {
  return useQuery<RankingResponse>({
    queryKey: ['ranking', 'daily', limit],
    queryFn: () => fetchDailyRanking(limit),
    placeholderData: EMPTY_RANKING,
    staleTime: 60_000,
  });
}

export function useWeeklyRanking(limit = 15) {
  return useQuery<RankingResponse>({
    queryKey: ['ranking', 'weekly', limit],
    queryFn: () => fetchWeeklyRanking(limit),
    placeholderData: EMPTY_RANKING,
    staleTime: 60_000,
  });
}

export function useMonthlyRanking(limit = 20) {
  return useQuery<RankingResponse>({
    queryKey: ['ranking', 'monthly', limit],
    queryFn: () => fetchMonthlyRanking(limit),
    placeholderData: EMPTY_RANKING,
    staleTime: 120_000,
  });
}

export function useRecordHit() {
  return useMutation({
    mutationFn: (articleId: number) => recordHit(articleId),
  });
}

/**
 * 各分类的真实文章数（全库聚合，不是当前页）。
 * 接口挂了就返回 undefined，页面上的数字徽标自动隐藏 —— 宁可不显示，也不显示错的。
 */
export function useCategories() {
  return useQuery<CategoryCounts | undefined>({
    queryKey: ['article-categories'],
    queryFn: async () => {
      const { data } = await client.get('/articles/categories');
      const v = unwrapOr<CategoryCounts | null>(data, null);
      return v ?? undefined;
    },
    staleTime: 120_000,
  });
}
