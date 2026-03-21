/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#0a0f1a',
          900: '#0d1422',
          800: '#111827',
        },
        ice: {
          400: '#4a9eff',
          300: '#7bb8ff',
          200: '#acd4ff',
        },
        cool: {
          50: '#e8edf5',
          100: '#d0dae8',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
