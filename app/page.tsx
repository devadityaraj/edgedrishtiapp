'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/store/auth-store'
import { apiClient } from '@/lib/api-client'
import { Shield, User, KeyRound, Lock, Eye, EyeOff, AlertTriangle } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading, error, clearError } = useAuthStore()

  const [activeTab, setActiveTab] = useState<'user' | 'admin'>('user')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [rememberDevice, setRememberDevice] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showMasterAdminLink, setShowMasterAdminLink] = useState(false)

  const [noUsersExist, setNoUsersExist] = useState(false)

  
  useEffect(() => {
    clearError()
    const checkStatus = async () => {
      try {
        const bootRes = await apiClient.checkFirstBoot()
        if (bootRes.success && bootRes.data?.first_boot) {
          router.push('/setup')
          return
        }
        if (bootRes.success && (bootRes.data as any)?.no_users_exist) {
          setNoUsersExist(true)
        }

        const localRes = await apiClient.checkLocalhost()
        setShowMasterAdminLink(localRes.success && localRes.data?.is_localhost === true)
      } catch (err) {
        console.error('Failed to check boot status:', err)
      }
    }
    checkStatus()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      
      const browserData = {
        browserName: navigator.userAgent,
        screenResolution: `${window.screen.width}x${window.screen.height}`,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        language: navigator.language,
      }
      
      await login(
        username,
        password,
        activeTab === 'admin' ? pin : undefined,
        rememberDevice
      )
    } catch (err) {
      
    }
  }

  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
      
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-orange-600/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-zinc-800/20 rounded-full blur-3xl" />

      <div className="w-full max-w-md z-10">
        
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-zinc-900 border border-zinc-800 rounded-full text-xs text-orange-500 font-semibold mb-4">
            <Shield className="w-3.5 h-3.5" />
            <span>100% Offline CCTV Security</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-500 bg-clip-text text-transparent">
            EDGE DRISHTI
          </h1>
          <p className="text-sm text-zinc-400 mt-1">AI-Powered Local Threat Detection Platform</p>
        </div>

        
        <div className="bg-zinc-950/70 backdrop-blur-md border border-zinc-800 rounded-2xl p-6 shadow-2xl">
          
          <div className="grid grid-cols-2 bg-zinc-900/60 p-1 rounded-xl mb-6 border border-zinc-800/40">
            <button
              onClick={() => {
                setActiveTab('user')
                clearError()
              }}
              className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'user'
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <User className="w-3.5 h-3.5" />
              <span>User Portal</span>
            </button>
            <button
              onClick={() => {
                setActiveTab('admin')
                clearError()
              }}
              className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'admin'
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <KeyRound className="w-3.5 h-3.5" />
              <span>Administrator</span>
            </button>
          </div>

          {noUsersExist && (
            <div className="mb-4 p-4 bg-orange-950/30 border border-orange-900/50 text-orange-400 rounded-xl text-xs leading-relaxed flex flex-col gap-2">
              <span className="font-bold flex items-center gap-1.5 text-orange-500">
                <AlertTriangle className="w-4 h-4" />
                <span>Portals Deactivated</span>
              </span>
              <p>No user or administrator accounts have been registered in the database yet.</p>
              <p className="text-[10px] text-zinc-500">Please access the Master Admin Console on the host machine to configure the first portal account.</p>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-950/30 border border-red-900/50 text-red-400 rounded-lg text-xs font-medium">
              {error}
            </div>
          )}

          
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                Username / ID
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={noUsersExist ? "Access Deactivated" : "Enter username"}
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  required
                  disabled={noUsersExist}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={noUsersExist ? "Access Deactivated" : "Enter password"}
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  required
                  disabled={noUsersExist}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                  disabled={noUsersExist}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            
            {activeTab === 'admin' && (
              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Admin Security PIN
                </label>
                <input
                  type="password"
                  maxLength={8}
                  pattern="\d{4,8}"
                  value={pin}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                  placeholder={noUsersExist ? "Deactivated" : "4-8 digit numeric PIN"}
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors font-mono tracking-widest text-center disabled:opacity-50 disabled:cursor-not-allowed"
                  required
                  disabled={noUsersExist}
                />
              </div>
            )}

            {/* Remember Device (User only) */}
            {activeTab === 'user' && (
              <label className="flex items-center gap-2 cursor-pointer mt-1 select-none">
                <input
                  type="checkbox"
                  checked={rememberDevice}
                  onChange={(e) => setRememberDevice(e.target.checked)}
                  className="w-4 h-4 rounded border-zinc-800 bg-zinc-900 text-orange-600 focus:ring-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={noUsersExist}
                />
                <span className="text-xs text-zinc-400 hover:text-zinc-300 transition-colors">
                  Remember this browser for 24 hours
                </span>
              </label>
            )}

            <button
              type="submit"
              disabled={isLoading || noUsersExist}
              className="w-full bg-orange-600 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-orange-950/20 mt-2"
            >
              {isLoading ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>
        </div>

        
        {showMasterAdminLink && (
          <div className="mt-6 text-center border-t border-zinc-800/80 pt-6">
            <p className="text-xs text-zinc-500 mb-2">Local Master Admin Setup Interface</p>
            <Link
              href="/master-admin/login"
              className="inline-flex items-center gap-1.5 text-xs text-orange-500 hover:text-orange-400 transition-colors font-bold bg-orange-950/20 border border-orange-900/30 px-3 py-1.5 rounded-full"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Master Admin Login</span>
            </Link>
          </div>
        )}

        
        <div className="mt-8 text-center text-[10px] text-zinc-600 flex flex-col gap-1">
          <p>© {new Date().getFullYear()} EDGE Drishti Platform</p>
          <p>Fully compliant with air-gapped system isolation rules</p>
        </div>
      </div>
    </main>
  )
}
