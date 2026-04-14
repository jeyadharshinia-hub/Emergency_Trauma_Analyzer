function ConfidenceDonut({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value || 0)))
  return (
    <div className="d-flex flex-column align-items-center">
      <div
        className="eta-donut"
        style={{
          background: `conic-gradient(var(--eta-primary) ${pct}%, #d8e7fb 0)`,
        }}
      >
        <div className="eta-donut-inner">
          <div>{pct}%</div>
          <small className="eta-subtle fw-semibold">Confidence</small>
        </div>
      </div>
    </div>
  )
}

export default ConfidenceDonut
