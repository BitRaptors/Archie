import { useAuth as useAuthContext } from '@/context/auth'

export function useAuth() {
  return useAuthContext()
}


