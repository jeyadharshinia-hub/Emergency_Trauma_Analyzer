function FeatureCard({ title, subtitle, icon, index = 0 }) {
  return (
    <div className="col-md-6 col-lg-3">
      <div
        className="card eta-card eta-feature h-100 eta-fade"
        style={{ animationDelay: `${index * 80}ms` }}
      >
        <div className="card-body text-center p-4">
          <div className="eta-icon-circle mx-auto mb-3">{icon}</div>
          <h6 className="mb-2">{title}</h6>
          <small className="eta-subtle">{subtitle}</small>
        </div>
      </div>
    </div>
  )
}

export default FeatureCard
