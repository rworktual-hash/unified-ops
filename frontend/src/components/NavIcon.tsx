type Props = {
  id: string
}

export function NavIcon({ id }: Props) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  switch (id) {
    case 'servers':
      return (
        <svg {...common}>
          <rect x="3" y="3.5" width="18" height="6" rx="1.5" />
          <rect x="3" y="14.5" width="18" height="6" rx="1.5" />
          <path d="M7 6.5h.01M7 17.5h.01" />
        </svg>
      )
    case 'hosts':
      return (
        <svg {...common}>
          <rect x="3" y="4" width="7" height="7" rx="1.4" />
          <rect x="14" y="4" width="7" height="7" rx="1.4" />
          <rect x="3" y="14" width="7" height="7" rx="1.4" />
          <rect x="14" y="14" width="7" height="7" rx="1.4" />
        </svg>
      )
    case 'infrastructure':
      return (
        <svg {...common}>
          <circle cx="12" cy="5" r="2.2" />
          <circle cx="5.5" cy="18" r="2.2" />
          <circle cx="18.5" cy="18" r="2.2" />
          <path d="M12 7.2v3.2M10.2 12.2 6.6 16M13.8 12.2 17.4 16M12 10.4h.01" />
        </svg>
      )
    case 'backupvault':
      return (
        <svg {...common}>
          <path d="M4 8.5 12 4l8 4.5v9L12 22l-8-4.5v-9z" />
          <path d="M12 13v9M4 8.5l8 4.5 8-4.5" />
        </svg>
      )
    case 'email':
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="m4 7 8 6 8-6" />
        </svg>
      )
    case 'voicemg':
      return (
        <svg {...common}>
          <path d="M4.5 13a7.5 7.5 0 0 1 15 0" />
          <rect x="3" y="12" width="4" height="6.5" rx="1.3" />
          <rect x="17" y="12" width="4" height="6.5" rx="1.3" />
          <path d="M12 19.2v1.6" />
        </svg>
      )
    case 'chat':
      return (
        <svg {...common}>
          <path d="M5 16.2 3.6 20V7.6A3.6 3.6 0 0 1 7.2 4h9.6A3.6 3.6 0 0 1 20.4 7.6v5.2A3.6 3.6 0 0 1 16.8 16.4H8z" />
        </svg>
      )
    case 'alerts':
      return (
        <svg {...common}>
          <path d="M6 16.5h12l-1.2-2.1V11a4.8 4.8 0 0 0-9.6 0v3.4L6 16.5z" />
          <path d="M10 16.5a2 2 0 0 0 4 0" />
        </svg>
      )
    case 'approvals':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="m8.5 12.2 2.3 2.3 4.7-5" />
        </svg>
      )
    case 'activity':
      return (
        <svg {...common}>
          <path d="M8 6h11M8 12h11M8 18h11" />
          <path d="M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="7" />
        </svg>
      )
  }
}
