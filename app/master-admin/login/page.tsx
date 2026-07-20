'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/store/auth-store'
import { apiClient } from '@/lib/api-client'
import { ShieldAlert, KeyRound, Lock, Eye, EyeOff, AlertTriangle } from 'lucide-react'

export default function MasterAdminLogin() {
  const router = useRouter()
  const { loginMaster, isLoading, error, clearError } = useAuthStore()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  
  
  const [recoveryMode, setRecoveryMode] = useState(false)
  const [recoveryKey, setRecoveryKey] = useState('')
  const [newUsername, setNewUsername] = useState('master_admin')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [recoverySuccessMsg, setRecoverySuccessMsg] = useState('')

  
  const [lockoutTimer, setLockoutTimer] = useState<number | null>(null)
  const [failedAttempts, setFailedAttempts] = useState<number>(0)

  
  const [isFirstBoot, setIsFirstBoot] = useState<boolean | null>(null)

  useEffect(() => {
    const checkFirstBoot = async () => {
      try {
        const res = await apiClient.checkFirstBoot()
        if (res.success && res.data?.first_boot) {
          router.replace('/setup')
        } else {
          setIsFirstBoot(false)
        }
      } catch (err) {
        setIsFirstBoot(false)
      }
    }
    checkFirstBoot()
  }, [router])

  useEffect(() => {
    const savedAttempts = localStorage.getItem('masterAdminFailedAttempts')
    if (savedAttempts) {
      setFailedAttempts(parseInt(savedAttempts, 10))
    }

    const savedExpiry = localStorage.getItem('masterAdminLockoutExpiry')
    if (savedExpiry) {
      const expiry = parseInt(savedExpiry, 10)
      const now = Date.now()
      if (expiry > now) {
        const remaining = Math.ceil((expiry - now) / 1000)
        setLockoutTimer(remaining)
      } else {
        localStorage.removeItem('masterAdminLockoutExpiry')
      }
    }
  }, [])

  useEffect(() => {
    if (lockoutTimer === null) return

    if (lockoutTimer <= 0) {
      setLockoutTimer(null)
      localStorage.removeItem('masterAdminLockoutExpiry')
      return
    }

    const interval = setInterval(() => {
      setLockoutTimer((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(interval)
          localStorage.removeItem('masterAdminLockoutExpiry')
          return null
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [lockoutTimer])

  const triggerLockout = (seconds: number) => {
    const expiry = Date.now() + seconds * 1000
    localStorage.setItem('masterAdminLockoutExpiry', expiry.toString())
    setLockoutTimer(seconds)
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (lockoutTimer !== null) return

    clearError()
    try {
      await loginMaster(username, password)
      
      localStorage.removeItem('masterAdminFailedAttempts')
      localStorage.removeItem('masterAdminLockoutExpiry')
      setFailedAttempts(0)
    } catch (err: any) {
      const status = err.status
      if (status === 429) {
        
        const newAttempts = Math.max(3, failedAttempts)
        setFailedAttempts(newAttempts)
        localStorage.setItem('masterAdminFailedAttempts', newAttempts.toString())
        triggerLockout(30)
      } else if (status === 401) {
        
        const newAttempts = failedAttempts + 1
        setFailedAttempts(newAttempts)
        localStorage.setItem('masterAdminFailedAttempts', newAttempts.toString())
        
        if (newAttempts >= 3 && newAttempts < 5) {
          triggerLockout(30)
        }
      }
    }
  }

  const handleRecover = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()

    if (newPassword.length < 8) {
      alert('Password must be at least 8 characters')
      return
    }

    if (newPassword !== confirmPassword) {
      alert('Passwords do not match')
      return
    }

    try {
      const res = await apiClient.request<any>('/api/auth/master/recover', {
        method: 'POST',
        body: JSON.stringify({
          recovery_key: recoveryKey,
          new_username: newUsername,
          new_password: newPassword,
        })
      })

      if (res.success && res.data) {
        
        setRecoverySuccessMsg('Account recovered successfully! Redirecting you now...')
        apiClient.setToken(res.data.session_token)
        localStorage.removeItem('masterAdminFailedAttempts')
        localStorage.removeItem('masterAdminLockoutExpiry')
        setFailedAttempts(0)
        setLockoutTimer(null)
        setTimeout(() => {
          router.push('/master-admin/dashboard')
        }, 1500)
      } else {
        alert(res.error || 'Recovery failed. Verify your key.')
      }
    } catch (err: any) {
      alert(err.message || 'Recovery connection error')
    }
  }

  const isInputDisabled = isLoading || lockoutTimer !== null || failedAttempts >= 5

  if (isFirstBoot === null) {
    return (
      <main className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
        
        <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-red-600/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-orange-600/5 rounded-full blur-3xl" />
        <div className="text-zinc-500 text-xs font-semibold animate-pulse z-10">
          Initializing Console...
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
      
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-red-600/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-orange-600/5 rounded-full blur-3xl" />

      <div className="w-full max-w-md z-10">
        
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-red-950/20 border border-red-900/30 rounded-full text-xs text-red-400 font-semibold mb-4">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Localhost Isolated Console</span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white flex items-center justify-center gap-2">
            <Lock className="w-5 h-5 text-red-500" />
            <span>MASTER CONSOLE</span>
          </h1>
          <p className="text-xs text-zinc-500 mt-1">EDGE Drishti Core Parameters & Setup Recovery</p>
        </div>

        
        <div className="bg-zinc-950/80 backdrop-blur border border-zinc-800 rounded-2xl p-6 shadow-2xl">
          {recoveryMode ? (
            
            <form onSubmit={handleRecover} className="flex flex-col gap-4">
              <div className="text-center mb-2">
                <h2 className="text-sm font-bold text-orange-400">Master Credentials Recovery</h2>
                <p className="text-[10px] text-zinc-400 mt-0.5">Use your 128-bit key to reset the Master Admin account.</p>
              </div>

              {recoverySuccessMsg && (
                <div className="p-3 bg-green-950/30 border border-green-900/50 text-green-400 rounded-lg text-xs font-semibold">
                  {recoverySuccessMsg}
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Recovery Key
                </label>
                <input
                  type="text"
                  value={recoveryKey}
                  onChange={(e) => setRecoveryKey(e.target.value.toUpperCase())}
                  placeholder="Enter your cryptographic key"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none transition-colors font-mono uppercase tracking-wider"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  New Username
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Min 8 characters"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none transition-colors"
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full bg-orange-600 hover:bg-orange-500 text-white py-2.5 rounded-xl text-xs font-semibold transition-all mt-2"
              >
                Reset Credentials & Sign In
              </button>

              <button
                type="button"
                onClick={() => {
                  setRecoveryMode(false)
                  clearError()
                }}
                className="text-center text-xs text-zinc-500 hover:text-zinc-300 transition-colors mt-1"
              >
                Cancel & Return to Login
              </button>
            </form>
          ) : (
            
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              {error && !lockoutTimer && failedAttempts < 5 && (
                <div className="p-3 bg-red-950/30 border border-red-900/50 text-red-400 rounded-lg text-xs font-medium">
                  {error}
                </div>
              )}

              
              {lockoutTimer !== null && (
                <div className="p-3 bg-red-950/30 border border-red-900/40 text-red-400 rounded-xl text-xs flex flex-col gap-1.5 animate-pulse">
                  <div className="flex items-center gap-1.5 font-bold">
                    <ShieldAlert className="w-4 h-4 text-red-500 shrink-0" />
                    <span>Master Admin Console Locked</span>
                  </div>
                  <p className="text-zinc-300">
                    Try again after <span className="font-extrabold text-white text-sm">{lockoutTimer} seconds</span>.
                  </p>
                  {failedAttempts < 5 && (
                    <p className="text-[10px] text-zinc-400 font-semibold">
                      Attempts left: {5 - failedAttempts} of 5 before permanent disable.
                    </p>
                  )}
                </div>
              )}

              
              {failedAttempts > 0 && failedAttempts < 3 && lockoutTimer === null && (
                <div className="p-3 bg-amber-950/20 border border-amber-900/40 text-amber-400 rounded-xl text-xs flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                    <span>Failed Attempt Tracked</span>
                  </div>
                  <p className="text-zinc-300 text-[10px]">
                    {5 - failedAttempts} attempts remaining before account disable.
                  </p>
                </div>
              )}

              
              {failedAttempts >= 5 && (
                <div className="p-3 bg-red-950/40 border border-red-900/60 text-red-400 rounded-xl text-xs flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 font-bold">
                    <ShieldAlert className="w-4.5 h-4.5 text-red-500 shrink-0" />
                    <span className="font-extrabold tracking-wider uppercase">Console Access Blocked</span>
                  </div>
                  <p className="text-zinc-300">
                    Master admin account has been disabled. Please use the Recovery Key below to reset your credentials.
                  </p>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-red-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors disabled:opacity-50"
                  required
                  disabled={isInputDisabled}
                />
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
                    placeholder="Enter password"
                    className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-red-500 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors disabled:opacity-50"
                    required
                    disabled={isInputDisabled}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
                    disabled={isInputDisabled}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isInputDisabled}
                className="w-full bg-red-700 hover:bg-red-600 disabled:opacity-40 disabled:hover:bg-red-700 text-white py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg mt-2 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  'Connecting Console...'
                ) : failedAttempts >= 5 ? (
                  <>
                    <ShieldAlert className="w-4 h-4" />
                    <span>Console Disabled</span>
                  </>
                ) : lockoutTimer !== null ? (
                  <>
                    <Lock className="w-4 h-4" />
                    <span>Locked ({lockoutTimer}s)</span>
                  </>
                ) : (
                  'Open Security Terminal'
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setRecoveryMode(true)
                  clearError()
                }}
                className="text-center text-xs text-orange-500 hover:text-orange-400 transition-colors font-bold mt-2"
              >
                Forgot credentials? Use Recovery Key
              </button>
            </form>
          )}
        </div>

        
        <div className="mt-6 text-center">
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors font-semibold">
            ← Back to User Login
          </Link>
        </div>
      </div>
    </main>
  )
}
