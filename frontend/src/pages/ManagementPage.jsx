import { useLang } from '../contexts/LangContext'
import PatientsPage from './PatientsPage'

function ManagementPage() {
  const { t } = useLang()

  return (
    <div className="eta-fade d-flex flex-column gap-3">
      <div className="card eta-card p-3 p-md-4">
        <h4 className="mb-1">{t.managementTitle}</h4>
        <p className="eta-subtle mb-0">{t.managementSubtitle}</p>
      </div>
      <PatientsPage embedded />
    </div>
  )
}

export default ManagementPage
