import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import { unwrapList, unwrapOr } from '../api/unwrap';

export interface Source {
  id: number;
  name: string;
  url: string;
  source_type: 'rss' | 'web';
  fetch_interval: number;
  last_fetched_at: string | null;
  status: string;
  error_message: string | null;
  folder: string | null;
  created_at: string;
}

export function useSources() {
  return useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: async () => {
      const { data } = await client.get('/sources');
      // sources 是裸返回；unwrapList 恒等透传，同时保证异常时至少是 []
      return unwrapList<Source>(data);
    },
    placeholderData: [],
  });
}

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (source: Partial<Source>) => {
      const { data } = await client.post('/sources', source);
      return unwrapOr<Source>(data, null as unknown as Source);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] });
    },
  });
}

export function useUpdateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...data }: Partial<Source> & { id: number }) => {
      const { data: result } = await client.patch(`/sources/${id}`, data);
      return unwrapOr<Source>(result, null as unknown as Source);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] });
    },
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/sources/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] });
    },
  });
}

export function useFetchSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await client.post(`/sources/${id}/fetch`);
      return unwrapOr(data, null);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}
