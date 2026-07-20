'use client'

import { useEffect, useState } from 'react'
import { wsClient } from '@/lib/ws-client'
import { Cpu, HardDrive, Layout, Server } from 'lucide-react'

interface StatsData {
  cpu_percent?: number
  ram_percent?: number
  ram_used_gb?: number
  ram_total_gb?: number
  disk_percent?: number
  disk_used_gb?: number
  disk_total_gb?: number
  gpu?: {
    name?: string
    utilization_percent?: number
    memory_percent?: number
    memory_used_gb?: number
    memory_total_gb?: number
  } | null
}

export function SystemStats() {
  const [stats, setStats] = useState<StatsData>({})

  useEffect(() => {
    
    wsClient.connect()
    const unsub = wsClient.subscribeSystemStats((msg) => {
      if (msg.data) {
        setStats(msg.data)
      }
    })

    return () => unsub()
  }, [])

  const getMetricColor = (val: number) => {
    if (val > 85) return 'text-red-500 bg-red-500'
    if (val > 70) return 'text-orange-500 bg-orange-500'
    return 'text-green-500 bg-green-500'
  }

  const renderProgress = (val: number) => {
    const color = getMetricColor(val).split(' ')[1]
    return (
      <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
        <div 
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${val}%` }}
        />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between shadow-md">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-orange-500" />
            <span className="text-sm font-semibold text-zinc-300">CPU Usage</span>
          </div>
          <span className="text-lg font-bold font-mono text-white">
            {stats.cpu_percent !== undefined ? `${Math.round(stats.cpu_percent)}%` : '--'}
          </span>
        </div>
        {renderProgress(stats.cpu_percent || 0)}
      </div>

      
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between shadow-md">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-semibold text-zinc-300">Memory (RAM)</span>
          </div>
          <div className="text-right">
            <span className="text-lg font-bold font-mono text-white">
              {stats.ram_percent !== undefined ? `${Math.round(stats.ram_percent)}%` : '--'}
            </span>
            {stats.ram_used_gb && (
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
                {stats.ram_used_gb} / {stats.ram_total_gb} GB
              </p>
            )}
          </div>
        </div>
        {renderProgress(stats.ram_percent || 0)}
      </div>

      
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between shadow-md">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-green-500" />
            <span className="text-sm font-semibold text-zinc-300">Local Storage</span>
          </div>
          <div className="text-right">
            <span className="text-lg font-bold font-mono text-white">
              {stats.disk_percent !== undefined ? `${Math.round(stats.disk_percent)}%` : '--'}
            </span>
            {stats.disk_used_gb && (
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
                {stats.disk_used_gb} / {stats.disk_total_gb} GB
              </p>
            )}
          </div>
        </div>
        {renderProgress(stats.disk_percent || 0)}
      </div>

      
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between shadow-md">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <Layout className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-semibold text-zinc-300">GPU compute</span>
          </div>
          <div className="text-right">
            <span className="text-lg font-bold font-mono text-white">
              {stats.gpu && stats.gpu.utilization_percent !== undefined 
                ? `${Math.round(stats.gpu.utilization_percent)}%` 
                : 'OFFLINE'}
            </span>
            {stats.gpu && stats.gpu.name && (
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate max-w-[130px]" title={stats.gpu.name}>
                {stats.gpu.name}
              </p>
            )}
          </div>
        </div>
        {renderProgress(stats.gpu?.utilization_percent || 0)}
      </div>
    </div>
  )
}
