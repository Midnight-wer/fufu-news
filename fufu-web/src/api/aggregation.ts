import client from './client';

export interface RelatedArticleBrief {
  id: number;
  title: string;
  source_id: number;
  source_name: string | null;
  summary: string | null;
  published_at: string | null;
  image_url: string | null;
  url: string;
  tags: string[];
}

export interface RelatedSourceItem {
  article: RelatedArticleBrief;
  perspective: string;
  overlap_keywords: string[];
  similarity_score: number;
}

export interface MainArticleData {
  id: number;
  source_id: number;
  title: string;
  url: string;
  content: string | null;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  fetched_at: string | null;
  image_url: string | null;
  is_read: boolean;
  is_favorite: boolean;
  is_later: boolean;
  read_progress: number;
  tags: string[];
  deep_summary: any;
  source_name: string | null;
  source_folder: string | null;
}

export interface AggregatedData {
  main_article: MainArticleData | null;
  related_sources: RelatedSourceItem[];
  common_points: string[];
  different_points: string[];
}

export interface AggregatedResponse {
  code: number;
  data: AggregatedData | null;
  message: string;
}

export async function fetchAggregatedView(
  articleId: number,
  limit: number = 4,
): Promise<AggregatedResponse> {
  const { data } = await client.get<AggregatedResponse>(`/articles/${articleId}/aggregated`, {
    params: { limit },
  });
  return data;
}
