import { create } from 'zustand'
import { apiClient, Camera, DetectionEvent } from '../api-client'
import { wsClient } from '../ws-client'

interface CameraStore {
  cameras: Camera[]
  selectedCameraId: string | null
  detectionEvents: Map<string, DetectionEvent[]>
  isLoading: boolean
  error: string | null
  cameraFrames: Record<string, string> 
  cameraDetections: Record<string, any[]> 

  fetchCameras: () => Promise<void>
  selectCamera: (cameraId: string | null) => void
  getDetectionEvents: (cameraId?: string) => Promise<void>
  addCamera: (name: string, sourceType: string, connectionUri: string, resolution?: string, recordEnabled?: boolean, recordDurationSeconds?: number) => Promise<void>
  removeCamera: (cameraId: string) => Promise<void>
  acknowledgeEvent: (eventId: string) => Promise<void>
  updateCameraStatus: (cameraId: string, status: Camera['status']) => void
  addDetectionEvent: (cameraId: string, event: DetectionEvent) => void
  setFrame: (cameraId: string, frame: string, detections: any[]) => void
}

export const useCameraStore = create<CameraStore>((set, get) => ({
  cameras: [],
  selectedCameraId: null,
  detectionEvents: new Map(),
  isLoading: false,
  error: null,
  cameraFrames: {},
  cameraDetections: {},

  fetchCameras: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.getMyCameras()
      if (response.success && response.data) {
        set({ cameras: response.data, isLoading: false })
      } else {
        set({ error: response.error, isLoading: false })
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to fetch cameras', isLoading: false })
    }
  },

  selectCamera: (cameraId) => set({ selectedCameraId: cameraId }),

  getDetectionEvents: async (cameraId) => {
    try {
      const response = await apiClient.getMyEvents({ camera_id: cameraId, limit: 50 })
      if (response.success && response.data) {
        const current = get().detectionEvents
        if (cameraId) {
          current.set(cameraId, response.data.data)
        }
        set({ detectionEvents: new Map(current) })
      }
    } catch (error) {
      console.error('Failed to fetch detection events:', error)
    }
  },

  addCamera: async (name, sourceType, connectionUri, resolution = 'default', recordEnabled = false, recordDurationSeconds = 60) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.addCamera({
        name,
        sourceType,
        connectionUri,
        resolution,
        recordEnabled,
        recordDurationSeconds,
      })
      if (response.success && response.data) {
        const newCamera = response.data as Camera
        set(state => ({
          cameras: [...state.cameras, newCamera],
          isLoading: false,
        }))
      } else {
        set({ error: response.error, isLoading: false })
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to add camera', isLoading: false })
    }
  },

  removeCamera: async (cameraId) => {
    try {
      const response = await apiClient.removeCamera(cameraId)
      if (response.success) {
        set(state => ({
          cameras: state.cameras.filter(c => c.id !== cameraId),
        }))
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to remove camera' })
    }
  },

  acknowledgeEvent: async (eventId) => {
    try {
      await apiClient.acknowledgeMyEvent(eventId)
    } catch (error) {
      console.error('Failed to acknowledge event:', error)
    }
  },

  updateCameraStatus: (cameraId, status) => {
    set(state => ({
      cameras: state.cameras.map(c => (c.id === cameraId ? { ...c, status } : c)),
    }))
  },

  addDetectionEvent: (cameraId, event) => {
    set(state => {
      const events = state.detectionEvents.get(cameraId) || []
      return {
        detectionEvents: new Map(state.detectionEvents).set(cameraId, [event, ...events].slice(0, 50)),
      }
    })
  },

  setFrame: (cameraId, frame, detections) => {
    set(state => ({
      cameraFrames: { ...state.cameraFrames, [cameraId]: frame },
      cameraDetections: { ...state.cameraDetections, [cameraId]: detections },
    }))
  },
}))

if (typeof window !== 'undefined') {
  // Listen for global camera status events or alert broadcasts if any
  wsClient.registerHandler('camera_status', (data: any) => {
    useCameraStore.getState().updateCameraStatus(data.camera_id, data.status)
  })
}
