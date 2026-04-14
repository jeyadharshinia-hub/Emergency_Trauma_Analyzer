/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import api from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    api
      .get('/auth/me')
      .then((res) => {
        if (mounted) {
          setUser(res.data.user)
        }
      })
      .catch(() => {
        if (mounted) {
          setUser(null)
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false)
        }
      })
    return () => {
      mounted = false
    }
  }, [])

  const value = useMemo(() => ({ user, setUser, loading }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return ctx
}
