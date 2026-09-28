import { create } from 'zustand';

export type CompanionMood = 'idle' | 'happy' | 'excited' | 'sleepy';

interface CompanionState {
  message: string | null;
  mood: CompanionMood;
  showMessage: (msg: string) => void;
  clearMessage: () => void;
  setMood: (mood: CompanionMood) => void;
}

export const useCompanionStore = create<CompanionState>((set) => ({
  message: null,
  mood: 'idle',
  showMessage: (msg) => {
    set({ message: msg });
    setTimeout(() => set({ message: null }), 4000);
  },
  clearMessage: () => set({ message: null }),
  setMood: (mood) => set({ mood }),
}));
