'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { apiClient, User } from '@/lib/api-client'
import { useAuthStore } from '@/lib/store/auth-store'
import { useUIStore } from '@/lib/store/ui-store'
import { useCameraStore } from '@/lib/store/camera-store'
import { NavSidebar } from '@/components/nav-sidebar'
import { 
  ShieldAlert, Settings, Users, History, Key, Check, X, Shield, 
  Trash, Plus, Download, RefreshCw, Cpu, PhoneCall, AlertTriangle, UserCheck,
  Video, Edit
} from 'lucide-react'

export default function MasterAdminDashboard() {
  const router = useRouter()
  const { logout } = useAuthStore()
  const { addNotification } = useUIStore()
  const { cameras, fetchCameras } = useCameraStore()

  const [activeTab, setActiveTab] = useState<'config' | 'accounts' | 'audit' | 'contacts' | 'faces' | 'lockdown' | 'cameras'>('config')
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<any>(null)

  
  const [sysConfig, setSysConfig] = useState<any>({ hostname: '', port: 8443, inference_device: 'auto', record_on_event: false })
  const [hardware, setHardware] = useState<any>({})

  
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [editingCameraId, setEditingCameraId] = useState<string | null>(null)
  const [cameraForm, setCameraForm] = useState({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
  const [usbDevices, setUsbDevices] = useState<{ id: string, name: string, path: string, type: string }[]>([])
  const [detectingUsb, setDetectingUsb] = useState(false)
  const [usbErrorText, setUsbErrorText] = useState<string | null>(null)
  const [uploadingVideo, setUploadingVideo] = useState(false)
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null)

  
  const [accounts, setAccounts] = useState<User[]>([])
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [accountForm, setAccountForm] = useState({ type: 'user', username: '', password: '', pin: '' })

  
  const [contacts, setContacts] = useState<any[]>([])
  const [showAddContact, setShowAddContact] = useState(false)
  const [contactForm, setContactForm] = useState({ name: '', channel: 'telegram', bot_token: '', chat_id: '' })


  
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [auditTotal, setAuditTotal] = useState(0)
  const [auditOffset, setAuditOffset] = useState(0)
  const [integrityStatus, setIntegrityStatus] = useState<string | null>(null)

  
  const [recoveryStatus, setRecoveryStatus] = useState<any>({})
  const [newGeneratedKey, setNewGeneratedKey] = useState('')

  const searchParams = useSearchParams()

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && ['config', 'accounts', 'audit', 'contacts', 'faces', 'lockdown', 'cameras'].includes(tab)) {
      setActiveTab(tab as any)
    } else if (!tab) {
      setActiveTab('config')
    }
  }, [searchParams])

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await apiClient.request('/api/admin/system/stats')
        if (res.success && res.data) {
          setStats(res.data)
        }
      } catch (err) {
        console.error('Failed to fetch system stats:', err)
      }
    }
    fetchStats()
    const statsInterval = setInterval(fetchStats, 5000)
    return () => clearInterval(statsInterval)
  }, [])

  const loadAll = async () => {
    try {
      await fetchCameras()

      const configRes = await apiClient.getSystemConfig()
      if (configRes.success && configRes.data) setSysConfig(configRes.data)

      const hwRes = await apiClient.getSystemHardware()
      if (hwRes.success && hwRes.data) setHardware(hwRes.data)

      const adminRes = await apiClient.getAdmins()
      const userRes = await apiClient.getUsers()
      const combined = []
      if (adminRes.success && adminRes.data) combined.push(...adminRes.data)
      if (userRes.success && userRes.data) combined.push(...userRes.data)
      setAccounts(combined)

      const contactRes = await apiClient.getAlertContacts()
      if (contactRes.success && contactRes.data) setContacts(contactRes.data)


      const auditRes = await apiClient.getAuditLog({ limit: 50, offset: auditOffset })
      if (auditRes.success && auditRes.data) {
        setAuditLogs(auditRes.data.data)
        setAuditTotal(auditRes.data.total)
      }

      const recRes = await apiClient.getRecoveryKeyStatus()
      if (recRes.success && recRes.data) setRecoveryStatus(recRes.data)
    } catch (err) {
      console.error('Failed to load master console data:', err)
    }
  }

  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        router.push('/')
        return
      }
      await loadAll()
      setLoading(false)
    }
    init()
  }, [auditOffset])

  
  const handleSaveConfig = async () => {
    const res = await apiClient.updateSystemConfig(sysConfig)
    if (res.success) {
      addNotification({ type: 'success', message: 'System configuration updated successfully', duration: 3000 })
      await loadAll()
    } else {
      alert(res.error || 'Failed to save config')
    }
  }

  
  const handleCreateAccount = async () => {
    if (!accountForm.username || !accountForm.password) {
      alert('Username and password are required')
      return
    }
    if (accountForm.type === 'admin' && !accountForm.pin) {
      alert('PIN is required for admin accounts')
      return
    }

    const res = accountForm.type === 'admin'
      ? await apiClient.createAdmin({ username: accountForm.username, password: accountForm.password, pin: accountForm.pin })
      : await apiClient.addUser({ username: accountForm.username, password: accountForm.password, role: 'user' })

    if (res.success) {
      addNotification({ type: 'success', message: 'Account created successfully', duration: 3000 })
      setAccountForm({ type: 'user', username: '', password: '', pin: '' })
      setShowAddAccount(false)
      await loadAll()
    } else {
      alert(res.error || 'Failed to create account')
    }
  }

  const handleDeleteAccount = async (id: string, role: string) => {
    if (confirm(`Delete this ${role} account?`)) {
      const res = role === 'admin' ? await apiClient.deleteAdmin(id) : await apiClient.removeUser(id)
      if (res.success) {
        addNotification({ type: 'success', message: 'Account deleted', duration: 3000 })
        await loadAll()
      }
    }
  }

  
  const handleVerifyAudit = async () => {
    setIntegrityStatus('Verifying...')
    const res = await apiClient.verifyAuditChain()
    if (res.success && res.data) {
      const report = res.data
      if (report.chain_intact) {
        setIntegrityStatus('INTEGRITY SECURE: SHA-256 hash chain verified with zero mutations.')
      } else {
        setIntegrityStatus(`TAMPER DETECTED: Chain broken at sequence number ${report.first_broken_sequence}!`)
      }
    } else {
      setIntegrityStatus('Verification connection failed.')
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

  const handleRegenRecoveryKey = async () => {
    if (confirm('Regenerate Master Recovery Key? The previous key will be voided.')) {
      const res = await apiClient.regenerateRecoveryKey()
      if (res.success && res.data) {
        setNewGeneratedKey(res.data.recovery_key)
        addNotification({ type: 'success', message: 'Recovery key regenerated', duration: 3000 })
        await loadAll()
      }
    }
  }

  
  const handleAddContact = async () => {
    if (!contactForm.name || !contactForm.bot_token || !contactForm.chat_id) {
      alert('All contact details are required')
      return
    }
    const res = await apiClient.createAlertContact(contactForm)
    if (res.success) {
      addNotification({ type: 'success', message: 'Telegram contact registered', duration: 3000 })
      setContactForm({ name: '', channel: 'telegram', bot_token: '', chat_id: '' })
      setShowAddContact(false)
      await loadAll()
    } else {
      alert(res.error || 'Failed to create contact')
    }
  }

  const handleDeleteContact = async (id: string) => {
    if (confirm('Delete this contact?')) {
      const res = await apiClient.deleteAlertContact(id)
      if (res.success) {
        await loadAll()
      }
    }
  }

  const handleTestContact = async (id: string) => {
    addNotification({ type: 'info', message: 'Sending test dispatch...', duration: 2000 })
    const res = await apiClient.testAlertContact(id)
    if (res.success && res.data?.success) {
      alert('Test alert successfully dispatched to Telegram chat.')
    } else {
      alert(`Test failed: ${res.data?.message || res.error}`)
    }
  }


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
    if (!cameraForm.name) {
      alert('Camera name is required')
      return
    }
    let uri = cameraForm.connectionUri
    if (cameraForm.sourceType === 'webcam' && !uri) {
      uri = '0'
    }
    if (!uri) {
      alert('Connection URI is required')
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
          await loadAll()
        } else {
          alert(res.error || 'Failed to update camera')
        }
      } else {
        const res = await apiClient.addCamera({
          name: cameraForm.name,
          sourceType: cameraForm.sourceType,
          connectionUri: uri,
          resolution: cameraForm.resolution,
          recordEnabled: cameraForm.recordEnabled,
          recordDurationSeconds: cameraForm.recordDurationSeconds,
        })
        if (res.success) {
          addNotification({ type: 'success', message: 'Camera registered successfully', duration: 3000 })
          setCameraForm({ name: '', sourceType: 'rtsp', connectionUri: '', resolution: 'default', recordEnabled: false, recordDurationSeconds: 60 })
          setUploadedFilename(null)
          setUsbDevices([])
          setUsbErrorText(null)
          setShowAddCamera(true)
          setEditingCameraId(null)
          await loadAll()
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
        await loadAll()
      }
    }
  }

  const handleRestartCamera = async (id: string) => {
    const res = await apiClient.restartCamera(id)
    if (res.success) {
      addNotification({ type: 'success', message: 'Inference thread restarted', duration: 3000 })
      await loadAll()
    }
  }

  
  const handleActivateLockdown = async () => {
    if (confirm('WARNING: ACTIVATE SYSTEM LOCKDOWN? All user and admin portals will be immediately locked out.')) {
      const res = await apiClient.activateLockdown()
      if (res.success) {
        addNotification({ type: 'error', message: 'LOCKDOWN ACTIVE: All portals disabled.', duration: 5000 })
      }
    }
  }

  const handleReleaseLockdown = async () => {
    const res = await apiClient.releaseLockdown()
    if (res.success) {
      addNotification({ type: 'success', message: 'Lockdown released. Portals active.', duration: 3000 })
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-red-700 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-black text-white overflow-hidden">
      <NavSidebar />

      <main className="flex-1 flex flex-col p-6 overflow-y-auto max-h-screen gap-6">
        
        <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-4 rounded-2xl shadow-lg">
          <div>
            <h1 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-red-500 animate-pulse" />
              <span>Master Console</span>
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">Critical system parameter dashboard. Authorized localhost access only.</p>
          </div>
        </div>

        
        <div className="flex flex-wrap gap-1.5 bg-zinc-950 border border-zinc-800 p-1.5 rounded-xl text-xs font-semibold w-full">
          {[
            { id: 'config', label: 'Server & Hardware' },
            { id: 'cameras', label: 'Video Source' },
            { id: 'accounts', label: 'Accounts' },
            { id: 'audit', label: 'Hash Audit Logs' },
            { id: 'contacts', label: 'Alerts' },
            { id: 'lockdown', label: 'Security Lockdown' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id as any)
                setNewGeneratedKey('')
              }}
              className={`px-3.5 py-2 rounded-lg transition-colors ${
                activeTab === tab.id ? 'bg-red-700 text-white font-bold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        
        {activeTab === 'config' && (
          <div className="w-full">
            
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col gap-5 w-full">
              <div className="border-b border-zinc-900 pb-3 flex justify-between items-center">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-4.5 h-4.5 text-red-500" />
                  <span>Compute & System Health Report</span>
                </h3>
                {stats && (
                  <span className="text-[10px] bg-red-950/30 border border-red-900/40 text-red-400 font-mono px-2 py-0.5 rounded-md animate-pulse">
                    LIVE MONITORING
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                <div className="flex flex-col gap-3 text-xs leading-relaxed">
                  <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider border-b border-zinc-900 pb-1">System hardware</h4>
                  <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                    <span className="text-zinc-400">Operation System:</span>
                    <span className="text-white font-semibold">{hardware.platform || 'Linux'}</span>
                  </div>
                  <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                    <span className="text-zinc-400">CPU Physical Cores:</span>
                    <span className="text-white font-semibold">{hardware.cpu?.cores_physical || 4}</span>
                  </div>
                  <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                    <span className="text-zinc-400">Installed RAM:</span>
                    <span className="text-white font-semibold">{hardware.ram_gb || 16} GB</span>
                  </div>
                  <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                    <span className="text-zinc-400">Inference Core:</span>
                    <span className="text-white font-bold uppercase text-orange-500">
                      {hardware.inference_device || 'cpu'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">GPU Hardware:</span>
                    <span className="text-white font-semibold truncate max-w-[200px]">
                      {hardware.gpu?.name || 'None detected / CPU Only'}
                    </span>
                  </div>
                </div>

                
                {stats && (
                  <div className="flex flex-col gap-4 text-xs">
                    <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider border-b border-zinc-900 pb-1">Resource utilization</h4>
                    
                    
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-zinc-400">
                        <span>CPU Active Load:</span>
                        <span className="text-white font-bold">{stats.cpu_percent}%</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-red-600 h-full rounded-full transition-all duration-500" 
                          style={{ width: `${stats.cpu_percent}%` }}
                        />
                      </div>
                    </div>

                    
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-zinc-400">
                        <span>RAM Memory Usage:</span>
                        <span className="text-white font-bold">{stats.ram_percent}% ({stats.ram_used_gb} GB / {stats.ram_total_gb} GB)</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-orange-500 h-full rounded-full transition-all duration-500" 
                          style={{ width: `${stats.ram_percent}%` }}
                        />
                      </div>
                    </div>

                    
                    <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                      <span className="text-zinc-400">RAM Memory Free:</span>
                      <span className="text-white font-semibold">{(stats.ram_total_gb - stats.ram_used_gb).toFixed(2)} GB</span>
                    </div>

                    
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-zinc-400">
                        <span>Disk Storage Usage:</span>
                        <span className="text-white font-bold">{stats.disk_percent}% ({stats.disk_used_gb} GB / {stats.disk_total_gb} GB)</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-zinc-700 h-full rounded-full transition-all duration-500" 
                          style={{ width: `${stats.disk_percent}%` }}
                        />
                      </div>
                    </div>

                    {/* GPU Load (if any) */}
                    {stats.gpu && (
                      <div className="flex flex-col gap-1.5 mt-1 border-t border-zinc-900 pt-3">
                        <div className="flex justify-between text-zinc-400">
                          <span>GPU Load:</span>
                          <span className="text-white font-bold">{stats.gpu.utilization_percent}%</span>
                        </div>
                        <div className="flex justify-between text-zinc-400 mt-1">
                          <span>GPU VRAM:</span>
                          <span className="text-white font-bold">{stats.gpu.memory_used_gb} GB / {stats.gpu.memory_total_gb} GB</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        
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
                className="flex items-center gap-1 bg-red-700 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
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
                          className="text-[10px] text-red-500 hover:text-red-400 disabled:text-zinc-600 font-semibold"
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
                        <span className="text-[10px] text-red-400 animate-pulse">Uploading video file to server...</span>
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

                  {editingCameraId && (
                    <>
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
                    </>
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
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleAddCamera}
                      className="flex-1 bg-red-700 hover:bg-red-650 text-white py-2 rounded-xl text-xs font-semibold"
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
              {cameras.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-xs border border-dashed border-zinc-800 rounded-2xl">
                  No cameras registered yet.
                </div>
              ) : (
                cameras.map(camera => (
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
                ))
              )}
            </div>
          </div>
        )}

        
        {activeTab === 'accounts' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">System Accounts</h2>
              <button
                onClick={() => setShowAddAccount(!showAddAccount)}
                className="flex items-center gap-1 bg-red-700 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Create Account</span>
              </button>
            </div>

            {showAddAccount && (
              <div className="bg-zinc-900/60 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 max-w-lg">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">New Account</h3>
                <div className="flex flex-col gap-3">
                  <select
                    value={accountForm.type}
                    onChange={(e) => setAccountForm({ ...accountForm, type: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                  >
                    <option value="user">Regular User (Live Grid View Only)</option>
                    <option value="admin">Administrator (Manage Cameras & Users)</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Username"
                    value={accountForm.username}
                    onChange={(e) => setAccountForm({ ...accountForm, username: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={accountForm.password}
                    onChange={(e) => setAccountForm({ ...accountForm, password: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  {accountForm.type === 'admin' && (
                    <input
                      type="text"
                      placeholder="PIN Code (4-8 digits)"
                      maxLength={8}
                      value={accountForm.pin}
                      onChange={(e) => setAccountForm({ ...accountForm, pin: e.target.value.replace(/\D/g, '') })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none text-center font-mono tracking-wider"
                    />
                  )}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleCreateAccount}
                      className="flex-1 bg-red-700 hover:bg-red-650 text-white py-2 rounded-xl text-xs font-semibold"
                    >
                      Save Account
                    </button>
                    <button
                      onClick={() => setShowAddAccount(false)}
                      className="flex-1 bg-zinc-850 hover:bg-zinc-800 text-zinc-400 py-2 rounded-xl text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {accounts.map(acc => (
                <div key={acc.id} className="flex justify-between items-center bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl hover:border-zinc-700 transition-colors">
                  <div>
                    <h3 className="text-xs font-bold text-white flex items-center gap-2">
                      <UserCheck className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{acc.username}</span>
                    </h3>
                    <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">
                      Role: {acc.role} • Status: {acc.status || 'active'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDeleteAccount(acc.id, acc.role)}
                      className="p-2 rounded-lg bg-red-950/20 border border-red-900/30 text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete account"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        
        {activeTab === 'audit' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">Tamper-Proof Audit logs</h2>
                <p className="text-[10px] text-zinc-400 mt-0.5">SHA-256 hash-chained log verify console.</p>
              </div>
              <button
                onClick={handleVerifyAudit}
                className="flex items-center gap-1.5 bg-red-700 hover:bg-red-600 text-white px-3.5 py-2 rounded-xl text-xs font-semibold transition-all"
              >
                <Shield className="w-3.5 h-3.5" />
                <span>Verify Chain Integrity</span>
              </button>
            </div>

            {integrityStatus && (
              <div className={`p-4 rounded-xl border text-xs font-bold ${
                integrityStatus.includes('SECURE')
                  ? 'bg-green-950/20 border-green-900/40 text-green-400'
                  : 'bg-red-950/20 border-red-900/40 text-red-400'
              }`}>
                {integrityStatus}
              </div>
            )}

            <div className="flex flex-col gap-3">
              {auditLogs.map((log) => (
                <div key={log.id} className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl text-xs flex flex-col gap-2 font-mono">
                  <div className="flex justify-between text-[10px] text-zinc-500">
                    <span>Seq: {log.sequence}</span>
                    <span>{new Date(log.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center text-white text-xs font-sans font-bold">
                    <span>Action: {log.action}</span>
                    <span className="text-[10px] bg-zinc-900 border border-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">
                      Role: {log.actorRole}
                    </span>
                  </div>
                  {log.detail && <p className="text-[11px] text-zinc-400 font-sans">{log.detail}</p>}
                  <div className="text-[9px] text-zinc-600 border-t border-zinc-900/80 pt-1.5 truncate">
                    HASH: {log.rowHash}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        
        {activeTab === 'contacts' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Telegram Alert Contacts</h2>
              <button
                onClick={() => setShowAddContact(!showAddContact)}
                className="flex items-center gap-1 bg-red-700 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Register Contact</span>
              </button>
            </div>

            {showAddContact && (
              <div className="bg-zinc-900/60 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 max-w-lg">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">New Telegram Dispatch</h3>
                <div className="flex flex-col gap-3">
                  <input
                    type="text"
                    placeholder="Contact Name (e.g. Head of Security)"
                    value={contactForm.name}
                    onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  <input
                    type="password"
                    placeholder="Telegram Bot Token"
                    value={contactForm.bot_token}
                    onChange={(e) => setContactForm({ ...contactForm, bot_token: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  <input
                    type="text"
                    placeholder="Telegram Chat / Group ID"
                    value={contactForm.chat_id}
                    onChange={(e) => setContactForm({ ...contactForm, chat_id: e.target.value })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleAddContact}
                      className="flex-1 bg-red-700 hover:bg-red-655 text-white py-2 rounded-xl text-xs font-semibold"
                    >
                      Save Dispatcher
                    </button>
                    <button
                      onClick={() => setShowAddContact(false)}
                      className="flex-1 bg-zinc-855 hover:bg-zinc-800 text-zinc-400 py-2 rounded-xl text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              {contacts.map(c => (
                <div key={c.id} className="flex justify-between items-center bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl hover:border-zinc-700 transition-colors">
                  <div>
                    <h3 className="text-xs font-bold text-white">{c.name}</h3>
                    <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">Channel: {c.channel} • Chat: {c.chatId}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleTestContact(c.id)}
                      className="flex items-center gap-1 bg-zinc-850 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors"
                    >
                      <PhoneCall className="w-3.5 h-3.5" />
                      <span>Test Dispatch</span>
                    </button>
                    <button
                      onClick={() => handleDeleteContact(c.id)}
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

        
        {activeTab === 'lockdown' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-zinc-900 pb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500 animate-bounce" />
              <span>Emergency system lockdown</span>
            </h2>

            <div className="bg-red-950/20 border border-red-900/40 p-4 rounded-xl text-xs text-red-400 leading-relaxed max-w-xl">
              <strong>WARNING:</strong> Triggering lockdown instantly revokes all user sessions and disables access keys for all regular user and administrator roles. Only the local physical master console (this interface) remains active to clear the lockdown.
            </div>

            <div className="flex gap-4">
              <button
                onClick={handleActivateLockdown}
                className="bg-red-700 hover:bg-red-600 text-white font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl transition-all shadow-lg shadow-red-950/30"
              >
                Activate Global Lockdown
              </button>
              <button
                onClick={handleReleaseLockdown}
                className="bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-300 font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl transition-all"
              >
                Release Lockdown
              </button>
            </div>

            
            <div className="bg-zinc-900/40 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 mt-6 max-w-xl">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Key className="w-4 h-4 text-orange-500" />
                <span>Consolidated Recovery Key</span>
              </h3>
              
              <div className="text-xs text-zinc-400 leading-relaxed flex flex-col gap-3">
                <p>Status: {recoveryStatus.used ? 'KEY ALREADY CONSUMED' : 'KEY SECURE (UNUSEDACTIVE)'}</p>
                
                {newGeneratedKey && (
                  <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl font-mono text-center font-bold text-white tracking-widest text-sm select-all">
                    {newGeneratedKey}
                  </div>
                )}
                
                <button
                  onClick={handleRegenRecoveryKey}
                  className="bg-zinc-850 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 font-semibold py-2 rounded-xl text-xs transition-colors self-start px-4"
                >
                  Regenerate Recovery Key
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
