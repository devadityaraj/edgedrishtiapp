'use client'

import { useEffect, useState, useRef } from 'react'
import { apiClient, Camera } from '@/lib/api-client'
import { wsClient } from '@/lib/ws-client'
import { useCameraStore } from '@/lib/store/camera-store'
import { Expand, ShieldAlert, Wifi, WifiOff, Play } from 'lucide-react'

interface CameraTileProps {
  camera: Camera
  onExpand?: () => void
}

export function CameraTile({ camera, onExpand }: CameraTileProps) {
  const { cameraFrames, cameraDetections, setFrame } = useCameraStore()
  const [isOnline, setIsOnline] = useState(camera.status === 'online')
  const [errorText, setErrorText] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
  const [replaying, setReplaying] = useState(false)
  
  const frameData = cameraFrames[camera.id]
  const detections = cameraDetections[camera.id] || []

  const handleReplay = async () => {
    setReplaying(true)
    try {
      await apiClient.restartCamera(camera.id)
    } catch (err) {
      console.error('Replay failed:', err)
    } finally {
      setTimeout(() => setReplaying(false), 1000)
    }
  }

  
  useEffect(() => {
    setIsOnline(camera.status === 'online')
    if (camera.status !== 'online') return

    const unsub = wsClient.subscribeCamera(camera.id, (msg) => {
      if (msg.frame) {
        setFrame(camera.id, msg.frame, msg.detections || [])
        setIsOnline(true)
        setErrorText(null)
      }
    })

    return () => unsub()
  }, [camera.id, camera.status])

  
  useEffect(() => {
    const matched = useCameraStore.getState().cameras.find(c => c.id === camera.id)
    if (matched) {
      setIsOnline(matched.status === 'online')
    }
  }, [camera.status])

  return (
    <div 
      ref={containerRef}
      className="group relative bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden aspect-video flex items-center justify-center select-none shadow-lg transition-transform duration-200"
    >
      
      {isOnline && frameData ? (
        <div className="relative w-full h-full">
          <img
            src={`data:image/jpeg;base64,${frameData}`}
            alt={camera.name}
            className="w-full h-full object-cover"
          />

          
          <svg 
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 640 360"
            preserveAspectRatio="none"
          >
            {detections.map((det: any, index: number) => {
              // Bounding box: [x1, y1, x2, y2]
              const [x1, y1, x2, y2] = det.bbox || [0, 0, 0, 0]
              
              // Normalize coordinate mappings (assumes native detection source is 640x360 or maps nicely)
              
              
              
              // We can write simple percentage coordinates if we know the frame aspect or native resolution.
              
              
              
              // But just in case, if we have custom client-side triggers, we can display additional alert badges.
              return null
            })}
          </svg>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 text-zinc-500">
          {camera.status === 'reconnecting' ? (
            <>
              <Wifi className="w-8 h-8 text-orange-500 animate-pulse" />
              <span className="text-xs font-semibold text-orange-400">Reconnecting...</span>
            </>
          ) : (
            <>
              <WifiOff className="w-8 h-8 text-zinc-700" />
              <span className="text-xs font-medium">Camera Offline</span>
              {(camera.sourceType === 'local_file' || (camera as any).source_type === 'local_file') && (
                <button
                  onClick={handleReplay}
                  disabled={replaying}
                  className="mt-2 flex items-center gap-1.5 bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-800 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors pointer-events-auto shadow-md"
                >
                  <Play className="w-3.5 h-3.5 fill-white" />
                  <span>{replaying ? 'Starting...' : 'Replay Video'}</span>
                </button>
              )}
            </>
          )}
        </div>
      )}

      
      <div className="absolute top-3 left-3 right-3 flex justify-between items-center opacity-85 group-hover:opacity-100 transition-opacity pointer-events-none">
        <div className="flex items-center gap-2 bg-black/70 backdrop-blur px-2.5 py-1 rounded-lg border border-zinc-800 pointer-events-auto">
          <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-xs font-semibold text-white">{camera.name}</span>
          {camera.fps && camera.fps > 0 ? (
            <span className="text-[10px] text-zinc-400 font-mono bg-zinc-900 px-1 py-0.5 rounded border border-zinc-800">
              {Math.round(camera.fps)} FPS
            </span>
          ) : null}
        </div>
        
        {onExpand && (
          <button 
            onClick={(e) => {
              e.stopPropagation()
              onExpand()
            }}
            className="p-1.5 rounded-lg bg-black/70 backdrop-blur border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors pointer-events-auto shadow-lg"
            title="Expand Camera"
          >
            <Expand className="w-4 h-4" />
          </button>
        )}
      </div>

      
      {isOnline && detections.length > 0 && (
        <div className="absolute bottom-3 left-3 bg-red-600/90 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded border border-red-500 flex items-center gap-1 shadow-lg shadow-red-950/50 animate-bounce">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{detections[0].label} Detected</span>
        </div>
      )}
    </div>
  )
}
