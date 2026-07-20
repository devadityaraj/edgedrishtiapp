'use client'

import { useState, useRef, useEffect } from 'react'
import { Plus, Trash, Check, X, RotateCcw } from 'lucide-react'

interface Point {
  x: number
  y: number
}

interface ROIEditorProps {
  backgroundImage?: string 
  initialZones?: Point[][] // Existing polygon coordinates (normalized 0-1)
  onSave: (zones: Point[][]) => void
  onCancel: () => void
}

export function ROIEditor({ backgroundImage, initialZones = [], onSave, onCancel }: ROIEditorProps) {
  const [zones, setZones] = useState<Point[][]>(initialZones)
  const [currentPoints, setCurrentPoints] = useState<Point[]>([])
  const [activeZoneIndex, setActiveZoneIndex] = useState<number | null>(null)
  
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [canvasSize, setCanvasSize] = useState({ width: 640, height: 360 })

  
  useEffect(() => {
    if (!containerRef.current) return
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width } = entry.contentRect
        
        setCanvasSize({
          width: width,
          height: (width * 9) / 16
        })
      }
    })
    resizeObserver.observe(containerRef.current)
    return () => resizeObserver.disconnect()
  }, [])

  
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw background image if available
    if (backgroundImage) {
      const img = new Image()
      img.src = backgroundImage.startsWith('data:') ? backgroundImage : `data:image/jpeg;base64,${backgroundImage}`
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        drawZones(ctx, canvas)
      }
    } else {
      
      ctx.fillStyle = '#18181b'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      
      ctx.strokeStyle = '#27272a'
      ctx.lineWidth = 1
      for (let i = 0; i < canvas.width; i += 40) {
        ctx.beginPath()
        ctx.moveTo(i, 0)
        ctx.lineTo(i, canvas.height)
        ctx.stroke()
      }
      for (let j = 0; j < canvas.height; j += 40) {
        ctx.beginPath()
        ctx.moveTo(0, j)
        ctx.lineTo(canvas.width, j)
        ctx.stroke()
      }
      drawZones(ctx, canvas)
    }

    function drawZones(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement) {
      
      zones.forEach((zone, index) => {
        if (zone.length === 0) return
        ctx.beginPath()
        ctx.moveTo(zone[0].x * canvas.width, zone[0].y * canvas.height)
        for (let i = 1; i < zone.length; i++) {
          ctx.lineTo(zone[i].x * canvas.width, zone[i].y * canvas.height)
        }
        ctx.closePath()
        
        const isActive = activeZoneIndex === index
        ctx.fillStyle = isActive ? 'rgba(249, 115, 22, 0.25)' : 'rgba(34, 197, 94, 0.15)'
        ctx.strokeStyle = isActive ? '#f97316' : '#22c55e'
        ctx.lineWidth = isActive ? 3 : 2
        ctx.fill()
        ctx.stroke()

        
        zone.forEach((pt) => {
          ctx.beginPath()
          ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 4, 0, 2 * Math.PI)
          ctx.fillStyle = isActive ? '#ea580c' : '#16a34a'
          ctx.fill()
        })
      })

      
      if (currentPoints.length > 0) {
        ctx.beginPath()
        ctx.moveTo(currentPoints[0].x * canvas.width, currentPoints[0].y * canvas.height)
        for (let i = 1; i < currentPoints.length; i++) {
          ctx.lineTo(currentPoints[i].x * canvas.width, currentPoints[i].y * canvas.height)
        }
        ctx.strokeStyle = '#3b82f6'
        ctx.lineWidth = 2
        ctx.stroke()

        
        currentPoints.forEach((pt, index) => {
          ctx.beginPath()
          ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 5, 0, 2 * Math.PI)
          ctx.fillStyle = index === 0 ? '#ef4444' : '#3b82f6'
          ctx.fill()
        })
      }
    }
  }, [zones, currentPoints, activeZoneIndex, canvasSize, backgroundImage])

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    
    
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height

    setCurrentPoints(prev => [...prev, { x, y }])
  }

  const handleFinishZone = () => {
    if (currentPoints.length < 3) {
      alert('A zone must have at least 3 points!')
      return
    }
    setZones(prev => [...prev, currentPoints])
    setCurrentPoints([])
  }

  const handleClearCurrent = () => {
    setCurrentPoints([])
  }

  const handleDeleteZone = (index: number) => {
    setZones(prev => prev.filter((_, i) => i !== index))
    if (activeZoneIndex === index) {
      setActiveZoneIndex(null)
    }
  }

  const handleSave = () => {
    onSave(zones)
  }

  return (
    <div className="flex flex-col gap-4 bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl max-w-4xl w-full mx-auto">
      <div className="flex justify-between items-center border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-lg font-bold text-white">Configure Detection Zones (ROI)</h2>
          <p className="text-xs text-zinc-400">Click on the image to draw custom polygon detection boundaries.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-sm font-medium transition-colors"
          >
            <X className="w-4 h-4" />
            <span>Cancel</span>
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-600 text-white hover:bg-orange-500 text-sm font-medium transition-colors shadow-md shadow-orange-950/20"
          >
            <Check className="w-4 h-4" />
            <span>Save Configuration</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        <div ref={containerRef} className="md:col-span-3 border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950 relative shadow-inner">
          <canvas
            ref={canvasRef}
            width={canvasSize.width}
            height={canvasSize.height}
            onClick={handleCanvasClick}
            className="cursor-crosshair w-full h-auto block"
          />
          {currentPoints.length > 0 && (
            <div className="absolute bottom-4 left-4 flex gap-2 bg-zinc-900/90 backdrop-blur border border-zinc-700 px-3 py-1.5 rounded-lg shadow-lg">
              <button
                onClick={handleFinishZone}
                className="flex items-center gap-1 text-xs font-bold text-green-400 hover:text-green-300 transition-colors"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Complete Zone</span>
              </button>
              <span className="text-zinc-600">|</span>
              <button
                onClick={handleClearCurrent}
                className="flex items-center gap-1 text-xs font-bold text-zinc-400 hover:text-zinc-300 transition-colors"
              >
                <Trash className="w-3.5 h-3.5" />
                <span>Clear points</span>
              </button>
            </div>
          )}
        </div>

        
        <div className="flex flex-col gap-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex-1 flex flex-col gap-3">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Active Zones ({zones.length})</h3>
            
            <div className="flex-1 overflow-y-auto max-h-[220px] flex flex-col gap-2 pr-1">
              {zones.length === 0 ? (
                <div className="text-center text-zinc-500 py-8 text-xs">
                  No custom zones defined. The whole screen is monitored.
                </div>
              ) : (
                zones.map((zone, index) => (
                  <div
                    key={index}
                    onClick={() => setActiveZoneIndex(index)}
                    className={`flex justify-between items-center px-3 py-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                      activeZoneIndex === index
                        ? 'bg-orange-950/20 border-orange-500 text-orange-200'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700'
                    }`}
                  >
                    <span className="font-semibold">Zone {index + 1} ({zone.length} points)</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteZone(index)
                      }}
                      className="text-zinc-500 hover:text-red-400 p-1 transition-colors"
                      title="Delete Zone"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="text-[11px] text-zinc-500 leading-relaxed bg-zinc-950 border border-zinc-800/60 p-3 rounded-lg">
            <h4 className="font-bold text-zinc-400 mb-1">How to draw:</h4>
            <ol className="list-decimal list-inside flex flex-col gap-1">
              <li>Click anywhere inside the viewport to add boundary vertices.</li>
              <li>Add at least 3 points to outline a closed region.</li>
              <li>Click &quot;Complete Zone&quot; to save it.</li>
              <li>Add multiple zones if desired.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}
