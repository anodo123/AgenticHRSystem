import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '../types'

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  login: (accessToken: string, refreshToken: string, user: User) => void
  setAccessToken: (token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(persist(
  (set) => ({
    accessToken: null,
    refreshToken: null,
    user: null,
    login: (accessToken, refreshToken, user) => set({ accessToken, refreshToken, user }),
    setAccessToken: (accessToken) => set({ accessToken }),
    logout: () => set({ accessToken: null, refreshToken: null, user: null }),
  }),
  { name: 'darwinboxai-auth' },
))
