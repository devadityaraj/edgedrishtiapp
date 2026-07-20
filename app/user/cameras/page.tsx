'use client'

import { useEffect, useState } from 'react'
import { useCameraStore } from '@/lib/store/camera-store'
import { NavSidebar } from '@/components/nav-sidebar'
import { Video, Radio, Shield, ShieldAlert, HardDrive, RefreshCw } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

export default function UserCamerasPage() {
  const { cameras, fetchCameras, isLoading } = useCameraStore()
  const [detailedStatuses, setDetailedStatuses] = useState<Record<string, any>>({})

  const loadData = async () => {
    await fetchCameras()
    
    const statusMap: Record<string, any> = {}
    for (let c of useCameraStore.getState().cameras) {
      const res = await apiClient.getMyCameraStatus(c.id)
      if (res.success && res.data) {
        statusMap[c.id] = res.data
      }
    }
    setDetailedStatuses(statusMap)
  }

  useEffect(() => {
    loadData()
  }, [])

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white">Camera Registry</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Overview of active network and USB video ingestion sources.</p>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 px-3.5 py-2 rounded-xl text-xs font-semibold text-zinc-300 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Status</span>
          </button>
        </div>

        
        {cameras.length === 0 ? (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-12 text-center text-zinc-500 max-w-xl mx-auto mt-12 flex flex-col items-center gap-4">
            <Video className="w-12 h-12 text-zinc-700 animate-pulse" />
            <div>
              <p className="font-semibold text-sm text-zinc-400">No Ingestion Channels Found</p>
              <p className="text-xs text-zinc-500 mt-1 max-w-sm">Please ask your system administrator to register camera sources in the Admin Console.</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {cameras.map((camera) => {
              const details = detailedStatuses[camera.id] || {}
              const isOnline = camera.status === 'online' || details.status === 'online'
              const statusText = details.status || camera.status || 'offline'
              const isUnavailableDevice = ['webcam', 'usb', 'capture_card'].includes(camera.sourceType) && statusText === 'offline'
              const displayStatus = isUnavailableDevice ? 'Device unavailable' : statusText
              
              return (
                <div 
                  key={camera.id}
                  className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 flex flex-col gap-4 shadow-xl hover:border-zinc-700 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center justify-center text-zinc-300">
                        <Video className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white">{camera.name}</h3>
                        <span className="text-[10px] bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded border border-zinc-800 font-mono mt-1 inline-block uppercase tracking-wider">
                          {camera.sourceType}
                        </span>
                      </div>
                    </div>

                    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded border ${
                      isOnline
                        ? 'bg-green-950/20 border-green-900/40 text-green-400'
                        : camera.status === 'reconnecting'
                        ? 'bg-orange-950/20 border-orange-900/40 text-orange-400'
                        : 'bg-red-950/20 border-red-900/40 text-red-400'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                      <span>{displayStatus}</span>
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 border-t border-zinc-900 pt-4 text-xs">
                    <div className="flex flex-col gap-1">
                      <span className="text-zinc-500 font-medium">Framerate:</span>
                      <span className="text-white font-mono font-bold">
                        {details.fps !== undefined ? `${Math.round(details.fps)} FPS` : '0 FPS'}
                      </span>
                    </div>

                    <div className="flex flex-col gap-1">
                      <span className="text-zinc-500 font-medium">Resolution:</span>
                      <span className="text-white font-semibold flex items-center gap-1">
                        <HardDrive className="w-3.5 h-3.5 text-zinc-400" />
                        <span>{camera.resolution}</span>
                      </span>
                    </div>
                  </div>

                  <div className="bg-zinc-900/40 border border-zinc-900 p-3 rounded-xl flex items-center justify-between text-xs text-zinc-400 mt-1">
                    <span className="flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-zinc-500" />
                      <span>Last Activity:</span>
                    </span>
                    <span className="font-mono text-[10px] text-zinc-300">
                      {camera.lastSeenAt ? new Date(camera.lastSeenAt).toLocaleString() : 'Never'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
