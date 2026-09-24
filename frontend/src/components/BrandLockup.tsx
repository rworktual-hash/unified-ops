type Props = {
  variant?: 'sidebar' | 'login'
  collapsed?: boolean
}

export function BrandLockup({ variant = 'sidebar', collapsed = false }: Props) {
  if (collapsed && variant === 'sidebar') {
    return (
      <div className={`brand-lockup brand-lockup--${variant} brand-lockup--collapsed`}>
        <img src="/favicon.png" alt="Worktual" className="brand-mark" />
      </div>
    )
  }
  return (
    <div className={`brand-lockup brand-lockup--${variant}`}>
      <img src="/worktual-logo.png" alt="Worktual" className="brand-logo-img" />
      <span className="brand-sub">Observability</span>
    </div>
  )
}
