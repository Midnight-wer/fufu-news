import { useQuery } from '@tanstack/react-query';
import { fetchAggregatedView, type AggregatedData } from '../api/aggregation';

/**
 * 多源聚合对比 Hook
 *
 * 当阅读文章时，自动查找来自不同订阅源但报道同一话题的相关文章。
 * 仅在文章内容区域可见时启用查询，减少不必要的 API 调用。
 *
 * 参数:
 *   articleId: 主文章 ID
 *   enabled: 是否启用查询（默认 true）
 *
 * 返回:
 *   useQuery 结果，包含 data（AggregatedData）、isLoading、error 等
 */
export function useAggregation(articleId: number | null, enabled: boolean = true) {
  return useQuery<AggregatedData | null>({
    queryKey: ['aggregation', articleId],
    queryFn: async () => {
      const res = await fetchAggregatedView(articleId!, 4);
      if (res.code === 200 && res.data) {
        return res.data;
      }
      return null;
    },
    enabled: !!articleId && enabled,
    staleTime: 10 * 60 * 1000, // 10 分钟内不重新请求
    gcTime: 30 * 60 * 1000,
    retry: 1,
  });
}
