import { AuthGuard } from '@/components/auth-guard'

export default function UserLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard requiredRole="user">{children}</AuthGuard>
}
