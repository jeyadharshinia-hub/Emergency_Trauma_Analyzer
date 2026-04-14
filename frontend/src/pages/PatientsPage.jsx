import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '../api'
import { useLang } from '../contexts/LangContext'
import { savePdfResponse } from '../utils/pdf'

const initialPatientForm = {
  full_name: '',
  age: '',
  gender: 'unknown',
  phone: '',
  notes: '',
}

const LOGS_PAGE_SIZE = 10

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString()
}

function PatientsPage({ embedded = false }) {
  const { t } = useLang()
  const navigate = useNavigate()
  const location = useLocation()

  const [patients, setPatients] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [creating, setCreating] = useState(false)
  const [createForm, setCreateForm] = useState(initialPatientForm)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(initialPatientForm)
  const [busyId, setBusyId] = useState(null)

  const [logsOpen, setLogsOpen] = useState(false)
  const [logsPatient, setLogsPatient] = useState(null)
  const [logsItems, setLogsItems] = useState([])
  const [logsQuery, setLogsQuery] = useState('')
  const [logsStatus, setLogsStatus] = useState('all')
  const [logsPage, setLogsPage] = useState(1)
  const [logsTotal, setLogsTotal] = useState(0)
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsError, setLogsError] = useState('')
  const [logsSuccess, setLogsSuccess] = useState('')
  const [downloadingLogScanId, setDownloadingLogScanId] = useState(null)
  const [rerunningLogScanId, setRerunningLogScanId] = useState(null)
  const autoOpenLogsKeyRef = useRef('')

  const logsTotalPages = useMemo(
    () => Math.max(1, Math.ceil(logsTotal / LOGS_PAGE_SIZE)),
    [logsTotal],
  )

  const loadPatients = async (nextQuery = query) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/patients', { params: { query: nextQuery, page_size: 200 } })
      setPatients(Array.isArray(res.data.items) ? res.data.items : [])
    } catch (err) {
      setError(
        err?.response?.status === 403
          ? t.accessDenied
          : err?.response?.data?.error || 'Failed to load patients.',
      )
    } finally {
      setLoading(false)
    }
  }

  const loadPatientLogs = async (patientId, nextPage, nextQuery, nextStatus) => {
    setLogsLoading(true)
    setLogsError('')
    setLogsSuccess('')
    try {
      const res = await api.get('/reports/history', {
        params: {
          patient_id: patientId,
          page: nextPage,
          page_size: LOGS_PAGE_SIZE,
          query: nextQuery,
          status: nextStatus,
        },
      })
      const payload = res.data || {}
      setLogsItems(Array.isArray(payload.items) ? payload.items : [])
      setLogsTotal(Number(payload.total || 0))
      setLogsPage(Number(payload.page || nextPage))
    } catch (err) {
      setLogsError(err?.response?.data?.error || 'Failed to load patient logs.')
    } finally {
      setLogsLoading(false)
    }
  }

  useEffect(() => {
    loadPatients('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onCreatePatient = async (event) => {
    event.preventDefault()
    setCreating(true)
    setError('')
    setSuccess('')
    try {
      await api.post('/patients', createForm)
      setCreateForm(initialPatientForm)
      setSuccess(t.patientCreated)
      await loadPatients(query)
    } catch (err) {
      setError(
        err?.response?.status === 403
          ? t.accessDenied
          : err?.response?.data?.error || 'Failed to create patient.',
      )
    } finally {
      setCreating(false)
    }
  }

  const onStartEdit = (entry) => {
    setEditingId(entry.id)
    setEditForm({
      full_name: entry.full_name || '',
      age: entry.age ?? '',
      gender: entry.gender || 'unknown',
      phone: entry.phone || '',
      notes: entry.notes || '',
    })
    setError('')
    setSuccess('')
  }

  const onUpdatePatient = async (patientId) => {
    setBusyId(patientId)
    setError('')
    setSuccess('')
    try {
      await api.put(`/patients/${patientId}`, editForm)
      setEditingId(null)
      setSuccess(t.patientUpdated)
      await loadPatients(query)
    } catch (err) {
      setError(
        err?.response?.status === 403
          ? t.accessDenied
          : err?.response?.data?.error || 'Failed to update patient.',
      )
    } finally {
      setBusyId(null)
    }
  }

  const onArchivePatient = async (entry) => {
    if (!window.confirm(`Archive patient "${entry.full_name}"?`)) {
      return
    }
    setBusyId(entry.id)
    setError('')
    setSuccess('')
    try {
      await api.delete(`/patients/${entry.id}`)
      setSuccess(t.patientArchived)
      await loadPatients(query)
    } catch (err) {
      setError(
        err?.response?.status === 403
          ? t.accessDenied
          : err?.response?.data?.error || 'Failed to archive patient.',
      )
    } finally {
      setBusyId(null)
    }
  }

  const onSearch = async (event) => {
    event.preventDefault()
    await loadPatients(query)
  }

  const openLogsModal = async (patient) => {
    setLogsPatient(patient)
    setLogsOpen(true)
    setLogsQuery('')
    setLogsStatus('all')
    setLogsPage(1)
    setLogsTotal(0)
    setLogsItems([])
    setLogsError('')
    setLogsSuccess('')
    await loadPatientLogs(patient.id, 1, '', 'all')
  }

  const closeLogsModal = () => {
    setLogsOpen(false)
    setLogsPatient(null)
    setLogsItems([])
    setLogsQuery('')
    setLogsStatus('all')
    setLogsPage(1)
    setLogsTotal(0)
    setLogsError('')
    setLogsSuccess('')
    setDownloadingLogScanId(null)
    setRerunningLogScanId(null)
  }

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const openLogs = params.get('open_logs') === '1'
    const patientId = params.get('patient_id')
    if (!openLogs || !patientId || loading) return

    const routeKey = `${location.pathname}?${location.search}`
    if (autoOpenLogsKeyRef.current === routeKey) return
    autoOpenLogsKeyRef.current = routeKey

    navigate({ pathname: location.pathname }, { replace: true })

    const targetPatient = patients.find((entry) => String(entry.id) === String(patientId))
    if (targetPatient) {
      void openLogsModal(targetPatient)
    }
  }, [location.pathname, location.search, loading, navigate, patients])

  const onLogsSearch = async (event) => {
    event.preventDefault()
    if (!logsPatient) return
    await loadPatientLogs(logsPatient.id, 1, logsQuery, logsStatus)
  }

  const onLogsStatusChange = async (event) => {
    if (!logsPatient) return
    const nextStatus = event.target.value
    setLogsStatus(nextStatus)
    await loadPatientLogs(logsPatient.id, 1, logsQuery, nextStatus)
  }

  const onLogsPageChange = async (nextPage) => {
    if (!logsPatient) return
    if (nextPage < 1 || nextPage > logsTotalPages || nextPage === logsPage) return
    await loadPatientLogs(logsPatient.id, nextPage, logsQuery, logsStatus)
  }

  const downloadLogPdf = async (scanId) => {
    setDownloadingLogScanId(scanId)
    setLogsError('')
    try {
      console.log('[DEBUG] Starting PDF download for scan:', scanId)
      
      // Get patient name from logsPatient if available
      const patientName = logsPatient?.full_name || 'Unknown'
      const safeName = patientName.replace(/[^\w\s\-]/g, '_').slice(0, 30)
      const dateStr = new Date().toISOString().split('T')[0]
      const fallbackFilename = `Report_${safeName}_${dateStr}.pdf`
      console.log('[DEBUG] Fallback filename:', fallbackFilename)
      
      const response = await api.get(`/reports/${scanId}/pdf`, {
        responseType: 'blob',
        validateStatus: () => true,
        withCredentials: true,
      })
      
      console.log('[DEBUG] Response status:', response.status)
      console.log('[DEBUG] Response headers:', response.headers)
      console.log('[DEBUG] Response data type:', response.data?.type)
      console.log('[DEBUG] Response data size:', response.data?.size)
      
      await savePdfResponse(response, fallbackFilename)
      setLogsSuccess(t.pdfReady || 'PDF report downloaded successfully')
    } catch (err) {
      console.error('[DEBUG] Error downloading PDF:', err)
      setLogsError(err?.message || 'Failed to download PDF report.')
    } finally {
      setDownloadingLogScanId(null)
    }
  }

  const rerunLogAi = async (scanId) => {
    if (!logsPatient) return
    setRerunningLogScanId(scanId)
    setLogsError('')
    setLogsSuccess('')
    try {
      await api.post(`/scans/${scanId}/reanalyze-live`)
      await loadPatientLogs(logsPatient.id, logsPage, logsQuery, logsStatus)
      setLogsSuccess(t.reanalyzeSuccess)
    } catch (err) {
      setLogsError(err?.response?.data?.error || t.reanalyzeFailed)
    } finally {
      setRerunningLogScanId(null)
    }
  }

  const viewLog = (scanId) => {
    const params = new URLSearchParams({ from: 'management' })
    if (logsPatient?.id != null) {
      params.set('patient_id', String(logsPatient.id))
    }
    closeLogsModal()
    navigate(`/scan/${scanId}/result?${params.toString()}`)
  }

  return (
    <div className="eta-fade d-flex flex-column gap-3">
      {!embedded && (
        <div className="card eta-card p-3 p-md-4">
          <h4 className="mb-1">{t.patientsTitle}</h4>
          <p className="eta-subtle mb-0">{t.patientsSubtitle}</p>
        </div>
      )}

      <div className="row g-3">
        <div className="col-lg-4">
          <div className="card eta-card p-3">
            <div className="eta-section-title">{t.createPatient}</div>
            <p className="eta-subtle mb-2">{t.patientFormHintDoctor}</p>
            <form className="d-flex flex-column gap-2" onSubmit={onCreatePatient}>
              <input
                className="form-control"
                placeholder={t.fullName}
                value={createForm.full_name}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, full_name: event.target.value }))}
              />
              <input
                className="form-control"
                type="number"
                placeholder={t.age}
                value={createForm.age}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, age: event.target.value }))}
              />
              <select
                className="form-select"
                value={createForm.gender}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, gender: event.target.value }))}
              >
                <option value="male">{t.genderMale}</option>
                <option value="female">{t.genderFemale}</option>
                <option value="other">{t.genderOther}</option>
                <option value="unknown">{t.genderUnknown}</option>
              </select>
              <input
                className="form-control"
                placeholder={t.phone}
                value={createForm.phone}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, phone: event.target.value }))}
              />
              <textarea
                className="form-control"
                rows={2}
                placeholder={t.notes}
                value={createForm.notes}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, notes: event.target.value }))}
              />
              <button className="btn btn-primary" type="submit" disabled={creating}>
                {creating ? `${t.createPatient}...` : t.createPatient}
              </button>
            </form>
          </div>
        </div>

        <div className="col-lg-8">
          <div className="card eta-card p-3">
            <form className="d-flex gap-2 mb-3" onSubmit={onSearch}>
              <input
                className="form-control"
                placeholder={t.searchPatientsPlaceholder}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="btn btn-outline-primary" type="submit">
                {t.search}
              </button>
            </form>

            {error && <div className="alert alert-danger py-2">{error}</div>}
            {success && <div className="alert alert-success py-2">{success}</div>}

            {loading ? (
              <div className="d-flex justify-content-center py-4">
                <div className="spinner-border text-primary" role="status" />
              </div>
            ) : patients.length === 0 ? (
              <div className="eta-subtle">{t.noPatientsFound}</div>
            ) : (
              <div className="table-responsive">
                <table className="table align-middle">
                  <thead>
                    <tr>
                      <th>{t.patientCode}</th>
                      <th>{t.fullName}</th>
                      <th>{t.age}</th>
                      <th>{t.gender}</th>
                      <th>{t.phone}</th>
                      <th>{t.actions}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {patients.map((entry) => (
                      <tr key={entry.id}>
                        <td>{entry.patient_code}</td>
                        <td>
                          {editingId === entry.id ? (
                            <input
                              className="form-control"
                              value={editForm.full_name}
                              onChange={(event) =>
                                setEditForm((prev) => ({ ...prev, full_name: event.target.value }))
                              }
                            />
                          ) : (
                            entry.full_name
                          )}
                        </td>
                        <td>
                          {editingId === entry.id ? (
                            <input
                              className="form-control"
                              type="number"
                              value={editForm.age}
                              onChange={(event) =>
                                setEditForm((prev) => ({ ...prev, age: event.target.value }))
                              }
                            />
                          ) : (
                            entry.age ?? '-'
                          )}
                        </td>
                        <td>
                          {editingId === entry.id ? (
                            <select
                              className="form-select"
                              value={editForm.gender}
                              onChange={(event) =>
                                setEditForm((prev) => ({ ...prev, gender: event.target.value }))
                              }
                            >
                              <option value="male">{t.genderMale}</option>
                              <option value="female">{t.genderFemale}</option>
                              <option value="other">{t.genderOther}</option>
                              <option value="unknown">{t.genderUnknown}</option>
                            </select>
                          ) : (
                            entry.gender
                          )}
                        </td>
                        <td>
                          {editingId === entry.id ? (
                            <input
                              className="form-control"
                              value={editForm.phone}
                              onChange={(event) =>
                                setEditForm((prev) => ({ ...prev, phone: event.target.value }))
                              }
                            />
                          ) : (
                            entry.phone || '-'
                          )}
                        </td>
                        <td>
                          {editingId === entry.id ? (
                            <div className="d-flex flex-column gap-2">
                              <textarea
                                className="form-control"
                                rows={2}
                                value={editForm.notes}
                                onChange={(event) =>
                                  setEditForm((prev) => ({ ...prev, notes: event.target.value }))
                                }
                              />
                              <div className="d-flex gap-2">
                                <button
                                  className="btn btn-sm btn-primary"
                                  type="button"
                                  disabled={busyId === entry.id}
                                  onClick={() => onUpdatePatient(entry.id)}
                                >
                                  {t.save}
                                </button>
                                <button
                                  className="btn btn-sm btn-outline-secondary"
                                  type="button"
                                  onClick={() => setEditingId(null)}
                                >
                                  {t.cancel}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="d-flex gap-2 flex-wrap">
                              <button
                                className="btn btn-sm btn-outline-primary"
                                type="button"
                                onClick={() => onStartEdit(entry)}
                              >
                                {t.edit}
                              </button>
                              <button
                                className="btn btn-sm btn-outline-secondary"
                                type="button"
                                onClick={() => openLogsModal(entry)}
                              >
                                {t.patientLogs}
                              </button>
                              <button
                                className="btn btn-sm btn-outline-danger"
                                type="button"
                                disabled={busyId === entry.id}
                                onClick={() => onArchivePatient(entry)}
                              >
                                {t.archivePatient}
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {logsOpen && (
        <>
          <div className="modal fade show d-block eta-patient-logs-modal" tabIndex="-1" onClick={closeLogsModal}>
            <div className="modal-dialog modal-xl modal-dialog-scrollable" onClick={(event) => event.stopPropagation()}>
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    {t.patientLogsTitle}
                    {logsPatient ? `: ${logsPatient.patient_code} - ${logsPatient.full_name}` : ''}
                  </h5>
                  <button type="button" className="btn-close" onClick={closeLogsModal} />
                </div>
                <div className="modal-body">
                  <form className="row g-2 mb-3" onSubmit={onLogsSearch}>
                    <div className="col-md-8">
                      <input
                        className="form-control"
                        value={logsQuery}
                        placeholder={t.searchLogsPlaceholder}
                        onChange={(event) => setLogsQuery(event.target.value)}
                      />
                    </div>
                    <div className="col-md-4">
                      <select className="form-select" value={logsStatus} onChange={onLogsStatusChange}>
                        <option value="all">{t.logStatusAll}</option>
                        <option value="with_report">{t.logStatusWithReport}</option>
                        <option value="no_report">{t.logStatusNoReport}</option>
                      </select>
                    </div>
                    <div className="col-12 d-flex gap-2">
                      <button className="btn btn-outline-primary" type="submit">
                        {t.search}
                      </button>
                    </div>
                  </form>

                  {logsError && <div className="alert alert-danger py-2">{logsError}</div>}
                  {logsSuccess && <div className="alert alert-success py-2">{logsSuccess}</div>}

                  {logsLoading ? (
                    <div className="d-flex justify-content-center py-4">
                      <div className="spinner-border text-primary" role="status" />
                    </div>
                  ) : logsItems.length === 0 ? (
                    <div className="eta-subtle">{t.noPatientLogsFound}</div>
                  ) : (
                    <div className="table-responsive">
                      <table className="table align-middle">
                        <thead>
                          <tr>
                            <th>{t.createdAt}</th>
                            <th>{t.scanId}</th>
                            <th>{t.scanType}</th>
                            <th>{t.status}</th>
                            <th>{t.diagnosis}</th>
                            <th>{t.severity}</th>
                            <th>{t.confidence}</th>
                            <th>{t.actions}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {logsItems.map((entry) => {
                            const report = entry.report || null
                            const hasReport = Boolean(entry.has_report && report)
                            return (
                              <tr key={entry.scan_id}>
                                <td>{formatDate(entry.created_at)}</td>
                                <td>{entry.scan_id}</td>
                                <td>{entry.scan_type || '-'}</td>
                                <td>{entry.analyze_status || '-'}</td>
                                <td>{report?.diagnosis || '-'}</td>
                                <td>{report?.severity || '-'}</td>
                                <td>{report ? `${report.confidence_pct ?? 0}%` : '-'}</td>
                                <td>
                                  <div className="d-flex gap-2 flex-wrap">
                                    <button
                                      type="button"
                                      className="btn btn-sm btn-outline-primary"
                                      disabled={!hasReport}
                                      onClick={() => viewLog(entry.scan_id)}
                                    >
                                      {t.view}
                                    </button>
                                    <button
                                      type="button"
                                      className="btn btn-sm btn-outline-warning"
                                      disabled={rerunningLogScanId === entry.scan_id}
                                      onClick={() => rerunLogAi(entry.scan_id)}
                                    >
                                      {rerunningLogScanId === entry.scan_id ? t.reanalyzing : t.reanalyzeLiveAi}
                                    </button>
                                    <button
                                      type="button"
                                      className="btn btn-sm btn-success"
                                      disabled={!hasReport || downloadingLogScanId === entry.scan_id}
                                      onClick={() => downloadLogPdf(entry.scan_id)}
                                    >
                                      {downloadingLogScanId === entry.scan_id ? t.downloading : t.downloadPdf}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                <div className="modal-footer d-flex justify-content-between">
                  <small className="eta-subtle">
                    {t.page} {logsPage} / {logsTotalPages}
                  </small>
                  <div className="d-flex gap-2">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      disabled={logsLoading || logsPage <= 1}
                      onClick={() => onLogsPageChange(logsPage - 1)}
                    >
                      {t.previous}
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      disabled={logsLoading || logsPage >= logsTotalPages}
                      onClick={() => onLogsPageChange(logsPage + 1)}
                    >
                      {t.next}
                    </button>
                    <button type="button" className="btn btn-sm btn-outline-dark" onClick={closeLogsModal}>
                      {t.closeLogs}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show eta-patient-logs-backdrop" />
        </>
      )}
    </div>
  )
}

export default PatientsPage
