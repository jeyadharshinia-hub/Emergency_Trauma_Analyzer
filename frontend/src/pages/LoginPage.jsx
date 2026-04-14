import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '../api'
import { useAuth } from '../contexts/AuthContext'
import { useLang } from '../contexts/LangContext'

const DEMO_CREDENTIALS = {
  doctor: { username: 'demo_doctor', password: 'demo123' },
  admin: { username: 'admin', password: 'admin123' },
}

function LoginPage() {
  const { setUser } = useAuth()
  const { t } = useLang()
  const navigate = useNavigate()
  const location = useLocation()
  const [loginRole, setLoginRole] = useState('doctor')
  const [username, setUsername] = useState(DEMO_CREDENTIALS.doctor.username)
  const [password, setPassword] = useState(DEMO_CREDENTIALS.doctor.password)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const redirectTo = location.state?.from
  const title = loginRole === 'admin' ? 'Admin Login' : t.loginTitle

  const applyRoleDefaults = (role) => {
    setLoginRole(role)
    setUsername(DEMO_CREDENTIALS[role].username)
    setPassword(DEMO_CREDENTIALS[role].password)
    setError('')
  }

  const login = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/login', { username, password })
      setUser(res.data.user)
      const destination =
        redirectTo ||
        (res.data.user?.role === 'admin' ? '/admin' : '/dashboard')
      navigate(destination, { replace: true })
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/quick-login', { role: loginRole })
      setUser(res.data.user)
      navigate(loginRole === 'admin' ? '/admin' : '/dashboard', { replace: true })
    } catch {
      setError('Unable to quick login')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="row eta-login-layout g-3">
      <div className="col-lg-6">
        <div className="eta-login-panel eta-fade h-100 d-flex flex-column justify-content-center">
          <h2 className="mb-3">Emergency Trauma Analyzer</h2>
          <p className="mb-3">
            Instant AI-assisted screening for trauma scans with doctor-controlled bilingual reporting.
          </p>
          <div className="d-flex flex-wrap gap-2">
            <span className="badge text-bg-light px-3 py-2">X-ray</span>
            <span className="badge text-bg-light px-3 py-2">CT</span>
            <span className="badge text-bg-light px-3 py-2">MRI</span>
            <span className="badge text-bg-light px-3 py-2">Severity Triage</span>
          </div>
        </div>
      </div>
      <div className="col-lg-6 col-xl-5">
        <div className="card eta-card eta-login-card eta-fade">
          <div className="eta-role-switch mb-4">
            <button
              type="button"
              className={`eta-role-switch__item ${loginRole === 'doctor' ? 'active' : ''}`}
              onClick={() => applyRoleDefaults('doctor')}
            >
              Doctor workspace
            </button>
            <button
              type="button"
              className={`eta-role-switch__item ${loginRole === 'admin' ? 'active' : ''}`}
              onClick={() => applyRoleDefaults('admin')}
            >
              Admin workspace
            </button>
          </div>
          <h4 className="text-center mb-2">{title}</h4>
          <p className="text-center eta-subtle small mb-4">
            {loginRole === 'admin'
              ? 'Admin can manage doctor accounts, all patient records, all reports, and system activity.'
              : 'Doctor can upload scans, generate reports, manage patients, and download PDFs.'}
          </p>
          {error && <div className="alert alert-danger py-2">{error}</div>}
          <form onSubmit={login} className="d-flex flex-column gap-3">
            <div>
              <label className="form-label">{t.username}</label>
              <input
                className="form-control"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <label className="form-label">{t.password}</label>
              <input
                className="form-control"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button disabled={loading} className="btn btn-primary">
              {t.login}
            </button>
            <button
              disabled={loading}
              type="button"
              className="btn btn-outline-primary"
              onClick={quickLogin}
            >
              {loginRole === 'admin' ? t.adminQuickAccess : t.quickAccess}
            </button>
            <small className="text-muted">
              {loginRole === 'admin'
                ? t.adminLoginHint
                : 'Doctor login: username demo_doctor / password demo123.'}
            </small>
          </form>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
