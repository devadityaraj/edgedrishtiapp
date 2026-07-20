import { AuthGuard } from '@/components/auth-guard'

export default function MasterAdminLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard requiredRole="master_admin">{children}</AuthGuard>
}
