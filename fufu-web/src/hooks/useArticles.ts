import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';

export interface DeepSummary {
  one_liner?: string;
  key_data?: { label: string; value: string }[];
  core_points?: string[];
  background?: string;
  reactions?: { support?: string; oppose?: string; neutral?: string };
  generated_at?: string;
  _parse_error?: boolean;
}

interface Article {
  id: number;
  source_id: number;
  title: string;
  url: string;
  content: string | null;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  fetched_at: string;
  image_url: string | null;
  is_read: boolean;
  is_favorite: boolean;
  is_later: boolean;
  read_progress: number;
  tags: string[];
  source_name?: string;
  source_folder?: string;
  deep_summary?: DeepSummary | null;
}

interface ArticlesResponse {
  articles: Article[];
  total: number;
  page: number;
  page_size: number;
}

const EMPTY_ARTICLES_RESPONSE: ArticlesResponse = {
  articles: [],
  total: 0,
  page: 1,
  page_size: 20,
};

export function useArticles(page = 1, pageSize = 20, sort: 'latest' | 'random' = 'random', since: string = '7d') {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', page, pageSize, sort, since],
    queryFn: async () => {
      const { data } = await client.get('/articles', {
        params: { page, page_size: pageSize, sort, since },
      });
      return data;
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

export function useArticle(id: number | null) {
  return useQuery<Article>({
    queryKey: ['article', id],
    queryFn: async () => {
      const { data } = await client.get(`/articles/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useFavorites(page = 1, pageSize = 20) {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', 'favorites', page, pageSize],
    queryFn: async () => {
      const { data } = await client.get('/articles', {
        params: { is_favorite: true, page, page_size: pageSize },
      });
      return data;
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

export function useLater(page = 1, pageSize = 20) {
  return useQuery<ArticlesResponse>({
    queryKey: ['articles', 'later', page, pageSize],
    queryFn: async () => {
      const { data } = await client.get('/articles', {
        params: { is_later: true, page, page_size: pageSize },
      });
      return data;
    },
    placeholderData: EMPTY_ARTICLES_RESPONSE,
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, value }: { id: number; value: boolean }) => {
      await client.patch(`/articles/${id}`, { is_favorite: value });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

export function useToggleLater() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, value }: { id: number; value: boolean }) => {
      await client.patch(`/articles/${id}`, { is_later: value });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await client.patch(`/articles/${id}`, { is_read: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
  });
}
