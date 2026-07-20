'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { apiClient } from '@/lib/api-client'

type PortalRole = 'user' | 'admin' | 'master_admin'

interface AuthGuardProps {
  children: React.ReactNode
  
  requiredRole?: PortalRole
}

/**
 * Route-level guard that enforces:
 *  1. A valid session token exists in localStorage.
 *  2. The stored role matches the required role for this portal.
 *  3. For master_admin routes: the request must originate from localhost
 *     (checked server-side). Non-localhost visitors receive a 403 screen.
 */
export function AuthGuard({ children, requiredRole = 'user' }: AuthGuardProps) {
  const router = useRouter()
  const pathname = usePathname()

  const [status, setStatus] = useState<'checking' | 'authorized' | 'forbidden' | 'unauthorized'>('checking')

  useEffect(() => {
    // Always allow the login sub-routes through (no auth needed to view login)
    if (pathname.includes('/login')) {
      setStatus('authorized')
      return
    }

    const checkAuth = async () => {
      const token = localStorage.getItem('accessToken')
      const storedRole = localStorage.getItem('userRole') as PortalRole | null

      
      if (!token) {
        setStatus('unauthorized')
        router.push('/')
        return
      }

      // Role hierarchy check: master_admin (3) >= admin (2) >= user (1)
      const roleHierarchy: Record<PortalRole, number> = {
        user: 1,
        admin: 2,
        master_admin: 3,
      }

      const storedRoleLevel = storedRole ? roleHierarchy[storedRole] : 0
      const requiredRoleLevel = roleHierarchy[requiredRole] || 1

      if (storedRoleLevel < requiredRoleLevel) {
        const roleRedirects: Record<PortalRole, string> = {
          user: '/user/dashboard',
          admin: '/admin/dashboard',
          master_admin: '/master-admin/dashboard',
        }
        setStatus('unauthorized')
        router.push(storedRole ? (roleRedirects[storedRole] ?? '/') : '/')
        return
      }

      
      // Verify with backend so network clients get a 403 even if they somehow
      
      if (requiredRole === 'master_admin') {
        try {
          const res = await apiClient.checkLocalhost()
          if (!res.success || !res.data?.is_localhost) {
            setStatus('forbidden')
            return
          }
        } catch {
          setStatus('forbidden')
          return
        }
      }

      setStatus('authorized')
    }

    checkAuth()
  }, [pathname, router, requiredRole])

  

  if (status === 'checking') {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-orange-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-semibold text-zinc-400">Verifying secure session...</span>
        </div>
      </div>
    )
  }

  if (status === 'forbidden') {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center p-6">
        <div className="max-w-md text-center flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-red-950/40 border border-red-800/60 flex items-center justify-center text-3xl">
            🔒
          </div>
          <h1 className="text-2xl font-extrabold text-red-400 tracking-tight">403 — Forbidden</h1>
          <p className="text-zinc-400 text-sm leading-relaxed">
            The <span className="text-orange-400 font-semibold">Master Admin Console</span> is restricted to the
            host machine only. Remote network access is not permitted.
          </p>
          <p className="text-zinc-600 text-xs">
            Access this page directly on the server running EDGE Drishti.
          </p>
        </div>
      </div>
    )
  }

  if (status === 'unauthorized') {
    
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-orange-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-semibold text-zinc-400">Redirecting...</span>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
