import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchHistory,
  recordRead,
  deleteHistoryItem,
  clearHistory,
  EMPTY_HISTORY_RESPONSE,
  type HistoryResponse,
} from '../api/history';

export function useHistory(page = 1, pageSize = 20) {
  return useQuery<HistoryResponse>({
    queryKey: ['history', page, pageSize],
    queryFn: () => fetchHistory(page, pageSize),
    placeholderData: EMPTY_HISTORY_RESPONSE,
    staleTime: 30_000,
  });
}

export function useRecordRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ articleId, duration }: { articleId: number; duration?: number }) =>
      recordRead(articleId, duration),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useDeleteHistoryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (articleId: number) => deleteHistoryItem(articleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useClearHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['history'] });
    },
  });
}
