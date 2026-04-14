import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

function ProtectedRoute({ children, requiredRoles = [] }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (requiredRoles.length > 0 && !requiredRoles.includes(user.role)) {
    const homePath = user.role === 'admin' ? '/admin' : '/dashboard'
    return <Navigate to={homePath} replace state={{ from: location.pathname, denied: true }} />
  }

  return children
}

export default ProtectedRoute
