'use client'

import { useEffect, useState } from 'react'
import { NavSidebar } from '@/components/nav-sidebar'
import { apiClient, DetectionEvent } from '@/lib/api-client'
import { ShieldAlert, Check, Calendar, Camera, Eye, ListFilter } from 'lucide-react'

export default function UserAlertsPage() {
  const [events, setEvents] = useState<DetectionEvent[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 20

  const [cameraId, setCameraId] = useState('')
  const [eventType, setEventType] = useState('')
  const [cameras, setCameras] = useState<any[]>([])

  const loadEvents = async () => {
    const res = await apiClient.getMyEvents({
      camera_id: cameraId || undefined,
      event_type: eventType || undefined,
      limit,
      offset
    })
    if (res.success && res.data) {
      setEvents(res.data.data)
      setTotal(res.data.total || 0)
    }
  }

  const loadCameras = async () => {
    const res = await apiClient.getMyCameras()
    if (res.success && res.data) {
      setCameras(res.data)
    }
  }

  useEffect(() => {
    loadCameras()
  }, [])

  useEffect(() => {
    loadEvents()
  }, [cameraId, eventType, offset])

  const handleAcknowledge = async (id: string) => {
    const res = await apiClient.acknowledgeMyEvent(id)
    if (res.success) {
      
      setEvents(prev => prev.map(e => e.id === id ? { ...e, acknowledged: true } : e))
    }
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white">Detection Logs</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Filter and review automatically classified threat triggers.</p>
          </div>
        </div>

        
        <div className="flex flex-wrap gap-4 bg-zinc-950 border border-zinc-800 p-4 rounded-2xl text-xs font-semibold">
          <div className="flex items-center gap-2">
            <ListFilter className="w-4 h-4 text-orange-500" />
            <span className="text-zinc-400 uppercase tracking-wider">Filters:</span>
          </div>

          <select
            value={cameraId}
            onChange={(e) => {
              setCameraId(e.target.value)
              setOffset(0)
            }}
            className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 focus:outline-none focus:border-orange-500 text-white font-medium"
          >
            <option value="">All Cameras</option>
            {cameras.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value)
              setOffset(0)
            }}
            className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 focus:outline-none focus:border-orange-500 text-white font-medium"
          >
            <option value="">All Alert Types</option>
            <option value="fire">Fire</option>
            <option value="smoke">Smoke</option>
            <option value="fall_detected">Fall Detected</option>
            <option value="person">Person</option>
            <option value="face">Face Match</option>
          </select>
        </div>

        
        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/40 text-zinc-400 font-bold uppercase tracking-wider">
                  <th className="p-4">Timestamp</th>
                  <th className="p-4">Camera</th>
                  <th className="p-4">Trigger Class</th>
                  <th className="p-4">Confidence</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-zinc-500">
                      No classification events found matching search parameters.
                    </td>
                  </tr>
                ) : (
                  events.map((event) => {
                    const cam = cameras.find(c => c.id === event.cameraId)
                    return (
                      <tr key={event.id} className="hover:bg-zinc-900/30 transition-colors">
                        <td className="p-4 font-mono text-zinc-400">
                          {new Date(event.timestamp).toLocaleString()}
                        </td>
                        <td className="p-4 font-semibold text-white">
                          {cam ? cam.name : event.cameraId}
                        </td>
                        <td className="p-4">
                          <span className="inline-flex items-center gap-1 font-bold text-red-400">
                            <ShieldAlert className="w-3.5 h-3.5 text-red-500" />
                            <span>{event.eventType}</span>
                          </span>
                        </td>
                        <td className="p-4 font-mono font-bold text-zinc-300">
                          {Math.round(event.confidence * 100)}%
                        </td>
                        <td className="p-4">
                          {event.acknowledged ? (
                            <span className="text-[10px] bg-green-950/20 border border-green-900/40 text-green-400 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                              Resolved
                            </span>
                          ) : (
                            <span className="text-[10px] bg-red-950/20 border border-red-900/40 text-red-400 px-2 py-0.5 rounded font-bold uppercase tracking-wider animate-pulse">
                              Pending
                            </span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          {!event.acknowledged && (
                            <button
                              onClick={() => handleAcknowledge(event.id)}
                              className="inline-flex items-center gap-1 bg-green-900/20 border border-green-800 hover:bg-green-800/40 text-green-400 px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors"
                            >
                              <Check className="w-3 h-3" />
                              <span>Acknowledge</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>

          
          {total > limit && (
            <div className="flex justify-between items-center border-t border-zinc-800 p-4 text-xs font-semibold">
              <span className="text-zinc-500">
                Showing {offset + 1} - {Math.min(offset + limit, total)} of {total} events
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(prev => Math.max(0, prev - limit))}
                  disabled={offset === 0}
                  className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-50 transition-all"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset(prev => prev + limit)}
                  disabled={offset + limit >= total}
                  className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-50 transition-all"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
