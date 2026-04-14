import { useNavigate } from 'react-router-dom'
import FeatureCard from '../components/FeatureCard'
import { AlertIcon, BoneIcon, BrainIcon, CtIcon } from '../components/FeatureIcons'
import { useLang } from '../contexts/LangContext'

function DashboardPage() {
  const { t } = useLang()
  const navigate = useNavigate()

  const cards = [
    { title: 'MRI Analysis', subtitle: 'Brain and soft tissue trauma', icon: <BrainIcon /> },
    { title: 'CT Screening', subtitle: 'Emergency head/chest scan support', icon: <CtIcon /> },
    { title: 'X-ray Detection', subtitle: 'Fracture and chest findings', icon: <BoneIcon /> },
    { title: 'Severity Triage', subtitle: 'Critical / Moderate / Mild', icon: <AlertIcon /> },
  ]

  return (
    <div className="eta-fade">
      <div className="eta-hero text-center mb-4">
        <div className="eta-chip-row mb-3">
          <span className="eta-chip">Golden Hour Ready</span>
          <span className="eta-chip">Bilingual Draft</span>
          <span className="eta-chip">Doctor-in-the-loop</span>
        </div>
        <h2 className="mb-2">{t.dashboardTitle}</h2>
        <p className="eta-subtle mb-3">{t.dashboardSubtitle}</p>
        <div className="d-flex justify-content-center gap-2 flex-wrap">
          <button className="btn btn-primary px-4" onClick={() => navigate('/scan')}>
            {t.uploadTitle}
          </button>
          <button className="btn btn-outline-primary px-4" onClick={() => navigate('/scan')}>
            Start New Analysis
          </button>
        </div>
      </div>
      <div className="row g-3">
        {cards.map((card, index) => (
          <FeatureCard key={card.title} {...card} index={index} />
        ))}
      </div>
    </div>
  )
}

export default DashboardPage
