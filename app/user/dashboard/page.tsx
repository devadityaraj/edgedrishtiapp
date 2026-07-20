'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/lib/store/auth-store'
import { useCameraStore } from '@/lib/store/camera-store'
import { apiClient } from '@/lib/api-client'
import { wsClient } from '@/lib/ws-client'
import { NavSidebar } from '@/components/nav-sidebar'
import { CameraGrid } from '@/components/camera-grid'
import { Bell, ShieldAlert, Cpu } from 'lucide-react'

export default function UserDashboard() {
  const { fetchProfile } = useAuthStore()
  const { cameras, fetchCameras } = useCameraStore()
  
  const [loading, setLoading] = useState(true)
  const [recentEvents, setRecentEvents] = useState<any[]>([])

  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        window.location.href = '/'
        return
      }

      wsClient.connect(token)
      await fetchProfile()
      await fetchCameras()
      
      
      const res = await apiClient.getMyEvents({ limit: 5 })
      if (res.success && res.data) {
        setRecentEvents(res.data.data)
      }
      
      setLoading(false)
    }

    init()

    
    const unsubEvent = wsClient.registerHandler('alert', (msg: any) => {
      if (msg.data) {
        setRecentEvents(prev => [msg.data, ...prev].slice(0, 5))
      }
    })

    return () => {
      unsubEvent()
      wsClient.disconnect()
    }
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-orange-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-semibold text-zinc-400">Loading secure environment...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white">Live Security Console</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Real-time localized video telemetry and anomaly classification.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs text-zinc-300 font-semibold">Secure Isolation Mode</span>
            </div>
          </div>
        </div>

        
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 items-start">
          
          <div className="lg:col-span-3 bg-zinc-950 border border-zinc-800 rounded-2xl p-4 shadow-xl">
            <CameraGrid cameras={cameras} />
          </div>

          
          <div className="flex flex-col gap-6">
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-orange-500" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">Real-time Events</h3>
                </div>
                <span className="text-[10px] bg-red-950/40 text-red-400 border border-red-900/30 px-1.5 py-0.5 rounded font-bold">LIVE</span>
              </div>

              <div className="flex flex-col gap-3 max-h-[400px] overflow-y-auto pr-1">
                {recentEvents.length === 0 ? (
                  <div className="text-center text-zinc-500 py-12 text-xs">
                    No recent alerts triggered. System idle.
                  </div>
                ) : (
                  recentEvents.map((evt) => (
                    <div 
                      key={evt.id} 
                      className="bg-zinc-900 border border-zinc-850 p-3 rounded-xl flex flex-col gap-2 hover:border-zinc-700 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <span className="text-xs font-bold text-white flex items-center gap-1">
                          <ShieldAlert className="w-3.5 h-3.5 text-red-500" />
                          <span>{evt.eventType || 'Threat'}</span>
                        </span>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      
                      <p className="text-[11px] text-zinc-400 leading-relaxed">
                        Detected with {Math.round((evt.confidence || 0) * 100)}% confidence.
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
