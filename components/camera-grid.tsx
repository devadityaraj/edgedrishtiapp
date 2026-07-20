'use client'

import { useState } from 'react'
import { Camera } from '@/lib/api-client'
import { CameraTile } from './camera-tile'
import { useUIStore } from '@/lib/store/ui-store'
import { Grid2X2, Grid3X3, Maximize } from 'lucide-react'

interface CameraGridProps {
  cameras: Camera[]
}

export function CameraGrid({ cameras }: CameraGridProps) {
  const { gridLayout, setGridLayout } = useUIStore()
  const [expandedCameraId, setExpandedCameraId] = useState<string | null>(null)

  
  const getGridClass = () => {
    switch (gridLayout) {
      case 1:
        return 'grid-cols-1'
      case 4:
        return 'grid-cols-1 sm:grid-cols-2 gap-4'
      case 6:
        return 'grid-cols-1 sm:grid-cols-3 md:grid-cols-3 gap-4'
      case 9:
        return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4'
      default:
        return 'grid-cols-2'
    }
  }

  
  if (expandedCameraId) {
    const matched = cameras.find((c) => c.id === expandedCameraId)
    if (matched) {
      return (
        <div className="flex flex-col gap-4 h-full">
          <div className="flex justify-between items-center bg-zinc-900 border border-zinc-800 px-4 py-2.5 rounded-xl">
            <span className="text-sm font-semibold text-white">Expanded Mode: {matched.name}</span>
            <button
              onClick={() => setExpandedCameraId(null)}
              className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg border border-zinc-700 font-medium transition-colors"
            >
              Back to Grid
            </button>
          </div>
          <div className="flex-1 bg-black rounded-xl overflow-hidden border border-zinc-800 flex items-center justify-center">
            <div className="w-full max-w-5xl shadow-2xl">
              <CameraTile camera={matched} />
            </div>
          </div>
        </div>
      )
    }
  }

  
  const visibleCameras = cameras.slice(0, gridLayout)

  return (
    <div className="flex flex-col gap-4 h-full">
      
      <div className="flex justify-between items-center border-b border-zinc-800 pb-3">
        <h2 className="text-sm font-bold text-white uppercase tracking-wider">Live Feeds ({visibleCameras.length}/{cameras.length})</h2>
        
        <div className="flex gap-1.5 bg-zinc-900 border border-zinc-850 p-1 rounded-lg">
          <button
            onClick={() => setGridLayout(1)}
            className={`p-1.5 rounded-md transition-colors ${
              gridLayout === 1 ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
            }`}
            title="Single Camera View"
          >
            <Maximize className="w-4 h-4" />
          </button>
          <button
            onClick={() => setGridLayout(4)}
            className={`p-1.5 rounded-md transition-colors ${
              gridLayout === 4 ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
            }`}
            title="2x2 Grid View"
          >
            <Grid2X2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setGridLayout(9)}
            className={`p-1.5 rounded-md transition-colors ${
              gridLayout === 9 ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
            }`}
            title="3x3 Grid View"
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
        </div>
      </div>

      
      {visibleCameras.length === 0 ? (
        <div className="flex-1 bg-zinc-900/40 border border-zinc-850 rounded-xl flex flex-col items-center justify-center text-center p-8 gap-3 min-h-[300px]">
          <span className="text-zinc-600 text-sm">No cameras configured yet.</span>
          <p className="text-xs text-zinc-500 max-w-sm">Please ask your system administrator or access the Admin Panel to configure camera ingestion streams.</p>
        </div>
      ) : (
        <div className={`grid ${getGridClass()}`}>
          {visibleCameras.map((camera) => (
            <CameraTile
              key={camera.id}
              camera={camera}
              onExpand={() => setExpandedCameraId(camera.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
