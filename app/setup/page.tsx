'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api-client'
import { Shield, Key, Download, Copy, Check, Eye, EyeOff, Lock } from 'lucide-react'

export default function SetupWizard() {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2>(1) 
  
  const [username, setUsername] = useState('master_admin')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [recoveryKey, setRecoveryKey] = useState('')
  const [keyCopied, setKeyCopied] = useState(false)
  const [keySavedCheckbox, setKeySavedCheckbox] = useState(false)

  
  useEffect(() => {
    const checkSetupNeeded = async () => {
      const res = await apiClient.checkFirstBoot()
      if (res.success && !res.data?.first_boot) {
        router.push('/')
      }
    }
    checkSetupNeeded()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters long')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const res = await apiClient.setupMasterAdmin({ username, password })
      if (res.success && res.data) {
        setRecoveryKey(res.data.recovery_key)
        setStep(2)
      } else {
        setError(res.error || 'Failed to initialize Master Admin')
      }
    } catch (err: any) {
      setError(err.message || 'System initialization failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyKey = () => {
    navigator.clipboard.writeText(recoveryKey)
    setKeyCopied(true)
    setTimeout(() => setKeyCopied(false), 2000)
  }

  const handleDownloadKey = () => {
    const element = document.createElement('a')
    const file = new Blob([
      `EDGE DRISHTI MASTER RECOVERY KEY\n`,
      `Generated: ${new Date().toISOString()}\n`,
      `Username: ${username}\n`,
      `Recovery Key: ${recoveryKey}\n`,
      `\n`,
      `WARNING: Keep this file secure. If lost, master reset is impossible.`
    ], { type: 'text/plain' })
    element.href = URL.createObjectURL(file)
    element.download = 'edge_drishti_recovery_key.txt'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const handleFinish = () => {
    router.push('/master-admin/login')
  }

  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
      
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-orange-600/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-zinc-800/20 rounded-full blur-3xl" />

      <div className="w-full max-w-xl z-10">
        
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${step >= 1 ? 'bg-orange-600 text-white' : 'bg-zinc-800 text-zinc-400'}`}>1</div>
          <div className="w-12 h-0.5 bg-zinc-800" />
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${step >= 2 ? 'bg-orange-600 text-white' : 'bg-zinc-800 text-zinc-400'}`}>2</div>
        </div>

        {step === 1 ? (
          <div className="bg-zinc-950/70 backdrop-blur-md border border-zinc-800 rounded-2xl p-8 shadow-2xl">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-orange-600/20 rounded-xl text-orange-500 mb-3 border border-orange-500/20">
                <Shield className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold">First-Boot Setup Wizard</h2>
              <p className="text-xs text-zinc-400 mt-1">Configure your primary system root Master Admin account.</p>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-950/30 border border-red-900/50 text-red-400 rounded-lg text-xs font-medium">
                {error}
              </div>
            )}

            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Master Admin Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. master_admin"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Master Admin Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 8 characters"
                    className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat master password"
                  className="w-full bg-zinc-900/50 border border-zinc-800 focus:border-orange-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-colors"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white py-2.5 rounded-xl text-sm font-semibold transition-all mt-4"
              >
                {loading ? 'Initializing Core Database...' : 'Initialize System & Generate Key'}
              </button>
            </form>
          </div>
        ) : (
          <div className="bg-zinc-950/70 backdrop-blur-md border border-zinc-800 rounded-2xl p-8 shadow-2xl flex flex-col gap-6">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-green-600/20 rounded-xl text-green-500 mb-3 border border-green-500/20">
                <Key className="w-6 h-6 animate-pulse" />
              </div>
              <h2 className="text-xl font-bold">System Cryptographic Recovery Key</h2>
              <p className="text-xs text-zinc-400 mt-1">This key is generated once and cannot be recovered if lost.</p>
            </div>

            <div className="bg-orange-950/20 border border-orange-900/40 p-4 rounded-xl text-xs text-orange-400 leading-relaxed">
              <strong>CRITICAL WARNING:</strong> Store this key in a physical safe, password manager, or secure offline environment. You will need it to recover master admin control or reset admin parameters in case of credential loss.
            </div>

            
            <div className="bg-zinc-900 border border-zinc-850 p-5 rounded-xl flex flex-col gap-3 relative shadow-inner">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Your Master Recovery Key:</span>
              <div className="font-mono text-base font-bold text-center tracking-widest text-white select-all break-all border border-zinc-800 bg-zinc-950/80 p-3 rounded-lg">
                {recoveryKey}
              </div>
              
              <div className="flex gap-2 justify-end mt-1">
                <button
                  onClick={handleCopyKey}
                  className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition-colors bg-zinc-850 border border-zinc-800 px-3 py-1.5 rounded-lg"
                >
                  {keyCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-green-400" />
                      <span className="text-green-400">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Key</span>
                    </>
                  )}
                </button>
                <button
                  onClick={handleDownloadKey}
                  className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition-colors bg-zinc-850 border border-zinc-800 px-3 py-1.5 rounded-lg"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Text file</span>
                </button>
              </div>
            </div>

            
            <label className="flex items-start gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={keySavedCheckbox}
                onChange={(e) => setKeySavedCheckbox(e.target.checked)}
                className="w-4 h-4 mt-0.5 rounded border-zinc-800 bg-zinc-900 text-orange-600 focus:ring-0 cursor-pointer"
              />
              <span className="text-xs text-zinc-400 hover:text-zinc-300 transition-colors leading-relaxed">
                I confirm that I have written down or saved the Master Recovery Key in a secure location, and I understand it will never be displayed again.
              </span>
            </label>

            <button
              onClick={handleFinish}
              disabled={!keySavedCheckbox}
              className="w-full bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white py-2.5 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2"
            >
              <Lock className="w-4 h-4" />
              <span>Complete Setup & Go to Login</span>
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
