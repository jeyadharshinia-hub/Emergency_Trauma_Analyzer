import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import api from '../api'
import ConfidenceDonut from '../components/ConfidenceDonut'
import { useLang } from '../contexts/LangContext'
import { savePdfResponse } from '../utils/pdf'

const formatFieldLabel = (name) =>
  String(name || '')
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')

function ResultPage() {
  const { scanId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useLang()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [rerunning, setRerunning] = useState(false)
  const [pageError, setPageError] = useState('')
  const [actionError, setActionError] = useState('')
  const [scan, setScan] = useState(null)
  const [patient, setPatient] = useState(null)
  const [report, setReport] = useState(null)
  const [success, setSuccess] = useState('')

  const sourceParams = new URLSearchParams(location.search)
  const sourceRoute = sourceParams.get('from')
  const sourcePatientId = sourceParams.get('patient_id')
  const fromManagement = sourceRoute === 'management'

  const applyReportPayload = (res) => {
    setScan(res.data.scan)
    setPatient(res.data.patient || null)
    const r = res.data.report
    const suggested = Array.isArray(r.missing_fields) ? r.missing_fields : []
    const existingValues =
      r.missing_field_values && typeof r.missing_field_values === 'object'
        ? r.missing_field_values
        : {}
    const mergedValues = {}
    const patientRecord = res.data.patient || null
    suggested.forEach((name) => {
      // Pre-fill age from patient record if age field is missing
      if (name === 'age' && patientRecord && patientRecord.age) {
        mergedValues[name] = existingValues[name] || patientRecord.age
      } else {
        mergedValues[name] = existingValues[name] || ''
      }
    })
    Object.entries(existingValues).forEach(([name, value]) => {
      mergedValues[name] = value || ''
    })
    setReport({
      ...r,
      ai_summary_text: String(r.ai_summary_text || '').trim(),
      doctor_review_text: String(r.doctor_review_text || '').trim(),
      patient_summary_text: String(r.patient_summary_text || '').trim(),
      missing_fields: suggested,
      missing_field_values: mergedValues,
    })
  }

  const reloadReport = async () => {
    const res = await api.get(`/reports/${scanId}`)
    applyReportPayload(res)
  }

  useEffect(() => {
    let mounted = true
    api
      .get(`/reports/${scanId}`)
      .then((res) => {
        if (!mounted) return
        applyReportPayload(res)
      })
      .catch((err) => {
        if (mounted) {
          setPageError(err?.response?.data?.error || 'Failed to fetch report')
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
  }, [scanId])

  const onChange = (key, value) => {
    setReport((prev) => ({ ...prev, [key]: value }))
  }

  const onMissingFieldValueChange = (name, value) => {
    setReport((prev) => ({
      ...prev,
      missing_field_values: {
        ...(prev.missing_field_values || {}),
        [name]: value,
      },
    }))
  }

  const save = async () => {
    if (!report) return
    setSaving(true)
    setSuccess('')
    setActionError('')
    try {
      const missingFieldValues =
        report.missing_field_values && typeof report.missing_field_values === 'object'
          ? report.missing_field_values
          : {}
      const unresolvedFields = Object.entries(missingFieldValues)
        .filter(([, value]) => !String(value || '').trim())
        .map(([name]) => name)

      const payload = {
        patient_name: report.patient_name,
        diagnosis: report.diagnosis,
        severity: report.severity,
        doctor_notes: report.doctor_review_text,
        doctor_review_text: report.doctor_review_text,
        patient_summary_text: report.patient_summary_text,
        missing_fields: unresolvedFields,
        missing_field_values: missingFieldValues,
      }
      const res = await api.put(`/reports/${scanId}`, payload)
      setReport((prev) => ({
        ...prev,
        ...res.data.report,
        ai_summary_text: String(res.data.report.ai_summary_text || '').trim(),
        doctor_review_text: String(res.data.report.doctor_review_text || '').trim(),
        patient_summary_text: String(res.data.report.patient_summary_text || '').trim(),
        missing_fields: Array.isArray(res.data.report.missing_fields)
          ? res.data.report.missing_fields
          : [],
        missing_field_values:
          res.data.report.missing_field_values &&
          typeof res.data.report.missing_field_values === 'object'
            ? res.data.report.missing_field_values
            : {},
      }))
      setSuccess('Report saved')
    } catch (err) {
      setActionError(err?.response?.data?.error || 'Failed to save report')
    } finally {
      setSaving(false)
    }
  }

  const downloadPdf = async () => {
    setDownloading(true)
    setActionError('')
    setSuccess('')
    try {
      console.log('[DEBUG] Starting PDF download for scan:', scanId)
      
      // Get patient name from report data if available
      const patientName = report?.patient_name || 'Unknown'
      const safeName = patientName.replace(/[^\w\s\-]/g, '_').slice(0, 30)
      const dateStr = new Date().toISOString().split('T')[0]
      const fallbackFilename = `eta_report_${safeName}_${dateStr}.pdf`
      console.log('[DEBUG] Fallback filename:', fallbackFilename)
      
      const response = await api.get(`/reports/${scanId}/pdf`, {
        responseType: 'blob',
        validateStatus: () => true,
      })
      
      console.log('[DEBUG] Response status:', response.status)
      console.log('[DEBUG] Response headers:', JSON.stringify(response.headers, null, 2))
      console.log('[DEBUG] Response data type:', response.data?.type)
      console.log('[DEBUG] Response data size:', response.data?.size)
      console.log('[DEBUG] Response data:', response.data)
      
      await savePdfResponse(response, fallbackFilename)
      setSuccess('PDF report downloaded successfully')
    } catch (err) {
      console.error('[DEBUG] Error downloading PDF:', err)
      console.error('[DEBUG] Error stack:', err.stack)
      setActionError(err?.message || 'Failed to download PDF report')
    } finally {
      setDownloading(false)
    }
  }

  const backToSource = () => {
    if (fromManagement) {
      const params = new URLSearchParams({ open_logs: '1' })
      if (sourcePatientId) {
        params.set('patient_id', sourcePatientId)
      }
      navigate(`/management?${params.toString()}`)
      return
    }
    navigate('/scan')
  }

  const rerunLiveAi = async () => {
    setRerunning(true)
    setActionError('')
    setSuccess('')
    try {
      await api.post(`/scans/${scanId}/reanalyze-live`)
      await reloadReport()
      setSuccess(t.reanalyzeSuccess)
    } catch (err) {
      setActionError(err?.response?.data?.error || t.reanalyzeFailed)
    } finally {
      setRerunning(false)
    }
  }

  const severityKey = (report?.severity || 'unknown').toLowerCase()
  const severityClass = `eta-severity eta-severity-${
    ['critical', 'moderate', 'mild'].includes(severityKey) ? severityKey : 'unknown'
  }`
  const missingInputEntries = Object.entries(report?.missing_field_values || {})

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status" />
      </div>
    )
  }

  if (!report) {
    if (pageError) {
      return <div className="alert alert-danger">{pageError}</div>
    }
    return <div className="alert alert-warning">No report data available for this scan.</div>
  }

  return (
    <div className="eta-fade d-flex flex-column gap-2">
      <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={backToSource}>
          {fromManagement ? t.backToManagement : t.backToUpload}
        </button>
        <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => navigate('/management')}>
          {t.goToManagement}
        </button>
      </div>
      <div className="row g-3">
      <div className="col-lg-4">
        <div className="eta-sticky">
          <div className="card eta-card p-3">
            <div className="d-flex justify-content-between align-items-start mb-3 gap-2">
              <h5 className="mb-0">Scan Result</h5>
              <span className={`badge ${report.ai_source === 'real' ? 'text-bg-success' : 'text-bg-warning'}`}>
                {report.ai_source === 'real' ? 'Live AI' : 'Fallback AI'}
              </span>
            </div>
            {scan?.processed_image_url && (
              <img src={scan.processed_image_url} alt="Uploaded scan" className="eta-result-image mb-3" />
            )}
            <ConfidenceDonut value={report.confidence_pct} />
            <div className="mt-3 d-flex flex-column gap-2">
              <div>
                <div className="eta-section-title">{t.diagnosis}</div>
                <div>{report.diagnosis || '-'}</div>
              </div>
              <div className="d-flex align-items-center gap-2">
                <span className="eta-section-title mb-0">{t.severity}</span>
                <span className={severityClass}>{report.severity}</span>
              </div>
              <div>
                <span className="eta-section-title mb-0">{t.confidence}</span>
                <span className="ms-2 fw-semibold">{report.confidence_pct}%</span>
              </div>
            </div>
            {report.ai_warning && <div className="alert alert-warning py-2 mt-3 mb-0">{report.ai_warning}</div>}
          </div>
        </div>
      </div>

      <div className="col-lg-8">
        <div className="card eta-card p-3 p-md-4">
          <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
            <h5 className="mb-0">Report Editor</h5>
            <div className="d-flex gap-2 flex-wrap">
              <button className="btn btn-outline-primary" onClick={rerunLiveAi} disabled={rerunning}>
                {rerunning ? t.reanalyzing : t.reanalyzeLiveAi}
              </button>
              <button className="btn btn-success" onClick={downloadPdf} disabled={downloading}>
                {downloading ? 'Downloading...' : t.downloadPdf}
              </button>
            </div>
          </div>
          {actionError && <div className="alert alert-danger py-2">{actionError}</div>}
          {success && <div className="alert alert-success py-2">{success}</div>}
          <div className="row g-3">
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">{t.linkedPatient}</div>
                {patient ? (
                  <div className="row g-2">
                    <div className="col-md-6">
                      <strong>{t.patientCode}:</strong> {patient.patient_code}
                    </div>
                    <div className="col-md-6">
                      <strong>{t.fullName}:</strong> {patient.full_name}
                    </div>
                    <div className="col-md-4">
                      <strong>{t.age}:</strong> {patient.age ?? '-'}
                    </div>
                    <div className="col-md-4">
                      <strong>{t.gender}:</strong> {patient.gender || '-'}
                    </div>
                    <div className="col-md-4">
                      <strong>{t.phone}:</strong> {patient.phone || '-'}
                    </div>
                  </div>
                ) : (
                  <p className="eta-subtle mb-0">{t.noPatientLinked}</p>
                )}
              </div>
            </div>
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">Clinical Basics</div>
                <div className="row g-3">
                  <div className="col-md-6">
                    <label className="form-label">{t.patientName}</label>
                    <input
                      className="form-control"
                      value={report.patient_name || ''}
                      onChange={(e) => onChange('patient_name', e.target.value)}
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">{t.severity}</label>
                    <select
                      className="form-select"
                      value={report.severity || 'unknown'}
                      onChange={(e) => onChange('severity', e.target.value)}
                    >
                      <option value="critical">critical</option>
                      <option value="moderate">moderate</option>
                      <option value="mild">mild</option>
                      <option value="unknown">unknown</option>
                    </select>
                  </div>
                  <div className="col-12">
                    <label className="form-label">{t.diagnosis}</label>
                    <input
                      className="form-control"
                      value={report.diagnosis || ''}
                      onChange={(e) => onChange('diagnosis', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">{t.aiSummary}</div>
                <p className="eta-subtle mb-2">{t.aiSummaryHelp}</p>
                <textarea
                  rows={4}
                  className="form-control"
                  value={report.ai_summary_text || ''}
                  readOnly
                />
              </div>
            </div>
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">{t.doctorReview}</div>
                <textarea
                  rows={4}
                  className="form-control"
                  value={report.doctor_review_text || ''}
                  onChange={(e) => onChange('doctor_review_text', e.target.value)}
                />
              </div>
            </div>
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">{t.patientSummary}</div>
                <textarea
                  rows={4}
                  className="form-control"
                  value={report.patient_summary_text || ''}
                  onChange={(e) => onChange('patient_summary_text', e.target.value)}
                />
              </div>
            </div>
            <div className="col-12">
              <div className="eta-card-soft p-3">
                <div className="eta-section-title">Required Clinical Inputs</div>
                {missingInputEntries.length === 0 ? (
                  <p className="eta-subtle mb-0">No additional fields suggested by AI.</p>
                ) : (
                  <div className="row g-3">
                    {missingInputEntries.map(([name, value]) => (
                      <div className="col-md-6" key={name}>
                        <label className="form-label">{formatFieldLabel(name)}</label>
                        <input
                          className="form-control"
                          value={value || ''}
                          onChange={(e) => onMissingFieldValueChange(name, e.target.value)}
                          placeholder={`Enter ${formatFieldLabel(name)}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          <p className="small eta-subtle mt-3 mb-2">{t.aiDisclaimer}</p>
          <div className="d-flex gap-2 flex-wrap">
            <button className="btn btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Saving...' : t.saveChanges}
            </button>
          </div>
        </div>
      </div>
    </div>
    </div>
  )
}

export default ResultPage
