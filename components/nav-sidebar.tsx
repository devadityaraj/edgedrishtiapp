'use client'

import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
import { useAuthStore } from '@/lib/store/auth-store'
import { useUIStore } from '@/lib/store/ui-store'
import { 
  LayoutDashboard, 
  Video, 
  Bell, 
  Settings, 
  Users, 
  ShieldAlert, 
  LogOut, 
  Moon, 
  Sun,
  Database,
  Cpu,
  History,
  Eye,
  Film,
  UserCheck
} from 'lucide-react'

export function NavSidebar() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { user, logout, role } = useAuthStore()
  const { theme, setTheme, sidebarOpen } = useUIStore()

  const handleLogout = () => {
    if (confirm('Are you sure you want to log out?')) {
      logout()
    }
  }

  // Determine active item state, accounting for query param tabs (like ?tab=faces)
  const isItemActive = (href: string) => {
    if (href.includes('?')) {
      const [basePath, query] = href.split('?')
      const hrefParams = new URLSearchParams(query)
      const tab = hrefParams.get('tab')
      return pathname === basePath && searchParams.get('tab') === tab
    }
    return pathname === href && !searchParams.get('tab')
  }

  
  const getNavSections = () => {
    const sections: { title?: string; items: { href: string; label: string; icon: any }[] }[] = []

    if (role === 'master_admin') {
      sections.push({
        items: [
          { href: '/master-admin/dashboard', label: 'Home (Master Panel)', icon: ShieldAlert },
          { href: '/master-admin/ai', label: 'Artificial Intelligence', icon: UserCheck },
          { href: '/admin/dashboard', label: 'Admin Panel', icon: Settings },
          { href: '/user/dashboard', label: 'Live Grid', icon: Video },
          { href: '/user/recordings', label: 'Recordings', icon: Film },
        ]
      })
    } else if (role === 'admin') {
      sections.push({
        items: [
          { href: '/admin/dashboard', label: 'Admin Dashboard', icon: LayoutDashboard },
          { href: '/user/dashboard', label: 'Live Grid', icon: Eye },
          { href: '/user/cameras', label: 'Cameras', icon: Video },
          { href: '/user/alerts', label: 'Alert History', icon: Bell },
          { href: '/user/recordings', label: 'Recordings', icon: Film },
          { href: '/user/settings', label: 'Settings', icon: Settings },
        ]
      })
    } else {
      
      sections.push({
        items: [
          { href: '/user/dashboard', label: 'Live Grid', icon: LayoutDashboard },
          { href: '/user/cameras', label: 'Cameras', icon: Video },
          { href: '/user/alerts', label: 'Alert History', icon: Bell },
          { href: '/user/recordings', label: 'Recordings', icon: Film },
          { href: '/user/settings', label: 'Settings', icon: Settings },
        ]
      })
    }

    return sections
  }

  const sections = getNavSections()
  const flatItems = sections.flatMap(s => s.items)

  if (!sidebarOpen) {
    return (
      <div className="w-16 h-screen bg-zinc-950 border-r border-zinc-800 flex flex-col items-center py-4 justify-between transition-all duration-300">
        <div className="flex flex-col items-center gap-6">
          <div className="w-8 h-8 rounded-lg bg-orange-600 flex items-center justify-center font-bold text-white text-sm animate-pulse">
            ED
          </div>
          <div className="flex flex-col gap-4 mt-8">
            {flatItems.map((item) => {
              const Icon = item.icon
              const isActive = isItemActive(item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`p-2 rounded-lg transition-colors ${
                    isActive ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
                  }`}
                  title={item.label}
                >
                  <Icon className="w-5 h-5" />
                </Link>
              )
            })}
          </div>
        </div>
        <div className="flex flex-col gap-4 items-center">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <button
            onClick={handleLogout}
            className="p-2 rounded-lg text-red-500 hover:bg-red-950/30 transition-colors"
            title="Log Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 h-screen bg-zinc-950 border-r border-zinc-800 flex flex-col justify-between p-4 transition-all duration-300">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center font-bold text-white text-base shadow-lg shadow-orange-900/30">
            ED
          </div>
          <div>
            <h1 className="font-bold text-white text-sm tracking-wide">EDGE DRISHTI</h1>
            <p className="text-[10px] text-orange-500 font-medium uppercase tracking-wider">
              {role?.replace('_', ' ')}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-6 mt-6">
          {sections.map((section, sIdx) => (
            <div key={sIdx} className="flex flex-col gap-1">
              {section.title && (
                <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider px-3 mb-2">
                  {section.title}
                </div>
              )}
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = isItemActive(item.href)
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive 
                        ? 'bg-orange-600 text-white shadow-md shadow-orange-900/20' 
                        : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                    }`}
                  >
                    <Icon className="w-4.5 h-4.5" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-4 border-t border-zinc-800 pt-4">
        <div className="flex items-center justify-between px-2 text-zinc-400">
          <span className="text-xs font-medium">Logged in as: <strong className="text-white">{user?.username}</strong></span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-zinc-900 text-zinc-400 hover:text-white hover:bg-zinc-850 transition-colors text-xs font-medium"
          >
            {theme === 'dark' ? (
              <>
                <Sun className="w-4 h-4 text-orange-500" />
                <span>Light</span>
              </>
            ) : (
              <>
                <Moon className="w-4 h-4 text-zinc-400" />
                <span>Dark</span>
              </>
            )}
          </button>
          <button
            onClick={handleLogout}
            className="px-3 py-2 rounded-lg bg-red-950/20 text-red-400 hover:bg-red-950/40 hover:text-red-300 transition-colors"
            title="Log Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
