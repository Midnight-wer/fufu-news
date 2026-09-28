import { create } from 'zustand';

export interface AchievementItem {
  key: string;
  title: string;
  description: string;
  icon: string;
  category: string;
  tier: number;
  progress: number;
  threshold: number;
  unlocked: boolean;
  unlocked_at: string | null;
}

interface AchievementState {
  toasts: AchievementItem[];
  addToast: (item: AchievementItem) => void;
  removeToast: (key: string) => void;
}

export const useAchievementStore = create<AchievementState>((set) => ({
  toasts: [],
  addToast: (item) => {
    set((s) => ({ toasts: [...s.toasts, item] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.key !== item.key) }));
    }, 5000);
  },
  removeToast: (key) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.key !== key) }));
  },
}));
