/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['"DM Sans"',        'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
        display: ['"Syne"',           'sans-serif'],
      },
      colors: {
        ink: {
          DEFAULT: '#0D0F12',
          50:  '#F4F5F6',
          100: '#E8EAEC',
          200: '#C8CDD3',
          300: '#9AA3AE',
          400: '#6B7785',
          500: '#4A5568',
          600: '#2D3748',
          700: '#1A202C',
          800: '#131720',
          900: '#0D0F12',
        },
        signal: { DEFAULT: '#E84545', soft: '#FDEAEA', dark: '#B52F2F' },
        amber:  { DEFAULT: '#F59E0B', soft: '#FEF3C7' },
        jade:   { DEFAULT: '#10B981', soft: '#D1FAE5' },
        sky:    { DEFAULT: '#3B82F6', soft: '#DBEAFE' },
      },
      animation: {
        'fade-in':    'fadeIn 0.3s ease-out',
        'slide-up':   'slideUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: 0 },                            to: { opacity: 1 } },
        slideUp:   { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.6 } },
      },
    },
  },
  plugins: [],
}
