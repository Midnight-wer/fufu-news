import { useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import { useSettingsStore } from '../stores/settingsStore';
import { useCheckAchievement } from './useAchievements';

function useAiConfig() {
  const settings = useSettingsStore((s) => s.settings);
  // 防御：确保 settings 存在且有必填字段
  return {
    ai_model: settings?.aiModel || 'deepseek-v4-pro',
    ai_base_url: settings?.aiBaseUrl || 'https://api.deepseek.com/v1/chat/completions',
    ai_api_key: settings?.aiApiKey || undefined,
  };
}

export function useAISummarize() {
  const qc = useQueryClient();
  const checkAchievement = useCheckAchievement();
  const aiConfig = useAiConfig();
  return useMutation<unknown, Error, number>({
    mutationFn: async (articleId: number) => {
      const { data } = await client.post(`/ai/summarize/${articleId}`, aiConfig);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
      checkAchievement.mutate({ key: 'first_ai' });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || error?.message || 'AI 服务连接失败';
      console.error('AI 摘要失败:', detail);
    },
  });
}

export function useAITag() {
  const qc = useQueryClient();
  const checkAchievement = useCheckAchievement();
  const aiConfig = useAiConfig();
  return useMutation<unknown, Error, number>({
    mutationFn: async (articleId: number) => {
      const { data } = await client.post(`/ai/tag/${articleId}`, aiConfig);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
      checkAchievement.mutate({ key: 'first_ai' });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || error?.message || 'AI 服务连接失败';
      console.error('AI 标签生成失败:', detail);
    },
  });
}

export function useAIProcessAll() {
  const qc = useQueryClient();
  const aiConfig = useAiConfig();
  return useMutation<unknown, Error, number>({
    mutationFn: async (limit: number) => {
      const { data } = await client.post('/ai/process-all', aiConfig, {
        params: { limit },
      });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles'] });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || error?.message || 'AI 批量处理失败';
      console.error('AI 批量处理失败:', detail);
    },
  });
}

export function useAIHealthCheck() {
  const aiConfig = useAiConfig();
  return useMutation<{ status: string; detail?: string; model?: string }, Error>({
    mutationFn: async () => {
      const { data } = await client.post('/ai/health', aiConfig);
      return data;
    },
  });
}

export function useGenerateDeepSummary() {
  const qc = useQueryClient();
  const checkAchievement = useCheckAchievement();
  const aiConfig = useAiConfig();
  return useMutation<unknown, Error, number>({
    mutationFn: async (articleId: number) => {
      const { data } = await client.post(`/ai/deep-summarize/${articleId}`, aiConfig);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
      checkAchievement.mutate({ key: 'first_ai' });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || error?.message || 'AI 服务连接失败';
      console.error('AI 深度摘要生成失败:', detail);
    },
  });
}
