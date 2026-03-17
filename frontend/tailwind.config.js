/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: '#F4F3F0',
        'cream-dark': '#E8E6E1',
        purple: {
          DEFAULT: '#6C5CE7',
          light: '#A29BFE',
          dark: '#5A4BD1',
          glow: 'rgba(108, 92, 231, 0.15)',
        },
        accent: {
          red: '#E74C4C',
          orange: '#DD8800',
          green: '#38A169',
          gray: '#A0A0A0',
        },
      },
      fontFamily: {
        sans: ['"Nunito Sans"', 'system-ui', 'sans-serif'],
        mono: ['"DM Mono"', 'ui-monospace', 'monospace'],
      },
      maxWidth: {
        dashboard: '860px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)',
        'card-selected': '0 0 0 2px rgba(108, 92, 231, 0.4), 0 4px 12px rgba(108,92,231,0.12)',
      },
      animation: {
        'slide-in': 'slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in': 'fadeIn 0.2s ease-out',
        'lift': 'lift 0.15s ease-out forwards',
      },
      keyframes: {
        slideIn: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        lift: {
          to: { transform: 'translateY(-2px)' },
        },
      },
    },
  },
  plugins: [],
}
