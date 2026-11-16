import client from './client';
import { unwrap } from './unwrap';

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

// 说明：后端 comments 端点返回 { code, data, message } 信封。
// 原先这里直接 `.then((r) => r.data)` 把整个信封交给调用方，
// useComments 又各自写了一份 `res.data || EMPTY` 解包，逻辑分散且容易漏。
// 现在统一在 api 层解包一次（unwrap 幂等，调用方再解一次也不会出错）。

export const commentApi = {
  /** 获取文章评论列表 */
  list: (articleId: number, page = 1, pageSize = 20, sort: 'latest' | 'hot' = 'latest') =>
    client
      .get(`/articles/${articleId}/comments`, {
        params: { page, page_size: pageSize, sort },
      })
      .then((r) => unwrap<CommentsResponse>(r.data)),

  /** 创建顶级评论 */
  create: (articleId: number, content: string) =>
    client.post(`/articles/${articleId}/comments`, { content }).then((r) => unwrap(r.data)),

  /** 回复评论 */
  reply: (commentId: number, content: string) =>
    client.post(`/comments/${commentId}/reply`, { content }).then((r) => unwrap(r.data)),

  /** 删除评论 */
  delete: (commentId: number) =>
    client.delete(`/comments/${commentId}`).then((r) => unwrap(r.data)),

  /** 点赞/取消点赞 */
  like: (commentId: number) =>
    client.post(`/comments/${commentId}/like`).then((r) => unwrap<LikeResponse>(r.data)),
};
