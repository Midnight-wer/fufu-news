import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commentApi, type CommentsResponse } from '../api/comments';

const EMPTY_RESPONSE: CommentsResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
};

/** 获取文章评论列表 */
export function useComments(
  articleId: number | null,
  page = 1,
  pageSize = 20,
  sort: 'latest' | 'hot' = 'latest',
) {
  return useQuery<CommentsResponse>({
    queryKey: ['comments', articleId, page, pageSize, sort],
    queryFn: async () => {
      const res = await commentApi.list(articleId!, page, pageSize, sort);
      // API 返回 { code, data: { items, total, page, page_size }, message }
      return (res.data || EMPTY_RESPONSE) as CommentsResponse;
    },
    enabled: !!articleId,
    placeholderData: (prev) => prev ?? EMPTY_RESPONSE,
    staleTime: 30_000,
  });
}

/** 创建顶级评论 */
export function useCreateComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ articleId, content }: { articleId: number; content: string }) =>
      commentApi.create(articleId, content),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['comments', variables.articleId] });
    },
  });
}

/** 回复评论 */
export function useReplyComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ commentId, content }: { commentId: number; content: string }) =>
      commentApi.reply(commentId, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments'] });
    },
  });
}

/** 删除评论 */
export function useDeleteComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: number) => commentApi.delete(commentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments'] });
    },
  });
}

/** 点赞/取消点赞 */
export function useToggleLike() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: number) => commentApi.like(commentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments'] });
    },
  });
}
