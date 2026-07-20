'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/lib/store/auth-store'
import { useUIStore } from '@/lib/store/ui-store'
import { NavSidebar } from '@/components/nav-sidebar'
import { 
  ShieldAlert, UserCheck, Flame, AlertTriangle, Users, Box,
  Trash, Trash2, Cpu, Eye, Sliders, ToggleLeft, ToggleRight, Sparkles,
  Car, Cat
} from 'lucide-react'

type AITab = 'faces' | 'person' | 'object' | 'vehicle' | 'animal' | 'fire_smoke' | 'accident'

const OBJECT_CLASSES = [
  "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
  "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
  "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
  "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
  "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
  "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
  "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
  "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
  "hair dryer", "toothbrush"
]

const VEHICLE_CLASSES = ["bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"]

const ANIMAL_CLASSES = ["bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"]

export default function MasterAdminAIPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { addNotification } = useUIStore()

  const [activeTab, setActiveTab] = useState<AITab>('faces')
  const [loading, setLoading] = useState(true)

  
  const [faces, setFaces] = useState<any[]>([])
  const [faceLabel, setFaceLabel] = useState('')
  const [faceFiles, setFaceFiles] = useState<File[]>([])
  const [uploadingFace, setUploadingFace] = useState(false)

  
  const [aiProcessingEnabled, setAiProcessingEnabled] = useState(true)

  
  const [aiModels, setAIModels] = useState<any[]>([])

  
  const [localFpsLimit, setLocalFpsLimit] = useState<number | null>(null)
  const [isFpsLimited, setIsFpsLimited] = useState<boolean>(false)
  const [localConfidenceThreshold, setLocalConfidenceThreshold] = useState<number>(0.5)
  const [localAlertsEnabled, setLocalAlertsEnabled] = useState<boolean>(true)

  
  const [localAllowedClasses, setLocalAllowedClasses] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  const getTargetClassesForTab = (tab: AITab): string[] => {
    if (tab === 'object') return OBJECT_CLASSES
    if (tab === 'vehicle') return VEHICLE_CLASSES
    if (tab === 'animal') return ANIMAL_CLASSES
    return []
  }

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && ['faces', 'person', 'object', 'vehicle', 'animal', 'fire_smoke', 'accident'].includes(tab)) {
      setActiveTab(tab as AITab)
    }
  }, [searchParams])

  const loadData = async () => {
    try {
      
      const faceRes = await apiClient.getFaces()
      if (faceRes.success && faceRes.data) {
        setFaces(faceRes.data)
      }

      
      const modelsRes = await apiClient.getAIModels()
      if (modelsRes.success && modelsRes.data) {
        setAIModels(modelsRes.data)
      }

      
      const configRes = await apiClient.getSystemConfig()
      if (configRes.success && configRes.data) {
        setAiProcessingEnabled(configRes.data.ai_processing_enabled !== false)
      }
    } catch (err) {
      console.error('Failed to load AI administration details:', err)
    }
  }

  
  useEffect(() => {
    if (activeTab !== 'faces') {
      const modelObj = aiModels.find(m => m.key === activeTab)
      if (modelObj) {
        const limit = modelObj.fpsLimit
        setLocalFpsLimit(limit !== undefined && limit !== null ? limit : null)
        setIsFpsLimited(limit !== null && limit !== undefined)

        const thresh = modelObj.confidenceThreshold
        setLocalConfidenceThreshold(thresh !== undefined && thresh !== null ? thresh : 0.5)

        const defaultClasses = getTargetClassesForTab(activeTab)
        setLocalAllowedClasses(modelObj.allowedClasses || defaultClasses)

        setLocalAlertsEnabled(modelObj.alertsEnabled !== false)
      } else {
        setLocalFpsLimit(null)
        setIsFpsLimited(false)
        setLocalConfidenceThreshold(0.5)
        setLocalAllowedClasses([])
        setLocalAlertsEnabled(true)
      }
    } else {
      
      const modelObj = aiModels.find(m => m.key === 'face')
      if (modelObj) {
        const thresh = modelObj.confidenceThreshold
        setLocalConfidenceThreshold(thresh !== undefined && thresh !== null ? thresh : 0.6)
        setLocalAlertsEnabled(modelObj.alertsEnabled !== false)
      } else {
        setLocalAlertsEnabled(true)
      }
    }
  }, [activeTab, aiModels])

  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        router.push('/')
        return
      }
      await loadData()
      setLoading(false)
    }
    init()
  }, [])

  
  const handleEnrollFace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (faceFiles.length === 0) {
      alert('Please select at least one image file')
      return
    }
    setUploadingFace(true)
    const res = await apiClient.enrollFace(faceLabel || null, faceFiles)
    setUploadingFace(false)
    if (res.success) {
      const count = res.data?.enrolled_count || 0
      const errors = res.data?.errors || []
      let msg = `Successfully enrolled ${count} face template(s).`
      if (errors.length > 0) {
        msg += ` Errors: ${errors.join(', ')}`
      }
      addNotification({ type: 'success', message: msg, duration: 5000 })
      setFaceLabel('')
      setFaceFiles([])
      const fileInput = document.getElementById('face-file-input') as HTMLInputElement
      if (fileInput) fileInput.value = ''
      await loadData()
    } else {
      alert(res.error || 'Face enrollment failed. Ensure face_recognition or insightface library is fully loaded.')
    }
  }

  const handleDeleteFace = async (id: string) => {
    if (confirm('Remove this face template?')) {
      const res = await apiClient.deleteFace(id)
      if (res.success) {
        addNotification({ type: 'success', message: 'Face template removed successfully', duration: 3000 })
        await loadData()
      }
    }
  }

  
  const handleToggleAiProcessing = async () => {
    const nextState = !aiProcessingEnabled
    setAiProcessingEnabled(nextState)
    const res = await apiClient.updateSystemConfig({ ai_processing_enabled: nextState })
    if (res.success) {
      addNotification({
        type: 'success',
        message: `Global AI System is now ${nextState ? 'ENABLED' : 'DISABLED'}`,
        duration: 3000
      })
      await loadData()
    } else {
      setAiProcessingEnabled(!nextState)
      alert(res.error || 'Failed to update global AI status')
    }
  }

  
  const handleToggleModel = async (modelId: string, currentEnabled: boolean) => {
    const nextState = !currentEnabled
    
    const currentModel = aiModels.find(m => m.id === modelId)
    const limit = currentModel ? currentModel.fpsLimit : null
    const classes = currentModel ? currentModel.allowedClasses : null
    const thresh = currentModel ? currentModel.confidenceThreshold : null
    const alerts = currentModel ? currentModel.alertsEnabled !== false : true

    const res = await apiClient.toggleAIModel(modelId, nextState, limit, classes, thresh, alerts)
    if (res.success) {
      addNotification({ 
        type: nextState ? 'success' : 'info', 
        message: `Model ${nextState ? 'enabled' : 'disabled'} globally`, 
        duration: 3000 
      })
      await loadData()
    } else {
      alert(res.error || 'Failed to toggle model state')
    }
  }

  
  const handleToggleClass = async (cls: string, checked: boolean) => {
    let nextClasses = [...localAllowedClasses]
    if (checked) {
      if (!nextClasses.includes(cls)) {
        nextClasses.push(cls)
      }
    } else {
      nextClasses = nextClasses.filter(c => c !== cls)
    }
    setLocalAllowedClasses(nextClasses)

    const modelObj = aiModels.find(m => m.key === activeTab)
    if (modelObj) {
      const res = await apiClient.toggleAIModel(modelObj.id, modelObj.enabledGlobally, modelObj.fpsLimit, nextClasses)
      if (res.success) {
        addNotification({
          type: 'success',
          message: `${modelObj.displayName} configuration autosaved`,
          duration: 1500
        })
        
        const modelsRes = await apiClient.getAIModels()
        if (modelsRes.success && modelsRes.data) {
          setAIModels(modelsRes.data)
        }
      }
    }
  }

  const handleSetAllClasses = async (classesList: string[]) => {
    setLocalAllowedClasses(classesList)
    const modelObj = aiModels.find(m => m.key === activeTab)
    if (modelObj) {
      const res = await apiClient.toggleAIModel(modelObj.id, modelObj.enabledGlobally, modelObj.fpsLimit, classesList)
      if (res.success) {
        addNotification({
          type: 'success',
          message: `All configuration options updated`,
          duration: 1500
        })
        const modelsRes = await apiClient.getAIModels()
        if (modelsRes.success && modelsRes.data) {
          setAIModels(modelsRes.data)
        }
      }
    }
  }

  const getModelDetails = (key: string) => {
    switch (key) {
      case 'person':
        return {
          title: 'Person Detection Model',
          desc: 'High-accuracy real-time object tracking utilizing YOLO architecture tuned specifically for human presence and motion vector paths.',
          icon: Users,
          color: 'text-blue-500'
        }
      case 'object':
        return {
          title: 'Object & Weapon Detection Model',
          desc: 'Identifies general categories of objects, bags, gear, and potentially dangerous tools inside designated ROI zones.',
          icon: Box,
          color: 'text-orange-500'
        }
      case 'vehicle':
        return {
          title: 'Vehicle Detection Model',
          desc: 'Identifies traffic-flow items globally (cars, bicycles, motorcycles, buses, trains, trucks, boats) for perimeter security.',
          icon: Car,
          color: 'text-emerald-500'
        }
      case 'animal':
        return {
          title: 'Animal Detection Model',
          desc: 'Identifies intrusion events by animal classes (dogs, cats, birds, horses, sheep, cows, wildlife) to prevent alarms from fauna.',
          icon: Cat,
          color: 'text-pink-500'
        }
      case 'fire_smoke':
        return {
          title: 'Fire & Smoke Detection Model',
          desc: 'Combines thermal color-spectrum classification heuristics with visual model detection to identify flare-ups or smoke.',
          icon: Flame,
          color: 'text-red-500'
        }
      case 'accident':
        return {
          title: 'Accident & Collision Detection Model',
          desc: 'Identifies sudden vehicle decelerations, skids, spin-outs, or collisions on perimeter roadways and parking zones.',
          icon: AlertTriangle,
          color: 'text-yellow-500'
        }
      default:
        return {
          title: 'Custom AI Inference Engine',
          desc: 'Global neural network classification pipeline for automated object cataloging.',
          icon: Cpu,
          color: 'text-purple-500'
        }
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
              <Sparkles className="w-5 h-5 text-orange-500 animate-pulse" />
              <span>Artificial Intelligence</span>
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">Global configuration, biometric registries, and neural network engines.</p>
          </div>

          <div className="flex items-center gap-3 bg-zinc-900/60 border border-zinc-850 px-4 py-2 rounded-xl">
            <div className="text-right">
              <div className="text-[11px] font-bold text-white uppercase tracking-wider">Global AI Processing</div>
              <div className="text-[9px] text-zinc-400 mt-0.5">
                {aiProcessingEnabled ? 'Active & Ingesting' : 'System Suspended'}
              </div>
            </div>
            <button
              onClick={handleToggleAiProcessing}
              className="focus:outline-none transition-transform active:scale-95"
            >
              {aiProcessingEnabled ? (
                <ToggleRight className="w-10 h-10 text-orange-500" />
              ) : (
                <ToggleLeft className="w-10 h-10 text-zinc-600" />
              )}
            </button>
          </div>
        </div>

        
        <div className="flex flex-wrap gap-1.5 bg-zinc-950 border border-zinc-800 p-1.5 rounded-xl text-xs font-semibold w-full">
          {[
            { id: 'faces', label: 'AI Face Detection', icon: UserCheck },
            { id: 'person', label: 'Person Detection', icon: Users },
            { id: 'object', label: 'Object Detection', icon: Box },
            { id: 'vehicle', label: 'Vehicle Detection', icon: Car },
            { id: 'animal', label: 'Animal Detection', icon: Cat },
            { id: 'fire_smoke', label: 'Fire Detection', icon: Flame },
            { id: 'accident', label: 'Accident Detection', icon: AlertTriangle }
          ].map(tab => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as AITab)}
                className={`px-3.5 py-2 rounded-lg transition-colors flex items-center gap-1.5 ${
                  activeTab === tab.id ? 'bg-orange-600 text-white font-bold' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>

        
        {activeTab === 'faces' && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
            <div className="border-b border-zinc-900 pb-3 flex justify-between items-center gap-2">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <UserCheck className="w-4.5 h-4.5 text-orange-500" />
                <span>AI Face Detection & Enrollment</span>
              </h2>
              {(() => {
                const faceModel = aiModels.find(m => m.key === 'face')
                if (!faceModel) return null
                return (
                  <button
                    onClick={() => handleToggleModel(faceModel.id, faceModel.enabledGlobally)}
                    className="flex items-center gap-1.5 focus:outline-none transition-transform active:scale-95"
                  >
                    <span className="text-xs text-zinc-400 font-semibold uppercase mr-1">
                      {faceModel.enabledGlobally ? 'Enabled Globally' : 'Disabled Globally'}
                    </span>
                    {faceModel.enabledGlobally ? (
                      <ToggleRight className="w-10 h-10 text-orange-500" />
                    ) : (
                      <ToggleLeft className="w-10 h-10 text-zinc-600" />
                    )}
                  </button>
                )
              })()}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2">
                <form onSubmit={handleEnrollFace} className="bg-zinc-900/40 border border-zinc-850 p-5 rounded-2xl flex flex-col gap-4 w-full">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">Enroll Profiles</h3>
                  
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-zinc-400 font-semibold uppercase">Identity Label (Optional)</label>
                      <input
                        type="text"
                        placeholder="E.g. John Doe (Leave blank to auto-detect from filenames)"
                        value={faceLabel}
                        onChange={(e) => setFaceLabel(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-orange-500 transition-colors"
                      />
                      <span className="text-[9px] text-zinc-500 leading-normal">
                        * If you specify a label, all uploaded images will be enrolled under this single identity (useful for multi-angle templates).
                        <br />
                        * If left blank, each image will create a separate identity using its filename (e.g. John_Doe.jpg &rarr; John Doe).
                      </span>
                    </div>
                    
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-zinc-400 font-semibold uppercase">Choose Photo(s)</label>
                      <input
                        id="face-file-input"
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={(e) => {
                          if (e.target.files) {
                            setFaceFiles(Array.from(e.target.files))
                          }
                        }}
                        className="w-full text-xs text-zinc-400 file:bg-zinc-800 file:hover:bg-zinc-700 file:border-0 file:text-white file:px-3 file:py-1.5 file:rounded-lg file:text-xs file:font-semibold cursor-pointer"
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={uploadingFace}
                      className="bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold py-2.5 rounded-xl transition-all shadow-md mt-2 flex items-center justify-center gap-1.5"
                    >
                      <UserCheck className="w-4 h-4" />
                      <span>{uploadingFace ? 'Extracting biometric features...' : 'Enroll Face Identity'}</span>
                    </button>
                  </div>
                </form>
              </div>

              <div className="md:col-span-1">
                {(() => {
                  const faceModel = aiModels.find(m => m.key === 'face')
                  if (!faceModel) return null
                  return (
                    <div className="bg-zinc-900/30 border border-zinc-850 p-4 rounded-xl flex flex-col gap-3 h-fit">
                      <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                        <Sliders className="w-3.5 h-3.5 text-orange-500" />
                        <span>Model Configuration Controls</span>
                      </h4>
                      
                      <p className="text-[11px] text-zinc-400 leading-relaxed mb-1">
                        Configure the confidence threshold for face biometric template matching globally.
                      </p>

                      <div className="flex flex-col gap-2 pt-3 border-t border-zinc-900">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-zinc-300 font-semibold">Confidence Threshold:</span>
                          <span className="text-orange-500 font-bold">{(localConfidenceThreshold * 100).toFixed(0)}%</span>
                        </div>
                        <input
                          type="range"
                          min="0.1"
                          max="0.95"
                          step="0.05"
                          value={localConfidenceThreshold}
                          onChange={(e) => setLocalConfidenceThreshold(parseFloat(e.target.value))}
                          className="w-full accent-orange-600 bg-zinc-955 h-1 rounded-lg appearance-none cursor-pointer"
                        />
                        <span className="text-[9px] text-zinc-500 leading-normal font-medium">
                          Minimum match accuracy required to recognize a face identity. Higher values reduce false positives but require clearer camera angles.
                        </span>
                      </div>

                      <div className="flex flex-col gap-2 pt-3 border-t border-zinc-900">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-zinc-300 font-semibold font-medium">Trigger Alerts:</span>
                          <button
                            type="button"
                            onClick={() => setLocalAlertsEnabled(!localAlertsEnabled)}
                            className="flex items-center focus:outline-none transition-transform active:scale-95 animate-fade-in"
                          >
                            {localAlertsEnabled ? (
                              <ToggleRight className="w-10 h-10 text-orange-500" />
                            ) : (
                              <ToggleLeft className="w-10 h-10 text-zinc-655" />
                            )}
                          </button>
                        </div>
                        <span className="text-[9px] text-zinc-500 leading-normal font-medium">
                          If enabled, face match detection events will create in-app notifications and trigger alert dispatches.
                        </span>
                      </div>

                      <button
                        onClick={async () => {
                          const res = await apiClient.toggleAIModel(
                            faceModel.id,
                            faceModel.enabledGlobally,
                            null,
                            faceModel.allowedClasses,
                            localConfidenceThreshold,
                            localAlertsEnabled
                          )
                          if (res.success) {
                            addNotification({
                              type: 'success',
                              message: 'Face Detection settings updated successfully',
                              duration: 3000
                            })
                            await loadData()
                          } else {
                            alert(res.error || 'Failed to update settings')
                          }
                        }}
                        className="mt-2 bg-orange-600 hover:bg-orange-500 text-white font-semibold py-2.5 rounded-xl text-xs transition-all w-full flex items-center justify-center gap-1.5 shadow-md"
                      >
                        <span>Apply Settings</span>
                      </button>
                    </div>
                  )
                })()}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Enrolled profiles:</span>
              {faces.length === 0 ? (
                <div className="text-center text-zinc-650 text-xs py-8 border border-zinc-900 rounded-xl">
                  No face identities registered yet.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {faces.map(f => (
                    <div key={f.id} className="flex justify-between items-center bg-zinc-900/40 border border-zinc-850 p-4 rounded-2xl hover:border-zinc-700 transition-colors">
                      <div>
                        <h3 className="text-xs font-bold text-white">{f.label}</h3>
                        <p className="text-[10px] text-zinc-500 mt-1">Enrolled: {new Date(f.enrolled_at).toLocaleDateString()}</p>
                      </div>
                      <button
                        onClick={() => handleDeleteFace(f.id)}
                        className="p-2 rounded-lg bg-red-955/20 border border-red-900/30 text-red-400 hover:bg-red-950/40 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Sub-tabs: Other Detection Modules (Global AI Toggles) ── */}
        {activeTab !== 'faces' && (() => {
          const modelKey = activeTab
          const modelObj = aiModels.find(m => m.key === modelKey)
          const meta = getModelDetails(modelKey)
          const Icon = meta.icon

          const showClassSelector = ['object', 'vehicle', 'animal'].includes(modelKey)
          const targetClasses = getTargetClassesForTab(modelKey)

          return (
            <div className="bg-zinc-955 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
              <div className="border-b border-zinc-900 pb-4 flex justify-between items-start">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl ${meta.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white uppercase tracking-wider">{meta.title}</h2>
                    <p className="text-xs text-zinc-400 mt-0.5">Configuration & Global Deployment Status</p>
                  </div>
                </div>

                {modelObj && (
                  <button
                    onClick={() => handleToggleModel(modelObj.id, modelObj.enabledGlobally)}
                    className="flex items-center gap-1.5 focus:outline-none transition-transform active:scale-95"
                  >
                    <span className="text-xs text-zinc-400 font-semibold uppercase mr-1">
                      {modelObj.enabledGlobally ? 'Enabled Globally' : 'Disabled Globally'}
                    </span>
                    {modelObj.enabledGlobally ? (
                      <ToggleRight className="w-12 h-12 text-orange-500" />
                    ) : (
                      <ToggleLeft className="w-12 h-12 text-zinc-650" />
                    )}
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2 flex flex-col gap-4">
                  <div className="bg-zinc-900/30 border border-zinc-850 p-4 rounded-xl">
                    <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-2">Engine Description</h4>
                    <p className="text-xs text-zinc-300 leading-relaxed">{meta.desc}</p>
                  </div>

                  <div className="bg-zinc-900/30 border border-zinc-850 p-4 rounded-xl flex flex-col gap-3">
                    <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Engine Specifications</h4>
                    <div className="flex justify-between text-xs py-1 border-b border-zinc-900/60">
                      <span className="text-zinc-400">Model Key Identifier</span>
                      <span className="text-white font-mono">{modelKey}</span>
                    </div>
                    <div className="flex justify-between text-xs py-1 border-b border-zinc-900/60">
                      <span className="text-zinc-400">Accelerator Constraint</span>
                      <span className="text-white font-semibold">
                        {modelObj?.requiresGpu ? 'NVIDIA GPU Acceleration Recommended' : 'CPU or Heterogeneous Run Mode'}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs py-1">
                      <span className="text-zinc-400">Deployment Status</span>
                      {modelObj?.enabledGlobally ? (
                        <span className="text-emerald-500 font-bold uppercase tracking-wider animate-pulse">Running Globally</span>
                      ) : (
                        <span className="text-zinc-500 font-semibold uppercase tracking-wider">Suspended Globally</span>
                      )}
                    </div>
                  </div>

                  
                  {showClassSelector && (
                    <div className="bg-zinc-900/30 border border-zinc-850 p-5 rounded-xl flex flex-col gap-4">
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-zinc-900 pb-3">
                        <div>
                          <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                            <Eye className="w-3.5 h-3.5 text-orange-500" />
                            <span>Global Classification Policies</span>
                          </h4>
                          <p className="text-[11px] text-zinc-400 mt-1">
                            Globally allow or disallow target classes for this model. Auto-saves changes.
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleSetAllClasses(targetClasses)}
                            className="bg-zinc-850 hover:bg-zinc-800 text-white text-[10px] font-bold uppercase tracking-wider px-2.5 py-1.5 rounded-lg border border-zinc-800 transition-colors"
                          >
                            Allow All
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSetAllClasses([])}
                            className="bg-zinc-850 hover:bg-zinc-800 text-white text-[10px] font-bold uppercase tracking-wider px-2.5 py-1.5 rounded-lg border border-zinc-800 transition-colors"
                          >
                            Disallow All
                          </button>
                        </div>
                      </div>

                      
                      <input
                        type="text"
                        placeholder={`Search classes...`}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-orange-500 transition-colors placeholder-zinc-600"
                      />

                      
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 max-h-[300px] overflow-y-auto pr-1">
                        {targetClasses.filter(c => c.toLowerCase().includes(searchQuery.toLowerCase())).map(cls => {
                          const isChecked = localAllowedClasses.includes(cls)
                          return (
                            <label
                              key={cls}
                              className={`flex items-center gap-2 p-2 rounded-lg border transition-all cursor-pointer select-none ${
                                isChecked 
                                  ? 'bg-orange-950/20 border-orange-900/40 text-orange-400 font-semibold' 
                                  : 'bg-zinc-950 border-zinc-900/60 text-zinc-500 hover:border-zinc-800 hover:text-zinc-300'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => handleToggleClass(cls, e.target.checked)}
                                className="w-3.5 h-3.5 rounded border-zinc-805 bg-zinc-955 text-orange-600 focus:ring-0 cursor-pointer"
                              />
                              <span className="text-[11px] capitalize tracking-wide">{cls}</span>
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <div className="md:col-span-1 flex flex-col gap-4">
                  
                  <div className="bg-zinc-900/30 border border-zinc-850 p-4 rounded-xl flex flex-col gap-3 h-fit">
                    <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-orange-500" />
                      <span>Model Configuration Controls</span>
                    </h4>
                    
                    <p className="text-[11px] text-zinc-400 leading-relaxed mb-1">
                      Limit the frame rate (FPS) and set the confidence threshold globally for this model.
                    </p>

                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 py-1 select-none cursor-pointer">
                        <input
                          type="checkbox"
                          id="fps_limit_check"
                          checked={isFpsLimited}
                          onChange={(e) => {
                            const checked = e.target.checked
                            if (!checked) {
                              const confirmDisable = confirm(
                                "WARNING: Disabling the FPS limit can stress the GPU/CPU and cause lags in the system. Are you sure you want to disable the limit?"
                              )
                              if (!confirmDisable) {
                                return
                              }
                              setIsFpsLimited(false)
                              setLocalFpsLimit(null)
                            } else {
                              setIsFpsLimited(true)
                              setLocalFpsLimit(5) 
                            }
                          }}
                          className="w-3.5 h-3.5 rounded border-zinc-800 bg-zinc-955 text-orange-600 focus:ring-0 cursor-pointer"
                        />
                        <label htmlFor="fps_limit_check" className="text-xs text-zinc-300 cursor-pointer select-none">
                          Enable Model FPS Limit
                        </label>
                      </div>

                      {isFpsLimited && (
                        <div className="flex flex-col gap-2 mt-1">
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-zinc-450">Maximum rate:</span>
                            <span className="text-orange-500 font-bold">{localFpsLimit} FPS</span>
                          </div>
                          <input
                            type="range"
                            min="1"
                            max="30"
                            step="1"
                            value={localFpsLimit || 5}
                            onChange={(e) => setLocalFpsLimit(parseInt(e.target.value))}
                            className="w-full accent-orange-600 bg-zinc-955 h-1 rounded-lg appearance-none cursor-pointer"
                          />
                        </div>
                      )}

                      <div className="flex flex-col gap-2 pt-3 border-t border-zinc-900">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-zinc-300 font-semibold">Confidence Threshold:</span>
                          <span className="text-orange-500 font-bold">{(localConfidenceThreshold * 100).toFixed(0)}%</span>
                        </div>
                        <input
                          type="range"
                          min="0.1"
                          max="0.95"
                          step="0.05"
                          value={localConfidenceThreshold}
                          onChange={(e) => setLocalConfidenceThreshold(parseFloat(e.target.value))}
                          className="w-full accent-orange-600 bg-zinc-955 h-1 rounded-lg appearance-none cursor-pointer"
                        />
                        <span className="text-[9px] text-zinc-500 leading-normal font-medium">
                          Minimum score required to trigger a detection event. Lower values increase sensitivity but may yield false positives.
                        </span>
                      </div>

                      <div className="flex flex-col gap-2 pt-3 border-t border-zinc-900">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-zinc-300 font-semibold font-medium">Trigger Alerts:</span>
                          <button
                            type="button"
                            onClick={() => setLocalAlertsEnabled(!localAlertsEnabled)}
                            className="flex items-center focus:outline-none transition-transform active:scale-95 animate-fade-in"
                          >
                            {localAlertsEnabled ? (
                              <ToggleRight className="w-10 h-10 text-orange-500" />
                            ) : (
                              <ToggleLeft className="w-10 h-10 text-zinc-655" />
                            )}
                          </button>
                        </div>
                        <span className="text-[9px] text-zinc-500 leading-normal font-medium">
                          If enabled, detection events will create in-app notifications and queue alerts to external endpoints.
                        </span>
                      </div>
                    </div>

                    {modelObj && (
                       <button
                        onClick={async () => {
                          const limitToSend = isFpsLimited ? localFpsLimit : null
                          const res = await apiClient.toggleAIModel(
                            modelObj.id,
                            modelObj.enabledGlobally,
                            limitToSend,
                            localAllowedClasses,
                            localConfidenceThreshold,
                            localAlertsEnabled
                          )
                          if (res.success) {
                            addNotification({
                              type: 'success',
                              message: 'Model parameters updated successfully',
                              duration: 3000
                            })
                            await loadData()
                          } else {
                            alert(res.error || 'Failed to update parameters')
                          }
                        }}
                        className="mt-2 bg-orange-600 hover:bg-orange-500 text-white font-semibold py-2.5 rounded-xl text-xs transition-all w-full flex items-center justify-center gap-1.5 shadow-md"
                      >
                        <span>Apply Settings</span>
                      </button>
                    )}
                  </div>

                  
                  <div className="bg-zinc-900/10 border border-zinc-900 p-4 rounded-xl flex flex-col gap-2 h-fit">
                    <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Status Information</h4>
                    <div className="text-[11px] leading-relaxed text-zinc-400">
                      When this model is enabled globally, ingestion pipelines scan raw camera frames for target triggers. 
                      Individual camera trigger settings and ROI configurations are defined in the <strong className="text-white">Admin Panel</strong>.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        })()}
      </main>
    </div>
  )
}
