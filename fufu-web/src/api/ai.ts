import client from './client';
import type { DeepSummary } from '../hooks/useArticles';

interface AiConfig {
  ai_model?: string;
  ai_base_url?: string;
  ai_api_key?: string;
}

export async function generateDeepSummary(
  articleId: number,
  aiConfig?: AiConfig,
): Promise<DeepSummary> {
  const { data } = await client.post(
    `/ai/deep-summarize/${articleId}`,
    aiConfig || {},
  );
  return data?.data?.deep_summary || data?.deep_summary || null;
}
