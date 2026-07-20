'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/lib/store/auth-store'
import { useCameraStore } from '@/lib/store/camera-store'
import { useUIStore } from '@/lib/store/ui-store'
import { apiClient } from '@/lib/api-client'
import { NavSidebar } from '@/components/nav-sidebar'
import { ROIEditor } from '@/components/roi-editor'
import { 
  Video, Users, Shield, Bell, Settings, Plus, Trash, Check, X, 
  RefreshCw, Power, Sliders, Calendar, Map, KeyRound, AlertTriangle, Edit,
  Download
} from 'lucide-react'

const COCO_CLASSES = [
  'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
  'cat', 'dog', 'horse', 'sheep', 'cow', 'backpack', 'umbrella', 'handbag', 'suitcase',
  'bottle', 'cup', 'chair', 'couch', 'potted plant', 'tv', 'laptop', 'cell phone', 'book'
]

export default function AdminDashboard() {
  const { user, logout, role } = useAuthStore()
  const { cameras, fetchCameras } = useCameraStore()
  const { addNotification } = useUIStore()

  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'cameras' | 'models' | 'users' | 'alerts' | 'settings'>('cameras')
  
  
  const [users, setUsers] = useState<any[]>([])
  const [aiModels, setAIModels] = useState<any[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [sysConfig, setSysConfig] = useState<any>({ hostname: '', port: 8443, inference_device: 'auto', record_on_event: false })

  
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [editingCameraId, setEditingCameraId] = useState<string | null>(null)
  const [cameraForm, setCameraForm] = useState({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
  const [usbDevices, setUsbDevices] = useState<{ id: string, name: string, path: string, type: string }[]>([])
  const [detectingUsb, setDetectingUsb] = useState(false)
  const [usbErrorText, setUsbErrorText] = useState<string | null>(null)
  const [uploadingVideo, setUploadingVideo] = useState(false)
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null)

  
  const [showAddUser, setShowAddUser] = useState(false)
  const [userForm, setUserForm] = useState({ username: '', password: '', role: 'user' })

  
  const [selectedCamForModel, setSelectedCamForModel] = useState<string | null>(null)
  const [cameraModelLinks, setCameraModelLinks] = useState<any[]>([])
  const [editingLink, setEditingLink] = useState<any | null>(null)
  const [showROIEditor, setShowROIEditor] = useState(false)

  const loadAllData = async () => {
    try {
      await fetchCameras()
      
      const usersRes = await apiClient.getUsers()
      if (usersRes.success && usersRes.data) setUsers(usersRes.data)

      const modelsRes = await apiClient.getAIModels()
      if (modelsRes.success && modelsRes.data) setAIModels(modelsRes.data)

      const eventsRes = await apiClient.getMyEvents({ limit: 30 })
      if (eventsRes.success && eventsRes.data) setEvents(eventsRes.data.data)

      try {
        const configRes = await apiClient.getSystemConfig()
        if (configRes.success && configRes.data) setSysConfig(configRes.data)
      } catch (configErr) {
        
      }
    } catch (err) {
      console.error('Failed to load admin data:', err)
    }
  }

  const handleSaveConfig = async () => {
    const res = await apiClient.updateSystemConfig(sysConfig)
    if (res.success) {
      addNotification({ type: 'success', message: 'System configuration updated successfully', duration: 3000 })
      await loadAllData()
    } else {
      alert(res.error || 'Failed to save config')
    }
  }

  const handleDownloadBackup = async () => {
    const res = await apiClient.downloadBackup()
    if (res.success && res.data) {
      const url = window.URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `edge_drishti_backup_${new Date().toISOString().slice(0, 10)}.db`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }
  }

  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        window.location.href = '/'
        return
      }
      await loadAllData()
      setIsLoading(false)
    }
    init()
  }, [])

  const handleSourceTypeChange = async (type: string) => {
    setCameraForm(prev => ({ ...prev, sourceType: type, connectionUri: type === 'webcam' ? '0' : '' }))
    setUsbErrorText(null)
    setUploadedFilename(null)
    
    if (type === 'usb' || type === 'capture_card') {
      setDetectingUsb(true)
      try {
        const res = await apiClient.detectUsbDevices()
        if (res.success && Array.isArray(res.data)) {
          const filtered = res.data.filter((d: any) => d.type === (type === 'usb' ? 'camera' : 'capture_card'))
          setUsbDevices(filtered)
          if (filtered.length > 0) {
            setCameraForm(prev => ({ ...prev, connectionUri: filtered[0].path }))
          } else {
            setUsbErrorText(type === 'usb' ? 'No USB cameras found.' : 'No USB capture cards found.')
            setCameraForm(prev => ({ ...prev, connectionUri: '' }))
          }
        } else {
          setUsbErrorText('Failed to detect devices.')
        }
      } catch (err) {
        setUsbErrorText('Failed to detect devices.')
      } finally {
        setDetectingUsb(false)
      }
    }
  }

  const handleVideoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setUploadingVideo(true)
    setUploadedFilename(null)
    try {
      const res = await apiClient.uploadCameraVideo(file)
      if (res.success && res.data?.path) {
        setCameraForm(prev => ({ ...prev, connectionUri: res.data.path }))
        setUploadedFilename(file.name)
      } else {
        alert(res.error || 'Failed to upload video')
      }
    } catch (err) {
      alert('Video upload failed')
    } finally {
      setUploadingVideo(false)
    }
  }

  
  const handleAddCamera = async () => {
    let uri = cameraForm.connectionUri
    if (cameraForm.sourceType === 'webcam' && !uri) {
      uri = '0'
    }
    if (!cameraForm.name || !uri) {
      alert('Camera name and URI/File/Port are required')
      return
    }
    try {
      if (editingCameraId) {
        const res = await apiClient.updateCamera(editingCameraId, {
          name: cameraForm.name,
          sourceType: cameraForm.sourceType,
          connectionUri: uri,
          resolution: cameraForm.resolution,
          recordEnabled: cameraForm.recordEnabled,
          recordDurationSeconds: cameraForm.recordDurationSeconds,
        })
        if (res.success) {
          addNotification({ type: 'success', message: 'Camera settings updated successfully', duration: 3000 })
          setCameraForm({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
          setUploadedFilename(null)
          setUsbDevices([])
          setUsbErrorText(null)
          setShowAddCamera(false)
          setEditingCameraId(null)
          await loadAllData()
        } else {
          alert(res.error || 'Failed to update camera')
        }
      } else {
        const res = await apiClient.addCamera({
          ...cameraForm,
          connectionUri: uri,
        })
        if (res.success) {
          addNotification({ type: 'success', message: 'Camera registered successfully', duration: 3000 })
          setCameraForm({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
          setUploadedFilename(null)
          setUsbDevices([])
          setUsbErrorText(null)
          setShowAddCamera(true)
          setEditingCameraId(null)
          await loadAllData()
        } else {
          alert(res.error || 'Failed to add camera')
        }
      }
    } catch (err) {
      addNotification({ type: 'error', message: editingCameraId ? 'Update camera failed' : 'Add camera failed', duration: 3000 })
    }
  }

  const handleEditCamera = (camera: any) => {
    setCameraForm({
      name: camera.name,
      sourceType: camera.sourceType,
      connectionUri: camera.connectionUri || '',
      resolution: camera.resolution || 'default',
      recordEnabled: camera.recordEnabled || false,
      recordDurationSeconds: camera.recordDurationSeconds || 60,
    })
    setEditingCameraId(camera.id)
    setShowAddCamera(true)
  }

  const handleRemoveCamera = async (id: string) => {
    if (confirm('Are you sure you want to delete this camera? All active analysis loops will stop.')) {
      const res = await apiClient.removeCamera(id)
      if (res.success) {
        addNotification({ type: 'success', message: 'Camera removed', duration: 3000 })
        await loadAllData()
      }
    }
  }

  const handleRestartCamera = async (id: string) => {
    const res = await apiClient.restartCamera(id)
    if (res.success) {
      addNotification({ type: 'success', message: 'Inference thread restarted', duration: 3000 })
      await loadAllData()
    }
  }

  
  const handleAddUser = async () => {
    if (!userForm.username || !userForm.password) {
      alert('Username and password are required')
      return
    }
    const res = await apiClient.addUser(userForm)
    if (res.success) {
      addNotification({ type: 'success', message: 'User added successfully', duration: 3000 })
      setUserForm({ username: '', password: '', role: 'user' })
      setShowAddUser(false)
      const uRes = await apiClient.getUsers()
      if (uRes.success && uRes.data) setUsers(uRes.data)
    } else {
      alert(res.error || 'Failed to create user')
    }
  }

  const handleRemoveUser = async (id: string) => {
    if (confirm('Delete this user?')) {
      const res = await apiClient.removeUser(id)
      if (res.success) {
        addNotification({ type: 'success', message: 'User removed', duration: 3000 })
        const uRes = await apiClient.getUsers()
        if (uRes.success && uRes.data) setUsers(uRes.data)
      }
    }
  }

  const handleReenableUser = async (id: string) => {
    const res = await apiClient.reEnableUser(id)
    if (res.success) {
      addNotification({ type: 'success', message: 'User account re-enabled', duration: 3000 })
      const uRes = await apiClient.getUsers()
      if (uRes.success && uRes.data) setUsers(uRes.data)
    }
  }

  
  const handleSelectCamForModel = async (camId: string) => {
    setSelectedCamForModel(camId)
    setEditingLink(null)
    const res = await apiClient.getCameraModels(camId)
    if (res.success && res.data) {
      setCameraModelLinks(res.data)
    }
  }

  const handleToggleModelLink = async (link: any, enabled: boolean) => {
    const payload = {
      enabled,
      sensitivityConfig: link.sensitivityConfig,
      roiZones: link.roiZones,
      schedule: link.schedule
    }
    const res = await apiClient.updateCameraModel(selectedCamForModel!, link.modelId, payload)
    if (res.success) {
      addNotification({ type: 'success', message: 'Model configuration saved', duration: 3000 })
      handleSelectCamForModel(selectedCamForModel!)
    }
  }

  const handleSaveSensitivity = async () => {
    if (!editingLink) return
    const res = await apiClient.updateCameraModel(selectedCamForModel!, editingLink.modelId, {
      enabled: editingLink.enabled,
      sensitivityConfig: editingLink.sensitivityConfig,
      roiZones: editingLink.roiZones,
      schedule: editingLink.schedule
    })
    if (res.success) {
      addNotification({ type: 'success', message: 'Sensitivity settings applied', duration: 3000 })
      setEditingLink(null)
      handleSelectCamForModel(selectedCamForModel!)
    }
  }

  const handleSaveROI = async (zones: any[][]) => {
    if (!editingLink) return
    const updatedLink = { ...editingLink, roiZones: zones }
    const res = await apiClient.updateCameraModel(selectedCamForModel!, editingLink.modelId, {
      enabled: editingLink.enabled,
      sensitivityConfig: editingLink.sensitivityConfig,
      roiZones: zones,
      schedule: editingLink.schedule
    })
    if (res.success) {
      addNotification({ type: 'success', message: 'ROI configuration updated', duration: 3000 })
      setShowROIEditor(false)
      setEditingLink(null)
      handleSelectCamForModel(selectedCamForModel!)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-orange-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-extrabold text-white">Administrator Console</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Global configuration, camera routing, and neural model settings.</p>
          </div>
          {role === 'master_admin' && (
            <button
              onClick={handleDownloadBackup}
              className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 px-3.5 py-2 rounded-xl text-xs font-semibold text-zinc-300 transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>Download DB Backup</span>
            </button>
          )}
        </div>

        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between shadow-md">
            <div>
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Monitored streams</span>
              <p className="text-2xl font-black mt-1 text-white">{cameras.length}</p>
            </div>
            <Video className="w-8 h-8 text-orange-500/80" />
          </div>

          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between shadow-md">
            <div>
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Registered Users</span>
              <p className="text-2xl font-black mt-1 text-white">{users.length}</p>
            </div>
            <Users className="w-8 h-8 text-blue-500/80" />
          </div>

          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between shadow-md">
            <div>
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Neural Engines</span>
              <p className="text-2xl font-black mt-1 text-white">{aiModels.length}</p>
            </div>
            <Shield className="w-8 h-8 text-green-500/80" />
          </div>
        </div>

        
        <div className="flex gap-2 bg-zinc-950 border border-zinc-800 p-1.5 rounded-xl text-xs font-semibold max-w-xl w-full">
          {(['cameras', 'models', 'users', 'alerts', 'settings'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 rounded-lg capitalize transition-colors ${
                activeTab === tab ? 'bg-orange-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tab === 'settings' ? 'Socket Parameters' : tab}
            </button>
          ))}
        </div>

        
        {activeTab === 'cameras' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Camera Management</h2>
              <button
                onClick={() => {
                  setEditingCameraId(null)
                  setCameraForm({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
                  setShowAddCamera(!showAddCamera)
                }}
                className="flex items-center gap-1 bg-orange-600 hover:bg-orange-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Register Camera</span>
              </button>
            </div>

            {showAddCamera && (
              <div className="bg-zinc-900/60 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 max-w-lg">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  {editingCameraId ? 'Edit Camera Settings' : 'New Camera Source'}
                </h3>
                
                <div className="flex flex-col gap-3">
                  <input
                    type="text"
                    placeholder="Display Name (e.g., Front Gate)"
                    value={cameraForm.name}
                    onChange={(e) => setCameraForm({ ...cameraForm, name: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  <select
                    value={cameraForm.sourceType}
                    onChange={(e) => handleSourceTypeChange(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                  >
                    <option value="rtsp">RTSP Network Stream</option>
                    <option value="webcam">Built-in Webcam</option>
                    <option value="usb">USB Camera</option>
                    <option value="capture_card">USB Capture Card</option>
                    <option value="http">HTTP MJPEG Stream</option>
                    <option value="local_file">Local Video File</option>
                  </select>

                  {cameraForm.sourceType === 'webcam' && (
                    <div className="bg-zinc-950 border border-zinc-805 rounded-xl px-4 py-3 text-xs text-zinc-400">
                      Using built-in camera (Device Index <span className="text-white font-mono font-bold">0</span>)
                    </div>
                  )}

                  {(cameraForm.sourceType === 'usb' || cameraForm.sourceType === 'capture_card') && (
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] text-zinc-500 uppercase tracking-wider">
                          Select {cameraForm.sourceType === 'usb' ? 'USB Camera' : 'USB Capture Card'} Port
                        </label>
                        <button
                          type="button"
                          onClick={() => handleSourceTypeChange(cameraForm.sourceType)}
                          disabled={detectingUsb}
                          className="text-[10px] text-orange-500 hover:text-orange-400 disabled:text-zinc-600 font-semibold"
                        >
                          {detectingUsb ? 'Scanning...' : 'Rescan Ports'}
                        </button>
                      </div>
                      
                      {usbErrorText ? (
                        <div className="bg-red-950/20 border border-red-900/50 rounded-xl px-4 py-3 text-xs text-red-400">
                          {usbErrorText}
                        </div>
                      ) : (
                        <select
                          value={cameraForm.connectionUri}
                          onChange={(e) => setCameraForm({ ...cameraForm, connectionUri: e.target.value })}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                        >
                          {usbDevices.map((dev) => (
                            <option key={dev.id} value={dev.path}>
                              {dev.name} ({dev.path})
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}

                  {cameraForm.sourceType === 'local_file' && (
                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-500 uppercase tracking-wider">
                        Select Local Video File
                      </label>
                      <div className="relative">
                        <input
                          type="file"
                          accept="video/*"
                          onChange={handleVideoFileChange}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none file:mr-4 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-[10px] file:font-semibold file:bg-zinc-800 file:text-white hover:file:bg-zinc-700 file:cursor-pointer"
                        />
                      </div>
                      {uploadingVideo && (
                        <span className="text-[10px] text-orange-400 animate-pulse">Uploading video file to server...</span>
                      )}
                      {uploadedFilename && (
                        <span className="text-[10px] text-green-400">✓ Uploaded: {uploadedFilename}</span>
                      )}
                    </div>
                  )}

                  {(cameraForm.sourceType === 'rtsp' || cameraForm.sourceType === 'http') && (
                    <input
                      type="text"
                      placeholder={cameraForm.sourceType === 'rtsp' ? "RTSP Connection URI (e.g. rtsp://192.168.1.100/stream)" : "HTTP MJPEG Stream URL (e.g. http://192.168.1.100:8080/video)"}
                      value={cameraForm.connectionUri}
                      onChange={(e) => setCameraForm({ ...cameraForm, connectionUri: e.target.value })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                    />
                  )}

                  <select
                    value={cameraForm.resolution}
                    onChange={(e) => setCameraForm({ ...cameraForm, resolution: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                  >
                    <option value="default">Default</option>
                    <option value="4k">4k</option>
                    <option value="2k">2k</option>
                    <option value="1080">1080</option>
                    <option value="720">720</option>
                    <option value="480">480</option>
                    <option value="240">240</option>
                  </select>
                  {editingCameraId && (
                    <div className="flex flex-col gap-3">
                      <label className="flex items-center gap-2 text-xs text-zinc-300">
                        <input
                          type="checkbox"
                          checked={cameraForm.recordEnabled}
                          onChange={(e) => setCameraForm({ ...cameraForm, recordEnabled: e.target.checked })}
                          className="w-4 h-4 rounded border-zinc-800 bg-zinc-950 text-orange-600 focus:ring-0"
                        />
                        Record video for this camera when AI triggers detection
                      </label>
                      {cameraForm.recordEnabled && (
                        <input
                          type="number"
                          min={20}
                          placeholder="Recording duration in seconds"
                          value={cameraForm.recordDurationSeconds}
                          onChange={(e) => setCameraForm({ ...cameraForm, recordDurationSeconds: Number(e.target.value) })}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white focus:outline-none"
                        />
                      )}
                    </div>
                  )}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleAddCamera}
                      className="flex-1 bg-orange-600 hover:bg-orange-500 text-white py-2 rounded-xl text-xs font-semibold"
                    >
                      {editingCameraId ? 'Update Camera' : 'Save Camera'}
                    </button>
                    <button
                      onClick={() => {
                        setShowAddCamera(false)
                        setEditingCameraId(null)
                        setCameraForm({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
                      }}
                      className="flex-1 bg-zinc-850 hover:bg-zinc-800 text-zinc-400 py-2 rounded-xl text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {cameras.map(camera => (
                <div key={camera.id} className="flex justify-between items-center bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl hover:border-zinc-700 transition-colors">
                  <div>
                    <h3 className="text-xs font-bold text-white">{camera.name}</h3>
                    <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">
                      {camera.sourceType} • Resolution: {camera.resolution} • Recording: {camera.recordEnabled ? `${camera.recordDurationSeconds}s` : 'Disabled'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEditCamera(camera)}
                      className="p-2 rounded-lg bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-white transition-colors"
                      title="Edit camera settings"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleRestartCamera(camera.id)}
                      className="p-2 rounded-lg bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-white transition-colors"
                      title="Restart ingestion worker"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleRemoveCamera(camera.id)}
                      className="p-2 rounded-lg bg-red-950/20 border border-red-900/30 text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete camera"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        
        {activeTab === 'models' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-zinc-900 pb-3">AI Model Configurations</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
              
              <div className="md:col-span-1 flex flex-col gap-2">
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-1">Select camera:</span>
                {cameras.map(c => (
                  <button
                    key={c.id}
                    onClick={() => handleSelectCamForModel(c.id)}
                    className={`text-left px-3.5 py-2.5 rounded-xl border text-xs font-semibold transition-colors ${
                      selectedCamForModel === c.id
                        ? 'bg-orange-950/20 border-orange-500 text-orange-200'
                        : 'bg-zinc-900 border-zinc-850 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>

              
              <div className="md:col-span-2 flex flex-col gap-4">
                {selectedCamForModel ? (
                  <>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Models config:</span>
                    
                    {showROIEditor && editingLink ? (
                      <ROIEditor
                        initialZones={editingLink.roiZones || []}
                        onSave={handleSaveROI}
                        onCancel={() => setShowROIEditor(false)}
                      />
                    ) : editingLink ? (
                      
                      <div className="bg-zinc-900 border border-zinc-800 p-5 rounded-2xl flex flex-col gap-4">
                        <div className="flex justify-between items-center">
                          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Sensitivity: {editingLink.displayName}</h3>
                          <button onClick={() => setEditingLink(null)} className="text-zinc-500 hover:text-zinc-300">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        <div className="flex flex-col gap-2">
                          <span className="text-xs text-zinc-400">Confidence Threshold: {Math.round((editingLink.sensitivityConfig?.confidence_threshold || 0.5) * 100)}%</span>
                          <input
                            type="range"
                            min="0.1"
                            max="0.95"
                            step="0.05"
                            value={editingLink.sensitivityConfig?.confidence_threshold || 0.5}
                            onChange={(e) => setEditingLink({
                              ...editingLink,
                              sensitivityConfig: {
                                ...editingLink.sensitivityConfig,
                                confidence_threshold: parseFloat(e.target.value)
                              }
                            })}
                            className="w-full accent-orange-600 bg-zinc-955"
                          />
                        </div>
                        {['object', 'vehicle', 'animal'].includes(editingLink.modelKey) && (() => {
                          const matchingModel = aiModels.find(m => m.key === editingLink.modelKey)
                          const fallbackClasses = 
                            editingLink.modelKey === 'vehicle' ? ['bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat'] :
                            editingLink.modelKey === 'animal' ? ['bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe'] :
                            COCO_CLASSES
                          const availableClasses = matchingModel?.allowedClasses || fallbackClasses
                          return (
                            <div className="flex flex-col gap-2">
                              <span className="text-xs text-zinc-400">Classes to Detect:</span>
                              <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto bg-zinc-955 p-3 rounded-xl border border-zinc-800">
                                {availableClasses.map(cls => {
                                  const selectedClasses = editingLink.sensitivityConfig?.classes || []
                                  const isChecked = selectedClasses.includes(cls)
                                  return (
                                    <label key={cls} className="flex items-center gap-2 cursor-pointer select-none text-[11px] text-zinc-300 hover:text-white">
                                      <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={(e) => {
                                          const newClasses = e.target.checked
                                            ? [...selectedClasses, cls]
                                            : selectedClasses.filter((c: string) => c !== cls)
                                          setEditingLink({
                                            ...editingLink,
                                            sensitivityConfig: {
                                              ...editingLink.sensitivityConfig,
                                              classes: newClasses
                                            }
                                          })
                                        }}
                                        className="w-3.5 h-3.5 rounded border-zinc-800 bg-zinc-900 text-orange-600 focus:ring-0"
                                      />
                                      <span className="capitalize">{cls}</span>
                                    </label>
                                  )
                                })}
                              </div>
                              <span className="text-[10px] text-zinc-500">Note: If no classes are selected, all allowed classes will be detected.</span>
                            </div>
                          )
                        })()}

                        <div className="flex items-center gap-2 py-1 select-none cursor-pointer">
                          <input
                            type="checkbox"
                            id="record_on_detect"
                            checked={!!editingLink.sensitivityConfig?.record_on_detect}
                            onChange={(e) => setEditingLink({
                              ...editingLink,
                              sensitivityConfig: {
                                ...editingLink.sensitivityConfig,
                                record_on_detect: e.target.checked
                              }
                            })}
                            className="w-3.5 h-3.5 rounded border-zinc-800 bg-zinc-900 text-orange-650 focus:ring-0 cursor-pointer"
                          />
                          <label htmlFor="record_on_detect" className="text-xs text-zinc-300 cursor-pointer">
                            Record Video on Detection (15s pre-buffer, 15s post-detection)
                          </label>
                        </div>

                        <button
                          onClick={handleSaveSensitivity}
                          className="bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold py-2 rounded-xl"
                        >
                          Apply Sensitivity
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {cameraModelLinks.map(link => (
                          <div key={link.linkId} className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl flex flex-col gap-3">
                            <div className="flex justify-between items-center">
                              <div>
                                <h3 className="text-xs font-bold text-white">{link.displayName}</h3>
                                <p className="text-[10px] text-zinc-500 mt-0.5">Global key: {link.modelKey}</p>
                              </div>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={link.enabled}
                                  onChange={(e) => handleToggleModelLink(link, e.target.checked)}
                                  className="w-4 h-4 rounded border-zinc-800 bg-zinc-950 text-orange-600 focus:ring-0"
                                />
                                <span className="text-xs text-zinc-400">Enabled</span>
                              </label>
                            </div>

                            {link.enabled && (
                              <div className="flex gap-2 border-t border-zinc-900 pt-3 text-[10px] font-bold uppercase tracking-wider">
                                <button
                                  onClick={() => setEditingLink(link)}
                                  className="flex items-center gap-1 bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-white px-2.5 py-1.5 rounded-lg transition-colors"
                                >
                                  <Sliders className="w-3.5 h-3.5" />
                                  <span>Sensitivity</span>
                                </button>
                                <button
                                  onClick={() => {
                                    setEditingLink(link)
                                    setShowROIEditor(true)
                                  }}
                                  className="flex items-center gap-1 bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-white px-2.5 py-1.5 rounded-lg transition-colors"
                                >
                                  <Map className="w-3.5 h-3.5" />
                                  <span>Configure Zones</span>
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-12 text-zinc-500 text-xs border border-dashed border-zinc-800 rounded-2xl">
                    Select a camera on the left to configure AI engine triggers.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        
        {activeTab === 'users' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">User Account Management</h2>
              <button
                onClick={() => setShowAddUser(!showAddUser)}
                className="flex items-center gap-1 bg-orange-600 hover:bg-orange-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Create Account</span>
              </button>
            </div>

            {showAddUser && (
              <div className="bg-zinc-900/60 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 max-w-lg">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">New User Account</h3>
                <div className="flex flex-col gap-3">
                  <input
                    type="text"
                    placeholder="Username"
                    value={userForm.username}
                    onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white focus:outline-none"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={userForm.password}
                    onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white focus:outline-none"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleAddUser}
                      className="flex-1 bg-orange-600 hover:bg-orange-500 text-white py-2 rounded-xl text-xs font-semibold"
                    >
                      Save Account
                    </button>
                    <button
                      onClick={() => setShowAddUser(false)}
                      className="flex-1 bg-zinc-850 hover:bg-zinc-800 text-zinc-400 py-2 rounded-xl text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {users.map(u => (
                <div key={u.id} className="flex justify-between items-center bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl hover:border-zinc-700 transition-colors">
                  <div>
                    <h3 className="text-xs font-bold text-white">{u.username}</h3>
                    <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">Role: {u.role} • Status: {u.status}</p>
                  </div>
                  <div className="flex gap-2">
                    {u.status === 'disabled' && (
                      <button
                        onClick={() => handleReenableUser(u.id)}
                        className="px-2.5 py-1.5 rounded-lg bg-green-950/20 border border-green-900/40 text-green-400 hover:bg-green-950/40 text-[10px] font-bold uppercase tracking-wider transition-colors"
                      >
                        Re-Enable
                      </button>
                    )}
                    <button
                      onClick={() => handleRemoveUser(u.id)}
                      className="p-2 rounded-lg bg-red-950/20 border border-red-900/30 text-red-400 hover:bg-red-950/40 transition-colors"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        
        {activeTab === 'alerts' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-4 text-xs">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-zinc-900 pb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              <span>External Alert dispatch Config</span>
            </h2>
            <p className="text-zinc-400 leading-relaxed max-w-lg">
              External dispatch channels like Telegram Bot credentials and SMS configurations affect core platform security. They can only be adjusted from the host device via the <strong>Master Admin Console</strong>.
            </p>
            <p className="text-zinc-500">
              Please contact the local systems administrator or access the Master Panel on the host device at <code>https://127.0.0.1:8443/master-admin</code> to modify alert channels.
            </p>
          </div>
        )}

        
        {activeTab === 'settings' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-zinc-900 pb-3 flex items-center gap-2">
              <Settings className="w-4 h-4 text-orange-500" />
              <span>Socket parameters</span>
            </h2>

            {role !== 'master_admin' ? (
              <div className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-xl text-xs text-orange-400 max-w-lg leading-relaxed">
                <strong>Access Restricted:</strong> Socket parameters affect host-level bindings and ports. They can only be modified when accessed by the <strong>Master Admin</strong>.
              </div>
            ) : (
              <div className="bg-zinc-900/60 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 max-w-lg">
                <div className="flex flex-col gap-3">
                  <div>
                    <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-2">Internal Host Bind</label>
                    <input
                      type="text"
                      value={sysConfig.hostname}
                      onChange={(e) => setSysConfig({ ...sysConfig, hostname: e.target.value })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-2">TLS Port Bind</label>
                    <input
                      type="number"
                      value={sysConfig.port}
                      onChange={(e) => setSysConfig({ ...sysConfig, port: Number(e.target.value) })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-2">Global Compute Engine Mode</label>
                    <select
                      value={sysConfig.inference_device}
                      onChange={(e) => setSysConfig({ ...sysConfig, inference_device: e.target.value })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="auto">Auto-detect (Recommended)</option>
                      <option value="cuda">Force NVIDIA CUDA</option>
                      <option value="cpu">Force CPU Fallback</option>
                      <option value="openvino">Force Intel OpenVINO</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2 py-1 select-none cursor-pointer">
                    <input
                      type="checkbox"
                      id="record_on_event"
                      checked={sysConfig.record_on_event}
                      onChange={(e) => setSysConfig({ ...sysConfig, record_on_event: e.target.checked })}
                      className="w-4 h-4 rounded border-zinc-800 bg-zinc-950 text-orange-655 focus:ring-0 cursor-pointer animate-pulse"
                    />
                    <label htmlFor="record_on_event" className="text-xs text-zinc-300 cursor-pointer">
                      Record Video on Threat Detection (15s pre-buffer, 15s post-detection)
                    </label>
                  </div>
                  <button
                    onClick={handleSaveConfig}
                    className="bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold py-2.5 rounded-xl transition-all shadow-md mt-2"
                  >
                    Apply Configuration
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
