type MessageHandler<T = any> = (data: T) => void

interface WsMsg {
  type: string
  camera_id?: string
  timestamp?: string
  frame?: string
  detections?: any[]
  data?: any
}

class WebSocketClient {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 2000
  private token: string | null = null
  private url: string
  private activeSubscriptions: Set<string> = new Set()
  private wantSystemStats = false

  constructor() {
    this.url = this.getWebSocketUrl()
  }

  private getWebSocketUrl(): string {
    if (typeof window === 'undefined') return 'wss://localhost:8443/ws/live'
    
    // Fallback if running on Next.js dev server (port 3000)
    if (window.location.port && window.location.port !== '8443') {
      return 'wss://localhost:8443/ws/live'
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws/live`
  }

  connect(token?: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return
    
    if (token) {
      this.token = token
    }

    try {
      const url = new URL(this.url)
      if (this.token) {
        url.searchParams.append('token', this.token)
      } else {
        const localToken = localStorage.getItem('accessToken')
        if (localToken) url.searchParams.append('token', localToken)
      }
      
      this.ws = new WebSocket(url.toString())
      
      this.ws.onopen = () => {
        console.log('[EDGE Drishti] WebSocket connected')
        this.reconnectAttempts = 0
        
        this.activeSubscriptions.forEach(camId => {
          this.send('subscribe_camera', { camera_id: camId })
          this.send('get_latest_frame', { camera_id: camId })
        })
        if (this.wantSystemStats) {
          this.send('subscribe_system', {})
        }
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message: WsMsg = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('[EDGE Drishti] Failed to parse message:', error)
        }
      }
      
      this.ws.onerror = (error) => {
        console.error('[EDGE Drishti] WebSocket error:', error)
      }
      
      this.ws.onclose = () => {
        console.log('[EDGE Drishti] WebSocket disconnected')
        this.attemptReconnect()
      }
    } catch (error) {
      console.error('[EDGE Drishti] Connection failed:', error)
      this.attemptReconnect()
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
      console.log(`[EDGE Drishti] Reconnecting in ${delay}ms...`)
      setTimeout(() => this.connect(this.token || undefined), delay)
    }
  }

  private handleMessage(message: WsMsg) {
    
    const handlers = this.handlers.get(message.type)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message)
        } catch (error) {
          console.error(`[EDGE Drishti] Error in ${message.type} handler:`, error)
        }
      })
    }
  }

  subscribeCamera(cameraId: string, handler: MessageHandler<WsMsg>): () => void {
    this.activeSubscriptions.add(cameraId)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send('subscribe_camera', { camera_id: cameraId })
      
      this.send('get_latest_frame', { camera_id: cameraId })
    }

    const unsubFrame = this.registerHandler('frame', (msg: WsMsg) => {
      if (msg.camera_id === cameraId) {
        handler(msg)
      }
    })

    return () => {
      unsubFrame()
      this.activeSubscriptions.delete(cameraId)
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send('unsubscribe_camera', { camera_id: cameraId })
      }
    }
  }

  subscribeSystemStats(handler: MessageHandler<WsMsg>): () => void {
    this.wantSystemStats = true
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send('subscribe_system', {})
    }

    const unsubStats = this.registerHandler('system_stats', handler)

    return () => {
      unsubStats()
      this.wantSystemStats = false
    }
  }

  registerHandler<T = any>(type: string, handler: MessageHandler<T>): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    
    this.handlers.get(type)!.add(handler)
    
    return () => {
      const handlers = this.handlers.get(type)
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  send(type: string, payload: any) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('[EDGE Drishti] WebSocket not open, message dropped:', type)
      return
    }
    this.ws.send(JSON.stringify({ type, ...payload }))
  }

  disconnect() {
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsClient = new WebSocketClient()
