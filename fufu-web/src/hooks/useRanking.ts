import { useQuery, useMutation } from '@tanstack/react-query';
import {
  fetchDailyRanking,
  fetchWeeklyRanking,
  fetchMonthlyRanking,
  recordHit,
  type RankingResponse,
} from '../api/ranking';

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
