function IconBase({ children }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {children}
    </svg>
  )
}

export function BrainIcon() {
  return (
    <IconBase>
      <path
        d="M8 5a3 3 0 1 0-2.5 4.66A3.5 3.5 0 0 0 9 13v5m0-13a3 3 0 1 1 3 3h-1m-2-3v8m5-8a3 3 0 1 1 3 3m-3 0v5a3 3 0 0 1-3 3"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </IconBase>
  )
}

export function CtIcon() {
  return (
    <IconBase>
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.7" />
      <path d="M12 6v2m0 8v2m6-6h-2M8 12H6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </IconBase>
  )
}

export function BoneIcon() {
  return (
    <IconBase>
      <path
        d="M6.5 8.5a2 2 0 1 1-2-2l2.5 2.5m0 0 8 8M17.5 15.5a2 2 0 1 1 2 2L17 15m0 0-8-8"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="6.5" cy="6.5" r="1.2" fill="currentColor" />
      <circle cx="17.5" cy="17.5" r="1.2" fill="currentColor" />
    </IconBase>
  )
}

export function AlertIcon() {
  return (
    <IconBase>
      <path
        d="M12 4 3.8 18.2a1 1 0 0 0 .87 1.5h14.66a1 1 0 0 0 .87-1.5L12 4Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M12 9v4m0 3h.01" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </IconBase>
  )
}

