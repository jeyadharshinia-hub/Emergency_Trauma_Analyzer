import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import api from '../api'
import { useAuth } from '../contexts/AuthContext'
import { useLang } from '../contexts/LangContext'

function AppNavbar() {
  const { user, setUser } = useAuth()
  const { lang, setLanguage, t } = useLang()
  const navigate = useNavigate()
  const location = useLocation()

  const hidden = location.pathname === '/login'

  const logout = async () => {
    await api.post('/auth/logout')
    setUser(null)
    navigate('/login')
  }

  if (hidden) {
    return null
  }

  const homePath = user?.role === 'admin' ? '/admin' : '/dashboard'

  return (
    <nav className="navbar eta-navbar mb-3">
      <div className="container">
        <div className="d-flex align-items-center gap-3 flex-wrap">
          <Link className="navbar-brand fw-semibold mb-0 eta-brand-wrap" to={homePath}>
            <span className="eta-brand-mark">+</span>
            <span>{t.appTitle}</span>
          </Link>
          <div className="d-flex align-items-center gap-1">
            {user?.role === 'admin' ? (
              <NavLink to="/admin" className={({ isActive }) => `eta-navlink ${isActive ? 'active' : ''}`}>
                Admin Dashboard
              </NavLink>
            ) : (
              <>
                <NavLink to="/dashboard" className={({ isActive }) => `eta-navlink ${isActive ? 'active' : ''}`}>
                  {t.navDashboard}
                </NavLink>
                <NavLink to="/management" className={({ isActive }) => `eta-navlink ${isActive ? 'active' : ''}`}>
                  {t.navManagement}
                </NavLink>
                <NavLink to="/scan" className={({ isActive }) => `eta-navlink ${isActive ? 'active' : ''}`}>
                  {t.navUpload}
                </NavLink>
              </>
            )}
          </div>
        </div>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          <button
            type="button"
            className={`btn btn-sm ${lang === 'en' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setLanguage('en')}
          >
            EN
          </button>
          <button
            type="button"
            className={`btn btn-sm ${lang === 'ta' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setLanguage('ta')}
          >
            TA
          </button>
          {user && (
            <span className="badge text-bg-light border px-2 py-1 fw-semibold">
              {user.role === 'admin' ? `Admin: ${user.username}` : user.username}
            </span>
          )}
          {user && (
            <button type="button" className="btn btn-sm btn-outline-dark" onClick={logout}>
              {t.logout}
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}

export default AppNavbar
