export const tokens = {
  // Spacing scale (4px base)
  space: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    '2xl': 32,
    '3xl': 48,
  },
  // Border radius
  radius: {
    xs: 6,
    sm: 10,
    md: 14,
    lg: 18,
    xl: 24,
    '2xl': 32,
    full: 9999,
  },
  // Blur values
  blur: {
    sm: '14px',
    md: '20px',
    lg: '26px',
    xl: '32px',
  },
  // Shadow levels
  shadow: {
    sm: '0 8px 20px rgba(0,0,0,0.18)',
    md: '0 16px 36px rgba(0,0,0,0.28)',
    lg: '0 24px 56px rgba(0,0,0,0.36)',
    xl: '0 32px 72px rgba(0,0,0,0.42)',
    // Inset highlights for depth
    insetLight: 'inset 0 1px 0 rgba(255,255,255,0.16)',
    insetStrong: 'inset 0 1px 0 rgba(255,255,255,0.24)',
  },
  // Typography scale
  typography: {
    // Font sizes
    size: {
      xs: '11px',
      sm: '12px',
      base: '14px',
      md: '16px',
      lg: '18px',
      xl: '22px',
      '2xl': '28px',
      '3xl': '36px',
    },
    // Line heights
    leading: {
      tight: 1.2,
      snug: 1.35,
      normal: 1.5,
      relaxed: 1.65,
    },
    // Font weights
    weight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    // Letter spacing
    tracking: {
      tight: '-0.02em',
      normal: '0',
      wide: '0.02em',
      wider: '0.04em',
    },
  },
  // Borders
  border: {
    glass: '1px solid rgba(255,255,255,0.12)',
    glassStrong: '1px solid rgba(255,255,255,0.18)',
    glassSubtle: '1px solid rgba(255,255,255,0.08)',
    accent: '1px solid rgba(106,165,255,0.4)',
  },
  // Glass morphism variants
  glass: {
    bg: 'rgba(255,255,255,0.08)',
    bgSubtle: 'rgba(255,255,255,0.05)',
    bgStrong: 'rgba(255,255,255,0.14)',
    bgHover: 'rgba(255,255,255,0.18)',
    highlight: 'rgba(255,255,255,0.22)',
    // Glows for premium feel
    glow: '0 0 40px rgba(106,165,255,0.18)',
    glowStrong: '0 0 60px rgba(106,165,255,0.28)',
    glowSubtle: '0 0 24px rgba(106,165,255,0.12)',
    // Gradient overlays
    gradient: 'linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.02))',
    gradientStrong: 'linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.04))',
  },
  // Transitions
  transition: {
    fast: '0.12s ease',
    normal: '0.2s ease',
    slow: '0.3s ease',
    // Specific
    hover: '0.18s ease',
    focus: '0.2s ease',
    transform: '0.24s cubic-bezier(0.34, 1.56, 0.64, 1)',
  },
  // Colors
  color: {
    text: '#e8ecf5',
    textMuted: 'rgba(232,236,245,0.72)',
    textSubtle: 'rgba(232,236,245,0.55)',
    bg: '#0b1020',
    bgElevated: '#101828',
    accent: '#6aa5ff',
    accentLight: '#8ec5ff',
    accentSoft: 'rgba(106,165,255,0.12)',
    accentMedium: 'rgba(106,165,255,0.22)',
    success: '#5BE1A5',
    successSoft: 'rgba(91,225,165,0.18)',
    warning: '#F6C16B',
    warningSoft: 'rgba(246,193,107,0.18)',
    danger: '#F07373',
    dangerSoft: 'rgba(240,115,115,0.18)',
    glassLight: 'rgba(255,255,255,0.08)',
    glassStrong: 'rgba(255,255,255,0.14)',
  },
} as const
