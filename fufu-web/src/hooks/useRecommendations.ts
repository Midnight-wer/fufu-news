import { useQuery } from '@tanstack/react-query';
import {
  fetchPersonalizedRecommendations,
  fetchSimilarArticles,
  fetchTrendingArticles,
  fetchCategoryRecommendations,
  EMPTY_RECOMMENDATION_RESPONSE,
  type RecommendationResponse,
} from '../api/recommendations';

/**
 * 个性化推荐 Hook。
 * 传入用户已见文章 ID 列表用于去重。
 */
export function usePersonalizedRecommendations(
  limit = 10,
  excludeIds: number[] = [],
  enabled = true,
) {
  return useQuery<RecommendationResponse>({
    queryKey: ['recommendations', 'personalized', limit, excludeIds.join(',')],
    queryFn: () => fetchPersonalizedRecommendations(limit, excludeIds),
    placeholderData: EMPTY_RECOMMENDATION_RESPONSE,
    staleTime: 5 * 60 * 1000, // 5 分钟内不重新请求
    enabled,
    retry: 1,
  });
}

/**
 * 相似文章推荐 Hook。
 */
export function useSimilarArticles(articleId: number, limit = 5) {
  return useQuery<RecommendationResponse>({
    queryKey: ['recommendations', 'similar', articleId, limit],
    queryFn: () => fetchSimilarArticles(articleId, limit),
    placeholderData: EMPTY_RECOMMENDATION_RESPONSE,
    staleTime: 5 * 60 * 1000,
    enabled: !!articleId,
    retry: 1,
  });
}

/**
 * 热门趋势 Hook。
 */
export function useTrendingArticles(limit = 10, excludeIds: number[] = []) {
  return useQuery<RecommendationResponse>({
    queryKey: ['recommendations', 'trending', limit, excludeIds.join(',')],
    queryFn: () => fetchTrendingArticles(limit, excludeIds),
    placeholderData: EMPTY_RECOMMENDATION_RESPONSE,
    staleTime: 3 * 60 * 1000, // 趋势数据 3 分钟刷新
    retry: 1,
  });
}

/**
 * 分类趋势推荐 Hook。
 */
export function useCategoryRecommendations(category: string, limit = 10) {
  return useQuery<RecommendationResponse>({
    queryKey: ['recommendations', 'category', category, limit],
    queryFn: () => fetchCategoryRecommendations(category, limit),
    placeholderData: EMPTY_RECOMMENDATION_RESPONSE,
    staleTime: 5 * 60 * 1000,
    enabled: !!category && category !== 'all',
    retry: 1,
  });
}
