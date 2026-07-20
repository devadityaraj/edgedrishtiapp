
const getApiBase = () => {
  if (typeof window === 'undefined') {
    return 'https://localhost:8443'
  }
  // Fallback to backend HTTPS port if running on Next.js dev server (port 3000)
  if (window.location.port && window.location.port !== '8443') {
    return 'https://localhost:8443'
  }
  return ''
}

const API_BASE = getApiBase()

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  details?: Record<string, unknown>
  status?: number
}

export interface LoginRequest {
  username: string
  password: string
  pin?: string
  rememberDevice?: boolean
  browser_data?: Record<string, any>
}

export interface LoginResponse {
  success: boolean
  user_id: string
  username: string
  role: 'user' | 'admin' | 'master_admin'
  session_token: string
  redirect_url: string
  trusted_device_token?: string
  expires_in: number
}

export interface Camera {
  id: string
  name: string
  sourceType: string
  status: 'online' | 'offline' | 'error' | 'reconnecting'
  lastSeenAt?: string
  retentionDays?: number
  resolution: string
  recordEnabled: boolean
  recordDurationSeconds: number
  addedAt?: string
  fps?: number
}

export interface DetectionEvent {
  id: string
  cameraId: string
  eventType: string
  confidence: number
  timestamp: string
  snapshotPath?: string
  boundingBoxes?: any
  acknowledged: boolean
}

export interface Notification {
  id: string
  title: string
  message: string
  type: string
  read: boolean
  createdAt: string
  detectionEventId?: string
}

export interface User {
  id: string
  username: string
  role: 'user' | 'admin' | 'master_admin'
  status: 'active' | 'disabled' | 'locked'
  lastLoginAt?: string
  createdAt?: string
  failedAttemptCount?: number
}

export interface AIModel {
  id: string
  key: string
  displayName: string
  enabledGlobally: boolean
  requiresGpu: boolean
  loaded?: boolean
  fpsLimit?: number | null
  confidenceThreshold?: number | null
  allowedClasses?: string[] | null
  alertsEnabled?: boolean
}

class ApiClient {
  private token: string | null = null
  private baseUrl: string

  constructor() {
    this.baseUrl = API_BASE
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('accessToken')
    }
  }

  setToken(token: string | null, role?: string) {
    this.token = token
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('accessToken', token)
        if (role) {
          localStorage.setItem('userRole', role)
        }
      } else {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('userRole')
      }
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('accessToken')
    }
    return this.token
  }

  public async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const headers: Headers = new Headers(options.headers || {})
    
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json')
    }

    const currentToken = this.getToken()
    if (currentToken) {
      headers.set('Authorization', `Bearer ${currentToken}`)
      headers.set('X-Session-Token', currentToken)
    }

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
      })

      if (response.status === 401) {
        this.setToken(null)
        if (typeof window !== 'undefined') {
          const path = window.location.pathname
          if (path !== '/' && !path.includes('/login')) {
            if (path.startsWith('/master-admin')) {
              window.location.href = '/master-admin/login/'
            } else {
              window.location.href = '/'
            }
          }
        }
      }

      if (response.headers.get('content-type')?.includes('application/octet-stream')) {
        const blob = await response.blob()
        return { success: true, data: blob as any }
      }

      const data = await response.json()

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || 'Request failed',
          details: data.details,
          status: response.status,
        }
      }

      let payload = data;
      if (data && typeof data === 'object' && 'data' in data) {
        const keys = Object.keys(data);
        if (keys.length === 1) {
          payload = data.data;
        }
      }

      return {
        success: true,
        data: payload,
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }

  
  async checkFirstBoot(): Promise<ApiResponse<{ first_boot: boolean }>> {
    return this.request('/api/status/first-boot')
  }

  async checkLocalhost(): Promise<ApiResponse<{ is_localhost: boolean }>> {
    return this.request('/api/auth/check-localhost')
  }

  async setupMasterAdmin(payload: any): Promise<ApiResponse<{ recovery_key: string }>> {
    return this.request('/api/auth/master/setup', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async loginMasterAdmin(payload: any): Promise<ApiResponse<LoginResponse>> {
    return this.request('/api/auth/master/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async login(payload: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    return this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  
  async getMyCameras(): Promise<ApiResponse<Camera[]>> {
    return this.request('/api/user/cameras')
  }

  async getMyCameraStatus(cameraId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/user/cameras/${cameraId}/status`)
  }

  async getMyEvents(params?: { camera_id?: string; event_type?: string; limit?: number; offset?: number }): Promise<ApiResponse<{ data: DetectionEvent[]; total: number }>> {
    const query = new URLSearchParams()
    if (params?.camera_id) query.append('camera_id', params.camera_id)
    if (params?.event_type) query.append('event_type', params.event_type)
    if (params?.limit) query.append('limit', params.limit.toString())
    if (params?.offset) query.append('offset', params.offset.toString())
    return this.request(`/api/user/events?${query}`)
  }

  async acknowledgeMyEvent(eventId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/user/events/${eventId}/acknowledge`, { method: 'POST' })
  }

  async getMyNotifications(unreadOnly = false): Promise<ApiResponse<{ data: Notification[]; unread_count: number }>> {
    return this.request(`/api/user/notifications?unread_only=${unreadOnly}`)
  }

  async readMyNotification(notificationId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/user/notifications/${notificationId}/read`, { method: 'PATCH' })
  }

  async readAllMyNotifications(): Promise<ApiResponse<void>> {
    return this.request('/api/user/notifications/read-all', { method: 'POST' })
  }

  async getMyLoginHistory(): Promise<ApiResponse<any[]>> {
    return this.request('/api/user/login-history')
  }

  async getMyTrustedDevices(): Promise<ApiResponse<any[]>> {
    return this.request('/api/user/trusted-devices')
  }

  async revokeMyTrustedDevice(deviceId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/user/trusted-devices/${deviceId}`, { method: 'DELETE' })
  }

  async getMyAnalytics(cameraId?: string): Promise<ApiResponse<any[]>> {
    const query = cameraId ? `?camera_id=${cameraId}` : ''
    return this.request(`/api/user/analytics${query}`)
  }

  // ── Camera CRUD (Admin) ──
  async getCameras(): Promise<ApiResponse<Camera[]>> {
    return this.request('/api/cameras')
  }

  async addCamera(payload: { name: string; sourceType: string; connectionUri: string; resolution: string; recordEnabled: boolean; recordDurationSeconds: number }): Promise<ApiResponse<Camera>> {
    return this.request('/api/admin/cameras', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async updateCamera(cameraId: string, payload: { name?: string; sourceType?: string; connectionUri?: string; resolution?: string; recordEnabled?: boolean; recordDurationSeconds?: number }): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/cameras/${cameraId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

  async removeCamera(cameraId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/cameras/${cameraId}`, { method: 'DELETE' })
  }

  async restartCamera(cameraId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/cameras/${cameraId}/restart`, { method: 'POST' })
  }

  // ── Camera model configurations (Admin) ──
  async getCameraModels(cameraId: string): Promise<ApiResponse<any[]>> {
    return this.request(`/api/admin/cameras/${cameraId}/models`)
  }

  async updateCameraModel(cameraId: string, modelId: string, payload: any): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/cameras/${cameraId}/models/${modelId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

  
  async getAIModels(): Promise<ApiResponse<AIModel[]>> {
    return this.request('/api/ai-models')
  }

  async toggleAIModel(
    modelId: string,
    enabled: boolean,
    fpsLimit?: number | null,
    allowedClasses?: string[],
    confidenceThreshold?: number | null,
    alertsEnabled?: boolean
  ): Promise<ApiResponse<void>> {
    const payload: any = { enabled }
    if (fpsLimit !== undefined) {
      payload.fpsLimit = fpsLimit
    }
    if (allowedClasses !== undefined) {
      payload.allowedClasses = allowedClasses
    }
    if (confidenceThreshold !== undefined) {
      payload.confidenceThreshold = confidenceThreshold
    }
    if (alertsEnabled !== undefined) {
      payload.alertsEnabled = alertsEnabled
    }
    return this.request(`/api/admin/ai-models/${modelId}/toggle`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  
  async getUsers(): Promise<ApiResponse<User[]>> {
    return this.request('/api/admin/users')
  }

  async addUser(payload: any): Promise<ApiResponse<User>> {
    return this.request('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async removeUser(userId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/users/${userId}`, { method: 'DELETE' })
  }

  async resetUserPassword(userId: string, payload: any): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async reEnableUser(userId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/admin/users/${userId}/re-enable`, { method: 'POST' })
  }

  async getUserLoginHistory(userId: string): Promise<ApiResponse<any[]>> {
    return this.request(`/api/admin/users/${userId}/login-history`)
  }

  
  async getSystemConfig(): Promise<ApiResponse<any>> {
    return this.request('/api/master/config')
  }

  async updateSystemConfig(payload: any): Promise<ApiResponse<void>> {
    return this.request('/api/master/config', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  }

  async getAuditLog(params?: { limit?: number; offset?: number }): Promise<ApiResponse<{ data: any[]; total: number }>> {
    const limit = params?.limit || 100
    const offset = params?.offset || 0
    return this.request(`/api/master/audit?limit=${limit}&offset=${offset}`)
  }

  async verifyAuditChain(): Promise<ApiResponse<any>> {
    return this.request('/api/master/audit/verify', { method: 'POST' })
  }

  async getAdmins(): Promise<ApiResponse<User[]>> {
    return this.request('/api/master/admins')
  }

  async createAdmin(payload: any): Promise<ApiResponse<User>> {
    return this.request('/api/master/admins', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async deleteAdmin(userId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/master/admins/${userId}`, { method: 'DELETE' })
  }

  async resetAdminPassword(userId: string, payload: any): Promise<ApiResponse<void>> {
    return this.request(`/api/master/admins/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async getRecoveryKeyStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/master/recovery-key/status')
  }

  async regenerateRecoveryKey(): Promise<ApiResponse<{ recovery_key: string }>> {
    return this.request('/api/master/recovery-key/regenerate', { method: 'POST' })
  }

  async getAlertContacts(): Promise<ApiResponse<any[]>> {
    return this.request('/api/master/contacts')
  }

  async createAlertContact(payload: any): Promise<ApiResponse<any>> {
    return this.request('/api/master/contacts', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async deleteAlertContact(contactId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/master/contacts/${contactId}`, { method: 'DELETE' })
  }

  async testAlertContact(contactId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/master/contacts/${contactId}/test`, { method: 'POST' })
  }

  async getFaces(): Promise<ApiResponse<any[]>> {
    return this.request('/api/master/faces')
  }

  async enrollFace(label: string | null, files: File[]): Promise<ApiResponse<any>> {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('images', file)
    })
    const url = label ? `/api/master/faces?label=${encodeURIComponent(label)}` : '/api/master/faces'
    return this.request(url, {
      method: 'POST',
      body: formData,
    })
  }

  async deleteFace(faceId: string): Promise<ApiResponse<void>> {
    return this.request(`/api/master/faces/${faceId}`, { method: 'DELETE' })
  }

  async activateLockdown(): Promise<ApiResponse<void>> {
    return this.request('/api/master/lockdown', { method: 'POST' })
  }

  async releaseLockdown(): Promise<ApiResponse<void>> {
    return this.request('/api/master/lockdown/release', { method: 'POST' })
  }

  async getSystemHardware(): Promise<ApiResponse<any>> {
    return this.request('/api/master/hardware')
  }

  async downloadBackup(): Promise<ApiResponse<Blob>> {
    return this.request('/api/master/backup', { method: 'POST' })
  }

  async detectUsbDevices(): Promise<ApiResponse<any>> {
    return this.request('/api/admin/cameras/detect-usb')
  }

  async uploadCameraVideo(file: File): Promise<ApiResponse<any>> {
    const formData = new FormData()
    formData.append('file', file)
    return this.request('/api/admin/cameras/upload-video', {
      method: 'POST',
      body: formData,
    })
  }

  async getRecordings(): Promise<ApiResponse<any>> {
    return this.request('/api/user/recordings')
  }

  async deleteRecording(eventId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/user/recordings/${eventId}`, {
      method: 'DELETE',
    })
  }
}

export const apiClient = new ApiClient()
