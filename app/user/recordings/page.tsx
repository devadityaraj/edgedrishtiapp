'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/lib/store/auth-store'
import { apiClient } from '@/lib/api-client'
import { NavSidebar } from '@/components/nav-sidebar'
import { 
  Play, 
  Download, 
  Trash2, 
  Film, 
  Calendar, 
  Video, 
  Clock, 
  X,
  Maximize2,
  HardDrive
} from 'lucide-react'

interface Recording {
  id: string
  cameraId: string
  cameraName: string
  eventType: string
  confidence: number
  timestamp: string
  fileSize: number
  duration: number
  url: string
  downloadUrl: string
}

export default function RecordingsPage() {
  const { role, fetchProfile } = useAuthStore()
  const [loading, setLoading] = useState(true)
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [activeRecording, setActiveRecording] = useState<Recording | null>(null)
  
  
  const loadRecordings = async () => {
    const res = await apiClient.getRecordings()
    if (res.success && res.data) {
      setRecordings(res.data)
    }
    setLoading(false)
  }

  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        window.location.href = '/'
        return
      }
      await fetchProfile()
      await loadRecordings()
    }
    init()
  }, [])

  
  const formatDateHeader = (dateStr: string) => {
    const d = new Date(dateStr)
    const day = String(d.getDate()).padStart(2, '0')
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const year = d.getFullYear()
    const weekday = d.toLocaleDateString('en-US', { weekday: 'long' })
    return `${day}/${month}/${year} ${weekday}`
  }

  
  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    })
  }

  
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  
  const groupedRecordings = recordings.reduce<Record<string, Recording[]>>((groups, recording) => {
    const dateHeader = formatDateHeader(recording.timestamp)
    if (!groups[dateHeader]) {
      groups[dateHeader] = []
    }
    groups[dateHeader].push(recording)
    return groups
  }, {})

  
  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation() 
    if (!confirm('Are you sure you want to permanently delete this video recording? This cannot be undone.')) {
      return
    }
    const res = await apiClient.deleteRecording(id)
    if (res.success) {
      
      setRecordings(prev => prev.filter(r => r.id !== id))
      if (activeRecording?.id === id) {
        setActiveRecording(null)
      }
    } else {
      alert(res.error || 'Failed to delete recording')
    }
  }

  // Handle Download helper (direct URL fetch)
  const handleDownload = (recording: Recording, e: React.MouseEvent) => {
    e.stopPropagation()
    const token = localStorage.getItem('accessToken')
    const downloadUrl = `${apiClient.request.prototype.constructor.name === 'ApiClient' ? '' : 'https://localhost:8443'}/api/user/recordings/${recording.id}/download`
    
    
    // Since browser downloads don't automatically send custom headers, we can fetch it as a blob or use query param if supported,
    
    const triggerDownload = async () => {
      try {
        const response = await fetch(`/api/user/recordings/${recording.id}/download`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        if (!response.ok) throw new Error('Download failed')
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${recording.cameraName}_${new Date(recording.timestamp).getTime()}.mp4`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      } catch (err) {
        alert('Could not download file')
      }
    }
    triggerDownload()
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white flex items-center gap-2">
              <Film className="w-5 h-5 text-orange-500" />
              <span>Video Archives & Recordings</span>
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">Browse, stream, and manage event-based local security records.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl text-xs text-zinc-300">
              <HardDrive className="w-4 h-4 text-zinc-400" />
              <span>Total Records: {recordings.length}</span>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 border-4 border-orange-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-semibold text-zinc-400">Scanning storage blocks...</span>
            </div>
          </div>
        ) : recordings.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center bg-zinc-950/40 border border-dashed border-zinc-800 rounded-2xl p-12 text-center">
            <Film className="w-12 h-12 text-zinc-600 mb-4 animate-pulse" />
            <h3 className="text-base font-bold text-zinc-300">No Video Archives Found</h3>
            <p className="text-xs text-zinc-500 max-w-sm mt-1">
              Events will trigger recordings automatically when detection rules require event-based storage.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-8">
            {Object.entries(groupedRecordings).map(([dateHeader, list]) => (
              <div key={dateHeader} className="flex flex-col gap-4">
                
                <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
                  <Calendar className="w-4.5 h-4.5 text-orange-500" />
                  <h2 className="text-sm font-bold text-zinc-300 tracking-wider uppercase">
                    {dateHeader}
                  </h2>
                </div>

                {/* Grid of Recordings (same as live grid) */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {list.map((rec) => (
                    <div 
                      key={rec.id}
                      onClick={() => setActiveRecording(rec)}
                      className="group relative bg-zinc-950 border border-zinc-800 hover:border-orange-500/40 rounded-2xl overflow-hidden shadow-md hover:shadow-orange-950/10 cursor-pointer transition-all duration-300 flex flex-col"
                    >
                      {/* Video Thumbnail Placeholder (Dark Gradient & Icon with Play Button) */}
                      <div className="aspect-video relative bg-gradient-to-br from-zinc-900 via-zinc-950 to-black flex items-center justify-center overflow-hidden border-b border-zinc-800">
                        
                        <div className="absolute inset-0 bg-radial-gradient group-hover:opacity-100 opacity-50 transition-opacity duration-300" />
                        
                        
                        <Film className="w-16 h-16 text-zinc-800/40 absolute group-hover:scale-110 transition-transform duration-300" />
                        
                        
                        <div className="w-12 h-12 rounded-full bg-zinc-900/90 border border-zinc-700 text-white flex items-center justify-center group-hover:bg-orange-600 group-hover:border-orange-500 shadow-lg group-hover:scale-110 transition-all duration-300 z-10">
                          <Play className="w-5 h-5 fill-current ml-0.5" />
                        </div>

                        
                        <span className="absolute top-3 left-3 bg-red-950/60 text-red-400 border border-red-900/50 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">
                          {rec.eventType}
                        </span>

                        
                        <span className="absolute bottom-3 right-3 bg-zinc-900/80 text-zinc-300 border border-zinc-700/50 px-2 py-0.5 rounded text-[10px] font-mono">
                          {rec.duration}s
                        </span>
                      </div>

                      
                      <div className="p-4 flex flex-col gap-3 flex-1">
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="text-sm font-bold text-white leading-tight group-hover:text-orange-500 transition-colors">
                              {rec.cameraName}
                            </h4>
                            <span className="text-[11px] text-zinc-500 flex items-center gap-1 mt-1">
                              <Clock className="w-3 h-3 text-zinc-650" />
                              <span>{formatTime(rec.timestamp)}</span>
                            </span>
                          </div>
                          <span className="text-xs bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded font-mono text-zinc-400">
                            {formatFileSize(rec.fileSize)}
                          </span>
                        </div>

                        
                        <div className="flex items-center justify-between border-t border-zinc-900 pt-3 mt-auto">
                          <button
                            onClick={(e) => handleDownload(rec, e)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 hover:text-white hover:bg-zinc-800 hover:border-zinc-700 transition-all"
                            title="Download video"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Download</span>
                          </button>

                          
                          {role === 'master_admin' && (
                            <button
                              onClick={(e) => handleDelete(rec.id, e)}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950/20 border border-red-900/40 text-xs text-red-400 hover:text-white hover:bg-red-900 hover:border-red-650 transition-all"
                              title="Delete recording"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              <span>Delete</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Video Player Modal (with same webpage + fullscreen support) */}
      {activeRecording && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="relative w-full max-w-4xl bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col">
            
            
            <div className="flex items-center justify-between p-4 border-b border-zinc-850">
              <div className="flex items-center gap-2">
                <Video className="w-4.5 h-4.5 text-orange-500" />
                <h3 className="text-sm font-bold text-white">
                  {activeRecording.cameraName} — {formatTime(activeRecording.timestamp)}
                </h3>
                <span className="text-[10px] bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded font-mono">
                  {activeRecording.eventType.toUpperCase()}
                </span>
              </div>
              <button 
                onClick={() => setActiveRecording(null)}
                className="w-8 h-8 rounded-lg bg-zinc-900 hover:bg-zinc-800 flex items-center justify-center text-zinc-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            
            <div className="aspect-video bg-black relative flex items-center justify-center">
              <video
                src={`/api/user/recordings/${activeRecording.id}/stream?token=${localStorage.getItem('accessToken')}`}
                controls
                autoPlay
                className="w-full h-full object-contain"
                crossOrigin="use-credentials"
              />
            </div>

            
            <div className="flex justify-between items-center p-4 border-t border-zinc-850 bg-zinc-950/80">
              <div className="flex flex-col gap-0.5 text-xs text-zinc-400">
                <span>Event Detection Confidence: <strong>{Math.round(activeRecording.confidence * 100)}%</strong></span>
                <span>Size: {formatFileSize(activeRecording.fileSize)} | Duration: {activeRecording.duration}s</span>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={(e) => handleDownload(activeRecording, e)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 text-sm text-white hover:bg-orange-500 transition-colors shadow-lg shadow-orange-950/20"
                >
                  <Download className="w-4 h-4" />
                  <span>Download File</span>
                </button>

                {role === 'master_admin' && (
                  <button
                    onClick={(e) => {
                      handleDelete(activeRecording.id, e)
                    }}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-950/40 border border-red-900 text-sm text-red-400 hover:text-white hover:bg-red-900 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Delete Record</span>
                  </button>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}
