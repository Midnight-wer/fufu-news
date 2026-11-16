import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '@/api/client';
import { unwrapList } from '@/api/unwrap';
import type { AchievementItem } from '@/stores/achievementStore';
import { useAchievementStore } from '@/stores/achievementStore';

export function useAchievements() {
  return useQuery<AchievementItem[]>({
    queryKey: ['achievements'],
    queryFn: async () => {
      const { data } = await client.get('/achievements');
      return unwrapList<AchievementItem>(data);
    },
    staleTime: 60_000,
    placeholderData: [],
  });
}

export function useCheckAchievement() {
  const queryClient = useQueryClient();
  const addToast = useAchievementStore((s) => s.addToast);

  return useMutation({
    mutationFn: async ({ key, count = 1 }: { key: string; count?: number }) => {
      const { data } = await client.post('/achievements/check', { key, count });
      return unwrapList<AchievementItem>(data);
    },
    onSuccess: (newlyUnlocked) => {
      if (newlyUnlocked && newlyUnlocked.length > 0) {
        for (const item of newlyUnlocked) {
          addToast(item);
        }
        queryClient.invalidateQueries({ queryKey: ['achievements'] });
      }
    },
  });
}
