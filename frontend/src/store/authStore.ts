import { create } from "zustand";
import { persist } from "zustand/middleware";
import { login as apiLogin } from "@/api/auth";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,

      login: async (email, password) => {
        const data = await apiLogin(email, password);
        set({ user: data.user, token: data.access_token, refreshToken: data.refresh_token });
      },

      logout: () => set({ user: null, token: null, refreshToken: null }),
    }),
    { name: "sca-auth" }
  )
);
