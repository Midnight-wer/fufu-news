import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';

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
      return data ?? [];
    },
    placeholderData: [],
  });
}

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (source: Partial<Source>) => {
      const { data } = await client.post('/sources', source);
      return data;
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
      return result;
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
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}
