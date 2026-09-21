type Props = {
  variant?: 'sidebar' | 'login'
}

export function BrandLockup({ variant = 'sidebar' }: Props) {
  return (
    <div className={`brand-lockup brand-lockup--${variant}`}>
      <img src="/worktual-mark.svg" alt="" className="brand-mark-img" />
      <div className="brand-words">
        <span className="brand-name">Worktual</span>
        <span className="brand-sub">Observability</span>
      </div>
    </div>
  )
}
