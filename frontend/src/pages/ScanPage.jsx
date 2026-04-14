import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useLang } from '../contexts/LangContext'

const ANALYZE_ERROR_MESSAGES = {
  NON_MEDICAL_IMAGE: 'Upload a valid medical X-ray/CT/MRI scan image.',
  AI_UNAVAILABLE: 'AI service unavailable. Check API keys/network and retry.',
  AI_QUOTA_EXCEEDED: 'Gemini quota exceeded. Update billing/quota and retry.',
  AI_AUTH_INVALID: 'AI authentication failed. Check Gemini/Groq API keys.',
  AI_RESPONSE_INVALID: 'AI response invalid. Retry analysis.',
}

const initialPatientForm = {
  full_name: '',
  age: '',
  gender: 'unknown',
  phone: '',
  notes: '',
}

function ScanPage() {
  const { t } = useLang()
  const navigate = useNavigate()

  const [scanType, setScanType] = useState('xray')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [patients, setPatients] = useState([])
  const [patientsLoading, setPatientsLoading] = useState(true)
  const [selectedPatientId, setSelectedPatientId] = useState('')
  const [showCreatePatient, setShowCreatePatient] = useState(false)
  const [patientCreating, setPatientCreating] = useState(false)
  const [patientForm, setPatientForm] = useState(initialPatientForm)

  const fileInputRef = useRef(null)

  const loadPatients = async () => {
    setPatientsLoading(true)
    setError('')
    try {
      const res = await api.get('/patients', { params: { page_size: 200 } })
      const items = Array.isArray(res.data.items) ? res.data.items : []
      setPatients(items)
      if (items.some((entry) => String(entry.id) === String(selectedPatientId))) {
        return
      }
      setSelectedPatientId(items.length > 0 ? String(items[0].id) : '')
    } catch (err) {
      setError(err?.response?.status === 403 ? t.accessDenied : err?.response?.data?.error || 'Failed to load patients.')
    } finally {
      setPatientsLoading(false)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!selectedPatientId) {
      setError(t.patientRequiredUpload)
      return
    }
    if (!file) {
      setError('Please select an image')
      return
    }
    setLoading(true)
    setError('')
    setInfo('')
    try {
      const formData = new FormData()
      formData.append('scan_type', scanType)
      formData.append('patient_id', selectedPatientId)
      formData.append('file', file)

      const uploadRes = await api.post('/scans', formData)
      const scanId = uploadRes.data.scan.id
      await api.post(`/scans/${scanId}/analyze`)
      navigate(`/scan/${scanId}/result`)
    } catch (err) {
      const code = err?.response?.data?.code
      setError(err?.response?.data?.error || ANALYZE_ERROR_MESSAGES[code] || 'Failed to analyze scan')
    } finally {
      setLoading(false)
    }
  }

  const onPickFile = (event) => {
    const selected = event.target.files?.[0] || null
    setFile(selected)
    setPreview((prev) => {
      if (prev) {
        URL.revokeObjectURL(prev)
      }
      return selected ? URL.createObjectURL(selected) : ''
    })
  }

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const openCreatePatientModal = () => {
    setShowCreatePatient(true)
    setError('')
    setInfo('')
  }

  const closeCreatePatientModal = () => {
    setShowCreatePatient(false)
  }

  const onCreatePatient = async () => {
    setPatientCreating(true)
    setError('')
    setInfo('')
    try {
      const payload = { ...patientForm }
      const res = await api.post('/patients', payload)
      const created = res.data.patient
      setPatients((prev) => [created, ...prev.filter((entry) => entry.id !== created.id)])
      setSelectedPatientId(String(created.id))
      setPatientForm(initialPatientForm)
      closeCreatePatientModal()
      setInfo(t.patientCreated)
    } catch (err) {
      setError(err?.response?.status === 403 ? t.accessDenied : err?.response?.data?.error || 'Failed to create patient.')
    } finally {
      setPatientCreating(false)
    }
  }

  useEffect(() => {
    loadPatients()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    return () => {
      if (preview) {
        URL.revokeObjectURL(preview)
      }
    }
  }, [preview])

  return (
    <div className="row justify-content-center eta-fade">
      <div className="col-lg-8 col-xl-7">
        <div className="card eta-card p-4">
          <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
            <h4 className="mb-0">{t.uploadTitle}</h4>
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/dashboard')}>
              {t.backToDashboard}
            </button>
          </div>
          <p className="eta-subtle mb-3">
            Upload a clear trauma scan image. ETA will preprocess the image, run AI extraction, and
            open an editable report.
          </p>
          {info && <div className="alert alert-success py-2">{info}</div>}
          {error && <div className="alert alert-danger py-2">{error}</div>}

          <form onSubmit={submit} className="d-flex flex-column gap-3">
            <div className="eta-card-soft p-3">
              <div className="d-flex justify-content-between align-items-center mb-2 gap-2 flex-wrap">
                <label className="form-label mb-0">{t.selectPatient}</label>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-primary"
                  onClick={openCreatePatientModal}
                >
                  {t.createPatientInline}
                </button>
              </div>
              <p className="eta-subtle mb-2">
                {t.scanPatientHintDoctor}
              </p>
              <select
                className="form-select"
                value={selectedPatientId}
                onChange={(event) => setSelectedPatientId(event.target.value)}
                disabled={patientsLoading}
              >
                <option value="">{t.selectPatientPlaceholder}</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.patient_code} - {patient.full_name}
                  </option>
                ))}
              </select>
              {patientsLoading && <small className="eta-subtle">{t.loadingPatients}</small>}
            </div>

            <div>
              <label className="form-label">{t.scanType}</label>
              <select
                value={scanType}
                onChange={(event) => setScanType(event.target.value)}
                className="form-select"
              >
                <option value="xray">X-ray</option>
                <option value="ct">CT</option>
                <option value="mri">MRI</option>
              </select>
            </div>

            <div className="eta-upload-drop">
              <label className="form-label">{t.scanFile}</label>
              <input
                ref={fileInputRef}
                id="eta-scan-file-input"
                type="file"
                accept=".png,.jpg,.jpeg"
                className="d-none"
                onChange={onPickFile}
              />
              <div className="d-flex flex-wrap align-items-center gap-2">
                <button type="button" className="btn btn-outline-primary btn-sm" onClick={openFilePicker}>
                  {file ? t.changeImage : t.chooseImage}
                </button>
                <span className="eta-file-name">{file ? file.name : t.noFileSelected}</span>
              </div>
              <small className="eta-subtle d-block mt-2">Accepted types: JPG, JPEG, PNG</small>
            </div>

            {preview && <img src={preview} alt="Scan preview" className="eta-preview-image" />}

            <button
              className="btn btn-primary"
              disabled={loading || !file || !selectedPatientId}
            >
              {loading ? 'Analyzing...' : t.analyze}
            </button>
          </form>
        </div>
      </div>

      {showCreatePatient && (
        <>
          <div
            className="modal fade show d-block eta-create-patient-modal"
            tabIndex="-1"
            onClick={closeCreatePatientModal}
          >
            <div className="modal-dialog modal-lg" onClick={(event) => event.stopPropagation()}>
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">{t.createPatient}</h5>
                  <button type="button" className="btn-close" onClick={closeCreatePatientModal} />
                </div>
                <div className="modal-body">
                  <div className="row g-2">
                    <div className="col-md-6">
                      <input
                        className="form-control"
                        placeholder={t.fullName}
                        value={patientForm.full_name}
                        onChange={(event) =>
                          setPatientForm((prev) => ({ ...prev, full_name: event.target.value }))
                        }
                      />
                    </div>
                    <div className="col-md-3">
                      <input
                        className="form-control"
                        type="number"
                        placeholder={t.age}
                        value={patientForm.age}
                        onChange={(event) =>
                          setPatientForm((prev) => ({ ...prev, age: event.target.value }))
                        }
                      />
                    </div>
                    <div className="col-md-3">
                      <select
                        className="form-select"
                        value={patientForm.gender}
                        onChange={(event) =>
                          setPatientForm((prev) => ({ ...prev, gender: event.target.value }))
                        }
                      >
                        <option value="male">{t.genderMale}</option>
                        <option value="female">{t.genderFemale}</option>
                        <option value="other">{t.genderOther}</option>
                        <option value="unknown">{t.genderUnknown}</option>
                      </select>
                    </div>
                    <div className="col-md-6">
                      <input
                        className="form-control"
                        placeholder={t.phone}
                        value={patientForm.phone}
                        onChange={(event) =>
                          setPatientForm((prev) => ({ ...prev, phone: event.target.value }))
                        }
                      />
                    </div>
                    <div className="col-md-6">
                      <input
                        className="form-control"
                        placeholder={t.notes}
                        value={patientForm.notes}
                        onChange={(event) =>
                          setPatientForm((prev) => ({ ...prev, notes: event.target.value }))
                        }
                      />
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-outline-secondary" onClick={closeCreatePatientModal}>
                    {t.cancel}
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={patientCreating}
                    onClick={onCreatePatient}
                  >
                    {patientCreating ? `${t.createPatient}...` : t.createPatient}
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show eta-create-patient-backdrop" />
        </>
      )}
    </div>
  )
}

export default ScanPage
