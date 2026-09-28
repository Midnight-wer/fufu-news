import client from './client';

export interface CommentItem {
  id: number;
  content: string;
  username: string;
  created_at: string;
  likes_count: number;
  is_liked: boolean;
  replies: CommentItem[];
}

export interface CommentsResponse {
  items: CommentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface LikeResponse {
  liked: boolean;
  likes_count: number;
}

export const commentApi = {
  /** 获取文章评论列表，返回完整 API 响应 { code, data, message } */
  list: (articleId: number, page = 1, pageSize = 20, sort: 'latest' | 'hot' = 'latest') =>
    client
      .get(`/articles/${articleId}/comments`, {
        params: { page, page_size: pageSize, sort },
      })
      .then((r) => r.data),

  /** 创建顶级评论 */
  create: (articleId: number, content: string) =>
    client
      .post(`/articles/${articleId}/comments`, { content })
      .then((r) => r.data),

  /** 回复评论 */
  reply: (commentId: number, content: string) =>
    client.post(`/comments/${commentId}/reply`, { content }).then((r) => r.data),

  /** 删除评论 */
  delete: (commentId: number) =>
    client.delete(`/comments/${commentId}`).then((r) => r.data),

  /** 点赞/取消点赞 */
  like: (commentId: number) =>
    client.post(`/comments/${commentId}/like`).then((r) => r.data),
};
