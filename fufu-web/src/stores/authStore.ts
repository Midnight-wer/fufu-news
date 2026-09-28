import { create } from 'zustand';
import client from '../api/client';

interface AuthState {
  token: string | null;
  initialized: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  init: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('fufu-token'),
  initialized: false,

  login: async (username, password) => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    const { data } = await client.post('/auth/token', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    const token = data.access_token;
    localStorage.setItem('fufu-token', token);
    set({ token, initialized: true });
    // 检查首次登录成就
    try {
      await client.post('/achievements/check', { key: 'first_login', count: 1 });
    } catch {
      /* 成就检查静默失败 */
    }
  },

  logout: () => {
    localStorage.removeItem('fufu-token');
    set({ token: null, initialized: true });
  },

  init: () => {
    const token = localStorage.getItem('fufu-token');
    set({ token, initialized: true });
  },
}));
