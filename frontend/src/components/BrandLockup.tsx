type Props = {
  variant?: 'sidebar' | 'login'
}

export function BrandLockup({ variant = 'sidebar' }: Props) {
  return (
    <div className={`brand-lockup brand-lockup--${variant}`}>
      <img src="/worktual-logo.png" alt="Worktual" className="brand-logo-img" />
      <span className="brand-sub">Observability</span>
    </div>
  )
}
