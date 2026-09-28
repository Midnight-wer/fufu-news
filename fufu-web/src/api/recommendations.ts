import client from './client';

export interface RecommendationItem {
  article_id: number;
  title: string;
  source_name: string;
  image_url?: string;
  published_at?: string;
  hot_score: number;
  reason: string;
  score: number;
  tags: string[];
}

export interface RecommendationResponse {
  items: RecommendationItem[];
  reasons: Record<number, string>;
}

const EMPTY_RECOMMENDATION_RESPONSE: RecommendationResponse = {
  items: [],
  reasons: {},
};

export { EMPTY_RECOMMENDATION_RESPONSE };

/**
 * 获取个性化推荐——基于用户阅读历史和兴趣。
 */
export async function fetchPersonalizedRecommendations(
  limit = 10,
  excludeIds: number[] = [],
): Promise<RecommendationResponse> {
  const params: Record<string, string | number> = { limit };
  if (excludeIds.length > 0) {
    params.exclude_ids = excludeIds.join(',');
  }
  const { data } = await client.get('/recommendations/personalized', { params });
  return unwrapRecommendationResponse(data);
}

/**
 * 获取与指定文章相似的其他文章。
 */
export async function fetchSimilarArticles(
  articleId: number,
  limit = 5,
): Promise<RecommendationResponse> {
  const { data } = await client.get(`/recommendations/similar/${articleId}`, {
    params: { limit },
  });
  return unwrapRecommendationResponse(data);
}

/**
 * 获取全局热门趋势文章。
 */
export async function fetchTrendingArticles(
  limit = 10,
  excludeIds: number[] = [],
): Promise<RecommendationResponse> {
  const params: Record<string, string | number> = { limit };
  if (excludeIds.length > 0) {
    params.exclude_ids = excludeIds.join(',');
  }
  const { data } = await client.get('/recommendations/trending', { params });
  return unwrapRecommendationResponse(data);
}

/**
 * 获取特定分类下的趋势文章。
 */
export async function fetchCategoryRecommendations(
  category: string,
  limit = 10,
): Promise<RecommendationResponse> {
  const { data } = await client.get(`/recommendations/category/${category}`, {
    params: { limit },
  });
  return unwrapRecommendationResponse(data);
}

/**
 * 从后端响应中解包推荐数据。
 * 后端包装格式: { code: 200, data: { items, reasons }, message: "ok" }
 */
function unwrapRecommendationResponse(response: any): RecommendationResponse {
  const inner = response?.data || response;
  if (inner && typeof inner === 'object' && Array.isArray(inner.items)) {
    return inner as RecommendationResponse;
  }
  return EMPTY_RECOMMENDATION_RESPONSE;
}
