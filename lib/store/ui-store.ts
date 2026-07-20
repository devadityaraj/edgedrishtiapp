import { create } from 'zustand'

interface Notification {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration?: number
}

interface UIStore {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  notifications: Notification[]
  gridLayout: 1 | 4 | 6 | 9

  setTheme: (theme: 'light' | 'dark') => void
  toggleSidebar: () => void
  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
  setGridLayout: (layout: 1 | 4 | 6 | 9) => void
}

export const useUIStore = create<UIStore>((set) => {
  const initialTheme = typeof window !== 'undefined' 
    ? (localStorage.getItem('theme') as 'light' | 'dark') || 'dark'
    : 'dark'

  return {
    theme: initialTheme,
    sidebarOpen: true,
    notifications: [],
    gridLayout: 4,

    setTheme: (theme) => {
      set({ theme })
      if (typeof window !== 'undefined') {
        localStorage.setItem('theme', theme)
        document.documentElement.classList.toggle('dark', theme === 'dark')
      }
    },

    toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),

    addNotification: (notification) => {
      const id = Math.random().toString(36).substring(7)
      const newNotification: Notification = { ...notification, id }

      set(state => ({
        notifications: [...state.notifications, newNotification],
      }))

      if (notification.duration) {
        setTimeout(() => {
          set(state => ({
            notifications: state.notifications.filter(n => n.id !== id),
          }))
        }, notification.duration)
      }

      return id
    },

    removeNotification: (id) => {
      set(state => ({
        notifications: state.notifications.filter(n => n.id !== id),
      }))
    },

    setGridLayout: (layout) => set({ gridLayout: layout }),
  }
})
