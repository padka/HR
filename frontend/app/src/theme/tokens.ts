export const tokens = {
  radius: {
    xs: 6,
    sm: 10,
    md: 14,
    lg: 18,
    xl: 24
  },
  blur: {
    sm: '12px',
    md: '18px',
    lg: '24px'
  },
  shadow: {
    sm: '0 10px 24px rgba(0,0,0,0.18)',
    md: '0 18px 40px rgba(0,0,0,0.24)',
    lg: '0 28px 70px rgba(0,0,0,0.32)'
  },
  border: {
    glass: '1px solid rgba(255,255,255,0.12)'
  },
  color: {
    text: '#e8ecf5',
    textMuted: 'rgba(232,236,245,0.72)',
    bg: '#0b1020',
    accent: '#6aa5ff',
    accentSoft: 'rgba(106,165,255,0.12)',
    success: '#5BE1A5',
    warning: '#F6C16B',
    danger: '#F07373',
    glassLight: 'rgba(255,255,255,0.08)',
    glassStrong: 'rgba(255,255,255,0.14)'
  }
} as const
