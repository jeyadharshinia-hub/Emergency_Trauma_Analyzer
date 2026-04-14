import { Navigate, Route, Routes } from 'react-router-dom'
import AppNavbar from './components/AppNavbar'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './contexts/AuthContext'
import AdminPage from './pages/AdminPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import ManagementPage from './pages/ManagementPage'
import ResultPage from './pages/ResultPage'
import ScanPage from './pages/ScanPage'

function RoleHomeRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Navigate to={user.role === 'admin' ? '/admin' : '/dashboard'} replace />
}

function App() {
  return (
    <div className="eta-app">
      <AppNavbar />
      <main className="eta-main container py-4 py-md-4">
        <Routes>
          <Route path="/" element={<RoleHomeRoute />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute requiredRoles={['doctor']}>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRoles={['admin']}>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/management"
            element={
              <ProtectedRoute requiredRoles={['doctor']}>
                <ManagementPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/patients"
            element={
              <ProtectedRoute requiredRoles={['doctor']}>
                <Navigate to="/management" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scan"
            element={
              <ProtectedRoute requiredRoles={['doctor']}>
                <ScanPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scan/:scanId/result"
            element={
              <ProtectedRoute requiredRoles={['doctor']}>
                <ResultPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<RoleHomeRoute />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
