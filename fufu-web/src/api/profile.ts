import client from './client';
import { unwrapOr } from './unwrap';

/**
 * 兴趣画像相关接口（自学习机制的只读展示）。
 *
 * 后端端点：
 * - GET  /profile/interests  → 当前用户兴趣画像（标签 + 权重）
 * - DELETE /profile/interests → 重置画像
 */

export interface InterestItem {
  tag: string;
  score: number;
}

export interface InterestsResponse {
  interests: InterestItem[];
  count: number;
}

const EMPTY_INTERESTS: InterestsResponse = { interests: [], count: 0 };

export async function fetchInterests(): Promise<InterestsResponse> {
  const { data } = await client.get('/profile/interests');
  const inner = unwrapOr<unknown>(data, null);
  if (inner && typeof inner === 'object' && !Array.isArray(inner) && 'interests' in inner) {
    const r = inner as InterestsResponse;
    return Array.isArray(r.interests) ? r : EMPTY_INTERESTS;
  }
  return EMPTY_INTERESTS;
}

export async function resetInterests(): Promise<number> {
  const { data } = await client.delete('/profile/interests');
  const inner = unwrapOr<{ deleted?: number } | null>(data, null);
  return inner && typeof inner === 'object' && typeof inner.deleted === 'number'
    ? inner.deleted
    : 0;
}
