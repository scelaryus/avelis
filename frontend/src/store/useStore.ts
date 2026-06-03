import { create } from 'zustand';

interface UserInfo {
  user_id: string;
  email: string;
  name: string;
  role: string;
  modules: string[];
  has_rf2: boolean;
}

interface AppStore {
  // Auth
  token: string | null;
  user: UserInfo | null;
  isAuthenticated: boolean;
  login: (token: string, user: UserInfo) => void;
  logout: () => void;
  // View
  viewMode: 'interne' | 'officiel';
  setViewMode: (mode: 'interne' | 'officiel') => void;
  canSeeRF2: boolean;
  setCanSeeRF2: (v: boolean) => void;
}

// Restore from localStorage on load
const savedToken = localStorage.getItem('access_token');
const savedUser = localStorage.getItem('user_info');
let initialUser: UserInfo | null = null;
try { if (savedUser) initialUser = JSON.parse(savedUser); } catch {}

export const useStore = create<AppStore>((set) => ({
  token: savedToken,
  user: initialUser,
  isAuthenticated: !!savedToken && !!initialUser,
  login: (token, user) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user_info', JSON.stringify(user));
    set({ token, user, isAuthenticated: true, canSeeRF2: user.has_rf2 });
  },
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    set({ token: null, user: null, isAuthenticated: false, canSeeRF2: false });
  },
  viewMode: 'interne',
  setViewMode: (mode) => set({ viewMode: mode }),
  canSeeRF2: initialUser?.has_rf2 ?? false,
  setCanSeeRF2: (v) => set({ canSeeRF2: v }),
}));
