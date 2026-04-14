import { useEffect, useMemo, useRef, useState } from 'react'
import api from '../api'
import { useLang } from '../contexts/LangContext'
import { savePdfResponse } from '../utils/pdf'

function extractApiError(err, fallback) {
  if (err?.response?.status === 404 || err?.response?.status === 405) {
    return 'Admin API not available. Restart the backend server and try again.'
  }
  return err?.response?.data?.error || err?.message || fallback
}

async function downloadAdminReportPdf(scanId, patientName) {
  const fallback = `eta_report_${patientName || `scan_${scanId}`}.pdf`
  const response = await api.get(`/admin/reports/${scanId}/pdf`, {
    responseType: 'blob',
    validateStatus: () => true,
  })
  return savePdfResponse(response, fallback)
}

function formatDate(value) {
  if (!value) return '-'
  const asDate = new Date(value)
  if (Number.isNaN(asDate.getTime())) return '-'
  return asDate.toLocaleString()
}

function SeverityBadge({ severity }) {
  if (!severity) {
    return <span className="badge text-bg-secondary">-</span>
  }

  const className =
    severity === 'critical'
      ? 'text-bg-danger'
      : severity === 'moderate'
      ? 'text-bg-warning'
      : severity === 'mild'
      ? 'text-bg-success'
      : 'text-bg-secondary'

  return <span className={`badge ${className}`}>{severity}</span>
}

function getActivePatients(items) {
  if (!Array.isArray(items)) {
    return []
  }
  return items.filter((patient) => patient?.is_active !== false)
}

function StatCard({ label, value, color }) {
  return (
    <div className="col-6 col-md-3">
      <div className="card eta-card eta-admin-stat h-100 text-center p-3">
        <div className={`fs-2 fw-bold text-${color}`}>{value ?? '-'}</div>
        <div className="small text-uppercase fw-semibold text-muted">{label}</div>
      </div>
    </div>
  )
}

function SectionCard({ title, subtitle, actions, children }) {
  return (
    <div className="card eta-card eta-admin-surface p-3 p-md-4">
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
        <div>
          <h5 className="mb-1">{title}</h5>
          {subtitle ? <p className="eta-subtle mb-0">{subtitle}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

function DoctorsTab() {
  const [doctors, setDoctors] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ username: '', password: '' })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchDoctors = async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/admin/users')
      setDoctors(Array.isArray(data.users) ? data.users : [])
    } catch (err) {
      setDoctors([])
      setError(extractApiError(err, 'Failed to load doctors.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDoctors()
  }, [])

  const handleCreate = async (event) => {
    event.preventDefault()
    setError('')
    setSuccess('')
    setCreating(true)
    try {
      await api.post('/admin/users', form)
      setSuccess(`Doctor "${form.username}" created successfully.`)
      setForm({ username: '', password: '' })
      await fetchDoctors()
    } catch (err) {
      setError(extractApiError(err, 'Failed to create doctor.'))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id, username) => {
    if (!window.confirm(`Delete doctor "${username}"? This cannot be undone.`)) {
      return
    }
    setError('')
    setSuccess('')
    try {
      await api.delete(`/admin/users/${id}`)
      setDoctors((prev) => prev.filter((doctor) => doctor.id !== id))
      setSuccess(`Doctor "${username}" removed.`)
    } catch (err) {
      setError(extractApiError(err, 'Failed to delete doctor.'))
    }
  }

  return (
    <SectionCard
      title="Doctor accounts"
      subtitle="Create doctor logins and review every active doctor account."
      actions={
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm"
          onClick={fetchDoctors}
          disabled={loading}
        >
          Refresh
        </button>
      }
    >
      {error && <div className="alert alert-danger py-2">{error}</div>}
      {success && <div className="alert alert-success py-2">{success}</div>}

      <form onSubmit={handleCreate} className="row g-3 eta-admin-form mb-4">
        <div className="col-md-5">
          <label className="form-label fw-semibold">Username</label>
          <input
            className="form-control"
            placeholder="doctor_ramesh"
            value={form.username}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, username: event.target.value }))
            }
            required
          />
        </div>
        <div className="col-md-5">
          <label className="form-label fw-semibold">Password</label>
          <input
            type="password"
            className="form-control"
            placeholder="Minimum 6 characters"
            value={form.password}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, password: event.target.value }))
            }
            required
            minLength={6}
          />
        </div>
        <div className="col-md-2 d-grid">
          <label className="form-label fw-semibold opacity-0">Create</label>
          <button className="btn btn-primary" disabled={creating}>
            {creating ? 'Creating...' : 'Create doctor'}
          </button>
        </div>
      </form>

      {loading ? (
        <div className="text-center py-4">
          <div className="spinner-border text-primary" />
        </div>
      ) : doctors.length === 0 ? (
        <div className="eta-admin-empty">No doctor accounts found.</div>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead className="table-light">
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Created</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {doctors.map((doctor) => (
                <tr key={doctor.id}>
                  <td className="text-muted">{doctor.id}</td>
                  <td className="fw-semibold">{doctor.username}</td>
                  <td>
                    <span className="badge text-bg-primary">{doctor.role}</span>
                  </td>
                  <td className="text-muted small">
                    {doctor.created_at
                      ? new Date(doctor.created_at).toLocaleDateString()
                      : '-'}
                  </td>
                  <td className="text-end">
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => handleDelete(doctor.id, doctor.username)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

function ReportsTab({ focus, onBackToPatients }) {
  const PAGE_SIZE = 20
  const [reports, setReports] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [inputQuery, setInputQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(null)
  const focusKey = useRef(null)
  const tableRef = useRef(null)

  useEffect(() => {
    if (!focus || focusKey.current === focus.key) {
      return
    }
    focusKey.current = focus.key
    const nextQuery = focus.query || ''
    setInputQuery(nextQuery)
    setPage(1)
    setQuery(nextQuery)
  }, [focus])

  // Scroll the results table into view once data loads after a patient focus
  useEffect(() => {
    if (!focus || loading) return
    if (tableRef.current) {
      tableRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [loading, focus])

  useEffect(() => {
    let active = true

    const loadReports = async () => {
      setLoading(true)
      setError('')
      try {
        const { data } = await api.get('/admin/reports', {
          params: { page, page_size: PAGE_SIZE, query },
        })
        if (!active) {
          return
        }
        setReports(Array.isArray(data.items) ? data.items : [])
        setTotal(Number(data.total || 0))
      } catch (err) {
        if (!active) {
          return
        }
        setReports([])
        setError(extractApiError(err, 'Failed to load reports.'))
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadReports()
    return () => {
      active = false
    }
  }, [page, query])

  const handleSearch = (event) => {
    event.preventDefault()
    setPage(1)
    setQuery(inputQuery.trim())
  }

  const handleDownload = async (scanId, patientName) => {
    setDownloading(scanId)
    setError('')
    try {
      await downloadAdminReportPdf(scanId, patientName)
    } catch (err) {
      setError(err?.message || 'Failed to download report.')
    } finally {
      setDownloading(null)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <SectionCard
      title="All reports"
      subtitle="Search every report generated by doctors and download a patient-ready PDF."
    >
      {focus?.query && (
        <div className="alert alert-info d-flex align-items-center justify-content-between py-2 mb-3">
          <span>
            Showing reports for patient: <strong>{focus.query}</strong>
          </span>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={() => onBackToPatients?.()}
          >
            Back to Patient Records
          </button>
        </div>
      )}
      <form onSubmit={handleSearch} className="row g-2 mb-3">
        <div className="col-md-6">
          <input
            className="form-control"
            placeholder="Search by patient, diagnosis, or doctor"
            value={inputQuery}
            onChange={(event) => setInputQuery(event.target.value)}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-primary">Search</button>
        </div>
        {query ? (
          <div className="col-auto">
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={() => {
                setInputQuery('')
                setQuery('')
                setPage(1)
              }}
            >
              Clear
            </button>
          </div>
        ) : null}
      </form>

      {error && <div className="alert alert-danger py-2">{error}</div>}

      <p className="text-muted small mb-3">
        {total} report{total !== 1 ? 's' : ''} found
      </p>

      <div ref={tableRef} />
      {loading ? (
        <div className="text-center py-4">
          <div className="spinner-border text-primary" />
        </div>
      ) : reports.length === 0 ? (
        <div className="eta-admin-empty">No reports found.</div>
      ) : (
        <>
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead className="table-light">
                <tr>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Diagnosis</th>
                  <th>Severity</th>
                  <th>Date</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((item) => (
                  <tr key={item.scan_id}>
                    <td>
                      {item.patient ? (
                        <>
                          <div className="fw-semibold">{item.patient.full_name}</div>
                          <div className="text-muted small">
                            {item.patient.patient_code}
                          </div>
                        </>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td className="text-muted">{item.doctor || '-'}</td>
                    <td>{item.report?.diagnosis || '-'}</td>
                    <td>
                      <SeverityBadge severity={item.report?.severity} />
                    </td>
                    <td className="text-muted small">
                      {item.created_at
                        ? new Date(item.created_at).toLocaleDateString()
                        : '-'}
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-primary"
                        disabled={downloading === item.scan_id}
                        onClick={() =>
                          handleDownload(item.scan_id, item.patient?.full_name)
                        }
                      >
                        {downloading === item.scan_id ? 'Downloading...' : 'Download PDF'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="d-flex gap-2 justify-content-center mt-3">
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={page === 1}
                onClick={() => setPage((prev) => prev - 1)}
              >
                Prev
              </button>
              <span className="align-self-center text-muted small">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={page === totalPages}
                onClick={() => setPage((prev) => prev + 1)}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      )}
    </SectionCard>
  )
}

function PatientsTab({ onViewReports, onArchiveDone }) {
  const { t } = useLang()
  const PAGE_SIZE = 20
  const [patients, setPatients] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [inputQuery, setInputQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [archivingId, setArchivingId] = useState(null)

  useEffect(() => {
    let active = true

    const loadPatients = async () => {
      setLoading(true)
      setError('')
      try {
        const { data } = await api.get('/admin/patients', {
          params: { page, page_size: PAGE_SIZE, query },
        })
        if (!active) {
          return
        }
        const activePatients = getActivePatients(data.items)
        const filteredCount = Array.isArray(data.items)
          ? data.items.length - activePatients.length
          : 0
        setPatients(activePatients)
        setTotal(Math.max(0, Number(data.total || 0) - filteredCount))
        setPage(Number(data.page || page))
      } catch (err) {
        if (!active) {
          return
        }
        setPatients([])
        setError(extractApiError(err, 'Failed to load patients.'))
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadPatients()
    return () => {
      active = false
    }
  }, [page, query])

  const handleSearch = (event) => {
    event.preventDefault()
    setPage(1)
    setQuery(inputQuery.trim())
  }

  const handleArchive = async (patient) => {
    if (!window.confirm(`Archive patient "${patient.full_name}"? They will be moved to the Archived Patients list.`)) {
      return
    }
    setArchivingId(patient.id)
    setError('')
    try {
      await api.delete(`/patients/${patient.id}`)
      onArchiveDone?.()
      const { data } = await api.get('/admin/patients', {
        params: { page, page_size: PAGE_SIZE, query },
      })
      const activePatients = getActivePatients(data.items)
      const filteredCount = Array.isArray(data.items)
        ? data.items.length - activePatients.length
        : 0
      setPatients(activePatients)
      setTotal(Math.max(0, Number(data.total || 0) - filteredCount))
    } catch (err) {
      setError(extractApiError(err, 'Failed to archive patient.'))
    } finally {
      setArchivingId(null)
    }
  }

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  )

  return (
    <SectionCard
      title="Patient records"
      subtitle="Monitor every patient record, the owning doctor, and recent activity."
    >
      <form onSubmit={handleSearch} className="row g-2 mb-3">
        <div className="col-md-6">
          <input
            className="form-control"
            placeholder={t.adminPatientSearchPlaceholder}
            value={inputQuery}
            onChange={(event) => setInputQuery(event.target.value)}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-primary" type="submit">
            {t.search}
          </button>
        </div>
      </form>

      {error && <div className="alert alert-danger py-2">{error}</div>}

      {loading ? (
        <div className="text-center py-4">
          <div className="spinner-border text-primary" />
        </div>
      ) : patients.length === 0 ? (
        <div className="eta-admin-empty">No patients found.</div>
      ) : (
        <>
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead className="table-light">
                <tr>
                  <th>{t.patientCode}</th>
                  <th>{t.fullName}</th>
                  <th>{t.ownerDoctor}</th>
                  <th>{t.phone}</th>
                  <th>{t.scanCount}</th>
                  <th>Last Activity</th>
                  <th>Status</th>
                  <th className="text-end">{t.actions}</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr key={patient.id}>
                    <td>{patient.patient_code}</td>
                    <td>{patient.full_name}</td>
                    <td>{patient.owner_username || '-'}</td>
                    <td>{patient.phone || '-'}</td>
                    <td>{patient.scan_count ?? 0}</td>
                    <td>{formatDate(patient.last_scan_at)}</td>
                    <td>
                      <span
                        className={`badge ${
                          patient.is_active ? 'text-bg-success' : 'text-bg-secondary'
                        }`}
                      >
                        {patient.is_active
                          ? t.adminPatientActive
                          : t.adminPatientArchived}
                      </span>
                    </td>
                    <td className="text-end">
                      <div className="d-flex gap-2 justify-content-end">
                        {patient.scan_count > 0 ? (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => onViewReports?.(patient)}
                            title="View reports"
                          >
                            {t.view}
                          </button>
                        ) : null}
                        {patient.is_active && (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-danger"
                            disabled={archivingId === patient.id}
                            onClick={() => handleArchive(patient)}
                          >
                            {archivingId === patient.id ? 'Archiving...' : 'Archive'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="d-flex gap-2 justify-content-center mt-3">
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={page === 1}
                onClick={() => setPage((prev) => prev - 1)}
              >
                Prev
              </button>
              <span className="align-self-center text-muted small">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={page === totalPages}
                onClick={() => setPage((prev) => prev + 1)}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      )}
    </SectionCard>
  )
}

function ActivityFeed({ items, loading, error, onRefresh, onViewPatient }) {
  const { t } = useLang()

  if (error) {
    return (
      <SectionCard
        title="Recent Activity"
        subtitle="Latest scans and reports"
        actions={
          <button className="btn btn-outline-secondary btn-sm" onClick={onRefresh}>
            {t.retry}
          </button>
        }
      >
        <div className="alert alert-danger py-2">{error}</div>
      </SectionCard>
    )
  }

  if (loading) {
    return (
      <SectionCard title="Recent Activity" subtitle="Latest scans and reports">
        <div className="text-center py-4">
          <div className="spinner-border text-primary" />
        </div>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      title="Recent Activity"
      subtitle="Latest scans and reports"
      actions={
        <button className="btn btn-outline-secondary btn-sm" onClick={onRefresh}>
          {t.refresh}
        </button>
      }
    >
      {items.length === 0 ? (
        <div className="eta-admin-empty">No activity yet.</div>
      ) : (
        <div className="table-responsive">
          <table className="table align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Scan ID</th>
                <th>Patient</th>
                <th>Doctor</th>
                <th>Type</th>
                <th>Status</th>
                <th>{t.diagnosis}</th>
                <th>{t.severity}</th>
                <th>{t.confidence}</th>
                <th>{t.createdAt}</th>
                <th className="text-end">{t.actions}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <tr key={entry.scan_id}>
                  <td>{entry.scan_id}</td>
                  <td>
                    {entry.patient ? (
                      <>
                        <div className="fw-semibold">{entry.patient.full_name}</div>
                        <div className="text-muted small">
                          {entry.patient.patient_code}
                        </div>
                      </>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>{entry.doctor || '-'}</td>
                  <td>{entry.scan_type || '-'}</td>
                  <td>{entry.status || '-'}</td>
                  <td>{entry.report?.diagnosis || '-'}</td>
                  <td>
                    <SeverityBadge severity={entry.report?.severity} />
                  </td>
                  <td>
                    {entry.report?.confidence_pct != null
                      ? `${entry.report.confidence_pct}%`
                      : '-'}
                  </td>
                  <td>{formatDate(entry.created_at)}</td>
                  <td className="text-end">
                    <button className="btn btn-sm btn-outline-secondary" disabled>
                      {t.view}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

function ArchivedPatientsTab() {
  const [patients, setPatients] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [restoring, setRestoring] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 20

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const loadArchived = async (nextPage = 1, nextQuery = query) => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/admin/archived-patients', {
        params: { page: nextPage, page_size: PAGE_SIZE, query: nextQuery },
      })
      setPatients(Array.isArray(data.items) ? data.items : [])
      setTotal(Number(data.total || 0))
      setPage(Number(data.page || nextPage))
    } catch (err) {
      setError(extractApiError(err, 'Failed to load archived patients.'))
      setPatients([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadArchived(1, '')
  }, [])

  const handleSearch = (event) => {
    event.preventDefault()
    setPage(1)
    loadArchived(1, query)
  }

  const handleRestore = async (patientId) => {
    setRestoring(patientId)
    setError('')
    setSuccess('')
    try {
      await api.post(`/admin/archived-patients/${patientId}/restore`)
      setSuccess('Patient restored successfully.')
      await loadArchived(page, query)
    } catch (err) {
      setError(err?.response?.data?.message || 'Failed to restore patient.')
    } finally {
      setRestoring(null)
    }
  }

  return (
    <SectionCard
      title="Archived Patients"
      subtitle="Restore archived patient records. These patients were previously soft-archived and their data is preserved."
    >
      <form onSubmit={handleSearch} className="row g-2 mb-3">
        <div className="col-md-6">
          <input
            className="form-control"
            placeholder="Search by code, name, or doctor"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-primary">Search</button>
        </div>
        {query ? (
          <div className="col-auto">
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={() => {
                setQuery('')
                setPage(1)
                loadArchived(1, '')
              }}
            >
              Clear
            </button>
          </div>
        ) : null}
      </form>

      {error && <div className="alert alert-danger py-2">{error}</div>}
      {success && <div className="alert alert-success py-2">{success}</div>}

      <p className="text-muted small mb-3">
        {total} archived patient{total !== 1 ? 's' : ''} found
      </p>

      {loading ? (
        <div className="text-center py-4">
          <div className="spinner-border text-primary" />
        </div>
      ) : patients.length === 0 ? (
        <div className="eta-admin-empty">No archived patients found.</div>
      ) : (
        <>
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead className="table-light">
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Age</th>
                  <th>Doctor</th>
                  <th>Scans</th>
                  <th>Archived</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr key={patient.id}>
                    <td>
                      <code className="text-muted">{patient.patient_code}</code>
                    </td>
                    <td className="fw-semibold">{patient.full_name}</td>
                    <td>{patient.age || '-'}</td>
                    <td className="text-muted">{patient.owner_username}</td>
                    <td>{patient.scan_count}</td>
                    <td className="text-muted small">{formatDate(patient.archived_date)}</td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-success"
                        disabled={restoring === patient.id}
                        onClick={() => handleRestore(patient.id)}
                      >
                        {restoring === patient.id ? 'Restoring...' : 'Restore'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <nav className="mt-3">
              <ul className="pagination justify-content-center mb-0">
                <li className={`page-item ${page === 1 ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => loadArchived(page - 1, query)}
                    disabled={page === 1}
                  >
                    Previous
                  </button>
                </li>
                {[...Array(totalPages)].map((_, idx) => (
                  <li
                    key={idx + 1}
                    className={`page-item ${page === idx + 1 ? 'active' : ''}`}
                  >
                    <button
                      className="page-link"
                      onClick={() => loadArchived(idx + 1, query)}
                    >
                      {idx + 1}
                    </button>
                  </li>
                ))}
                <li className={`page-item ${page === totalPages ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => loadArchived(page + 1, query)}
                    disabled={page === totalPages}
                  >
                    Next
                  </button>
                </li>
              </ul>
            </nav>
          )}
        </>
      )}
    </SectionCard>
  )
}

function mapReportsToActivity(items) {
  if (!Array.isArray(items)) {
    return []
  }
  return items.map((item) => ({
    scan_id: item.scan_id,
    scan_type: item.scan_type,
    status: item.report ? 'completed' : '-',
    created_at: item.created_at,
    doctor: item.doctor,
    patient: item.patient,
    report: item.report,
    has_report: Boolean(item.report),
  }))
}

function AdminPage() {
  const { t } = useLang()
  const [stats, setStats] = useState(null)
  const [statsError, setStatsError] = useState('')
  const [activeTab, setActiveTab] = useState('doctors')
  const [reportsFocus, setReportsFocus] = useState(null)
  const [activity, setActivity] = useState([])
  const [activityLoading, setActivityLoading] = useState(true)
  const [activityError, setActivityError] = useState('')

  useEffect(() => {
    api
      .get('/admin/stats')
      .then(({ data }) => {
        setStats(data)
        setStatsError('')
      })
      .catch((err) => {
        setStats(null)
        setStatsError(extractApiError(err, 'Failed to load admin stats.'))
      })
  }, [])

  const loadActivity = async () => {
    setActivityError('')
    setActivityLoading(true)
    try {
      const { data } = await api.get('/admin/activity', { params: { limit: 12 } })
      setActivity(Array.isArray(data.items) ? data.items : [])
    } catch (err) {
      if (err?.response?.status === 404) {
        try {
          const fallback = await api.get('/admin/reports', {
            params: { page: 1, page_size: 12 },
          })
          setActivity(mapReportsToActivity(fallback.data?.items))
          setActivityError('')
        } catch (fallbackErr) {
          setActivity([])
          setActivityError(
            extractApiError(fallbackErr, 'Failed to load activity.'),
          )
        }
      } else {
        setActivity([])
        setActivityError(extractApiError(err, 'Failed to load activity.'))
      }
    } finally {
      setActivityLoading(false)
    }
  }

  useEffect(() => {
    loadActivity()
  }, [])

  const focusReportsForPatient = (patient) => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    setReportsFocus({
      key: `patient-${patient.id}-${patient.last_scan_at || ''}`,
      query: patient.patient_code,
    })
    setActiveTab('reports')
  }

  return (
    <div className="eta-fade d-flex flex-column gap-4">
      <div className="eta-hero eta-admin-hero">
        <div className="eta-chip-row justify-content-start mb-3">
          <span className="eta-chip">Admin controls</span>
          <span className="eta-chip">Doctor accounts</span>
          <span className="eta-chip">Reports and activity</span>
        </div>
        <div className="row g-3 align-items-center">
          <div className="col-lg-8">
            <h3 className="mb-2">Admin command center</h3>
            <p className="eta-subtle mb-0">
              Manage doctors, audit patient records, monitor scan activity, and
              download every report generated in the system.
            </p>
          </div>
          <div className="col-lg-4">
            <div className="eta-admin-hero-note">
              Use the tabs below to switch between doctor setup, report review,
              and patient oversight.
            </div>
          </div>
        </div>
      </div>

      {statsError ? <div className="alert alert-danger py-2">{statsError}</div> : null}

      <div className="row g-3">
        <StatCard label="Doctors" value={stats?.total_doctors} color="primary" />
        <StatCard label="Patients" value={stats?.total_patients} color="success" />
        <StatCard label="Scans" value={stats?.total_scans} color="info" />
        <StatCard label="Reports" value={stats?.total_reports} color="warning" />
      </div>

      <div className="card eta-card p-2">
        <div className="eta-admin-tabs">
          <button
            className={`eta-admin-tab ${activeTab === 'doctors' ? 'active' : ''}`}
            onClick={() => setActiveTab('doctors')}
          >
            {t.adminDoctorsTab}
          </button>
          <button
            className={`eta-admin-tab ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => setActiveTab('reports')}
          >
            {t.adminReportsTab}
          </button>
          <button
            className={`eta-admin-tab ${activeTab === 'patients' ? 'active' : ''}`}
            onClick={() => setActiveTab('patients')}
          >
            {t.adminPatientsTab}
          </button>
          <button
            className={`eta-admin-tab ${activeTab === 'archived' ? 'active' : ''}`}
            onClick={() => setActiveTab('archived')}
          >
            Archived Patients
          </button>
        </div>
      </div>

      {activeTab === 'doctors' ? <DoctorsTab /> : null}
      {activeTab === 'reports' ? (
        <ReportsTab
          focus={reportsFocus}
          onBackToPatients={() => {
            setReportsFocus(null)
            setActiveTab('patients')
          }}
        />
      ) : null}
      {activeTab === 'patients' ? (
        <PatientsTab
          onViewReports={focusReportsForPatient}
          onArchiveDone={() => setActiveTab('archived')}
        />
      ) : null}
      {activeTab === 'archived' ? <ArchivedPatientsTab /> : null}

      <ActivityFeed
        items={activity}
        loading={activityLoading}
        error={activityError}
        onRefresh={loadActivity}
      />
    </div>
  )
}

export default AdminPage
