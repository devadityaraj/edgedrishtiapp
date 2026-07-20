import { create } from 'zustand'
import { apiClient, User } from '../api-client'

interface AuthStore {
  user: User | null
  isLoading: boolean
  error: string | null
  isAuthenticated: boolean
  role: 'user' | 'admin' | 'master_admin' | null

  login: (username: string, password: string, pin?: string, rememberDevice?: boolean) => Promise<void>
  loginMaster: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  fetchProfile: () => Promise<void>
  clearError: () => void
  setUser: (user: User | null) => void
}


const _savedRole = (typeof window !== 'undefined' ? localStorage.getItem('userRole') : null) as AuthStore['role']
const _savedToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  isLoading: false,
  error: null,
  isAuthenticated: !!_savedToken,
  role: _savedRole,

  login: async (username, password, pin, rememberDevice) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.login({
        username,
        password,
        pin,
        rememberDevice,
      })

      if (!response.success || !response.data) {
        throw new Error(response.error || 'Login failed')
      }

      const { session_token, role, redirect_url, trusted_device_token } = response.data
      apiClient.setToken(session_token, role)
      if (trusted_device_token) {
        localStorage.setItem('trustedDeviceToken', trusted_device_token)
      }

      set({
        isLoading: false,
        isAuthenticated: true,
        role: role as any,
        user: { id: response.data.user_id, username, role: role as any, status: 'active' }
      })

      await new Promise(r => setTimeout(r, 100))
      window.location.href = redirect_url || '/user/dashboard'
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed'
      set({ isLoading: false, error: message })
      throw error
    }
  },

  loginMaster: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.loginMasterAdmin({ username, password })
      if (!response.success || !response.data) {
        const err = new Error(response.error || 'Master login failed')
        ;(err as any).status = response.status
        throw err
      }

      const { session_token, role, redirect_url } = response.data
      apiClient.setToken(session_token, role)

      set({
        isLoading: false,
        isAuthenticated: true,
        role: role as any,
        user: { id: response.data.user_id, username, role: role as any, status: 'active' }
      })

      await new Promise(r => setTimeout(r, 100))
      window.location.href = redirect_url || '/master-admin/dashboard'
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Master login failed'
      set({ isLoading: false, error: message })
      throw error
    }
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      
      apiClient.setToken(null)
      set({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        role: null,
        error: null,
      })
      window.location.href = '/'
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Logout failed'
      set({ isLoading: false, error: message })
    }
  },

  fetchProfile: async () => {
    set({ isLoading: true })
    try {
      // Just check if we are authenticated by verifying we have a token
      const token = apiClient.getToken()
      if (token) {
        set({
          isLoading: false,
          isAuthenticated: true,
        })
      } else {
        set({ isLoading: false })
      }
    } catch (error) {
      set({ isLoading: false })
    }
  },

  clearError: () => set({ error: null }),

  setUser: (user) => set({ user, isAuthenticated: !!user, role: user ? user.role : null }),
}))
