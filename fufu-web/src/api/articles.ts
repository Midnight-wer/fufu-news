import client from './client';
import { unwrapOr } from './unwrap';

/**
 * 文章相关接口集合（列表 / 投票）。
 *
 * 收敛目的：ArticlePage 内联了投票的读写、NewsTicker 内联了列表拉取，
 * 现在统一由此模块持有路径与解包逻辑。
 */

export type PollOption = 'support' | 'oppose' | 'neutral';

export interface PollResult {
  support: number;
  oppose: number;
  neutral: number;
  total: number;
  my_vote: PollOption | null;
}

/** 空投票结果：接口无数据时的统一兜底，避免页面出现 NaN。 */
export const EMPTY_POLL: PollResult = {
  support: 0,
  oppose: 0,
  neutral: 0,
  total: 0,
  my_vote: null,
};

/**
 * 拉取文章列表。
 * 用泛型是因为不同调用方对返回体的关注点不同（列表页关心分页字段、
 * NewsTicker 只关心 articles），把具体形状交给调用方声明。
 */
export async function fetchArticles<T = unknown>(
  params: Record<string, string | number> = {},
): Promise<T | null> {
  const { data } = await client.get('/articles', { params });
  return unwrapOr<T | null>(data, null);
}

/** 读取某篇文章的投票结果（一人一票、可改票/撤票）。 */
export async function fetchPoll(articleId: number): Promise<PollResult> {
  const { data } = await client.get(`/articles/${articleId}/poll`);
  return unwrapOr<PollResult>(data, EMPTY_POLL);
}

/**
 * 提交/修改投票。option 传 null 表示撤票。
 * 兜底里带上 my_vote: option，让界面在响应异常时也能反映用户刚做的选择。
 */
export async function submitPoll(
  articleId: number,
  option: PollOption | null,
): Promise<PollResult> {
  const { data } = await client.post(`/articles/${articleId}/poll`, { option });
  return unwrapOr<PollResult>(data, { ...EMPTY_POLL, my_vote: option });
}
