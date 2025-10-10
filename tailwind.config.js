import defaultTheme from 'tailwindcss/defaultTheme';

export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    './backend/apps/admin_ui/templates/**/*.html',
    './backend/apps/admin_ui/static/js/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: 'rgb(var(--bg-base) / <alpha-value>)',
          elev1: 'rgb(var(--bg-elev-1) / <alpha-value>)',
          elev2: 'rgb(var(--bg-elev-2) / <alpha-value>)',
          elev3: 'rgb(var(--bg-elev-3) / <alpha-value>)',
        },
        fg: {
          primary: 'rgb(var(--fg-primary) / <alpha-value>)',
          secondary: 'rgb(var(--fg-secondary) / var(--fg-secondary-alpha))',
          muted: 'rgb(var(--fg-secondary) / var(--fg-muted-alpha))',
        },
        accent: 'rgb(var(--accent) / <alpha-value>)',
        'accent-soft': 'rgb(var(--accent-soft) / <alpha-value>)',
        'accent-strong': 'rgb(var(--accent-strong) / <alpha-value>)',
        success: 'rgb(var(--success) / <alpha-value>)',
        warning: 'rgb(var(--warning) / <alpha-value>)',
        danger: 'rgb(var(--danger) / <alpha-value>)',
        info: 'rgb(var(--info) / <alpha-value>)',
        stroke: 'rgb(var(--stroke) / <alpha-value>)',
        border: 'rgb(var(--border) / var(--border-alpha))',
      },
      fontFamily: {
        sans: ['"SF Pro Display"', 'Inter', 'var(--font-sans)', ...defaultTheme.fontFamily.sans],
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      boxShadow: {
        glass: '0 18px 40px 0 rgb(var(--shadow-soft))',
        'glass-strong': '0 28px 70px 0 rgb(var(--shadow-strong))',
        'focus-ring': '0 0 0 4px rgb(var(--shadow-focus))',
      },
      backdropBlur: {
        glass: 'var(--blur)',
      },
      transitionTimingFunction: {
        snap: 'var(--transition-snap)',
      },
      keyframes: {
        'glass-in': {
          '0%': { opacity: '0', transform: 'translateY(8px) scale(0.98)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-60%)' },
          '100%': { transform: 'translateX(120%)' },
        },
      },
      animation: {
        'glass-in': 'glass-in 220ms var(--transition-snap) both',
        shimmer: 'shimmer 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')],
};
