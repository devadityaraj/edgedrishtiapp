'use client'

import { useEffect, useState } from 'react'
import { NavSidebar } from '@/components/nav-sidebar'
import { apiClient } from '@/lib/api-client'
import { KeyRound, ShieldCheck, History, Monitor, Trash } from 'lucide-react'
import { useUIStore } from '@/lib/store/ui-store'

export default function UserSettingsPage() {
  const { theme, setTheme } = useUIStore()
  const [history, setHistory] = useState<any[]>([])
  const [devices, setDevices] = useState<any[]>([])

  const loadData = async () => {
    try {
      const histRes = await apiClient.getMyLoginHistory()
      if (histRes.success && histRes.data) {
        setHistory(histRes.data)
      }
      
      const devRes = await apiClient.getMyTrustedDevices()
      if (devRes.success && devRes.data) {
        setDevices(devRes.data)
      }
    } catch (error) {
      console.error('Failed to load settings data:', error)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleRevokeDevice = async (id: string) => {
    if (confirm('Are you sure you want to untrust this device? You will need to login with password next time.')) {
      const res = await apiClient.revokeMyTrustedDevice(id)
      if (res.success) {
        setDevices(prev => prev.filter(d => d.id !== id))
      }
    }
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white">Account Settings</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Manage your preferences, active browser bindings, and login audit logs.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          
          <div className="flex flex-col gap-6">
            
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4 border-b border-zinc-900 pb-2 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-orange-500" />
                <span>General Preferences</span>
              </h2>
              <div className="flex justify-between items-center text-xs">
                <div>
                  <h3 className="font-semibold text-white">Visual Interface Mode</h3>
                  <p className="text-zinc-500 mt-0.5 text-[10px]">Select dark or light theme interface presentation.</p>
                </div>
                <div className="flex gap-1.5 bg-zinc-905 border border-zinc-800 p-1 rounded-lg">
                  <button
                    onClick={() => setTheme('light')}
                    className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors ${
                      theme === 'light' ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    Light
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors ${
                      theme === 'dark' ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    Dark
                  </button>
                </div>
              </div>
            </div>

            
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4 border-b border-zinc-900 pb-2 flex items-center gap-2">
                <Monitor className="w-4 h-4 text-orange-500" />
                <span>Trusted Browser Bindings</span>
              </h2>
              
              <div className="flex flex-col gap-3">
                {devices.length === 0 ? (
                  <p className="text-xs text-zinc-500 py-4 text-center">
                    No active trusted browser bindings configured.
                  </p>
                ) : (
                  devices.map((dev) => (
                    <div 
                      key={dev.id}
                      className="bg-zinc-900 border border-zinc-850 px-3.5 py-3 rounded-xl flex justify-between items-center text-xs"
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-bold text-white">Device Token: {dev.id.substring(0, 8)}...</span>
                        <span className="text-[10px] text-zinc-500">Expires: {new Date(dev.expires_at).toLocaleString()}</span>
                      </div>
                      <button
                        onClick={() => handleRevokeDevice(dev.id)}
                        className="text-zinc-500 hover:text-red-400 p-1.5 transition-colors"
                        title="Revoke Device Trust"
                      >
                        <Trash className="w-4 h-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4 border-b border-zinc-900 pb-2 flex items-center gap-2">
              <History className="w-4 h-4 text-orange-500" />
              <span>Authentication Audit History</span>
            </h2>

            <div className="flex flex-col gap-3 max-h-[360px] overflow-y-auto pr-1">
              {history.length === 0 ? (
                <p className="text-xs text-zinc-500 py-8 text-center">No authentication audits logged.</p>
              ) : (
                history.map((log) => (
                  <div 
                    key={log.id}
                    className="bg-zinc-900 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5 text-xs"
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-zinc-400">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                      <span className={`inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${
                        log.result === 'success'
                          ? 'bg-green-950/20 border-green-900/40 text-green-400'
                          : 'bg-red-950/20 border-red-900/40 text-red-400'
                      }`}>
                        {log.result}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center text-[11px] text-zinc-500 font-mono">
                      <span>IP: {log.ipAddress}</span>
                      <span>OS: {log.osName || 'unknown'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
