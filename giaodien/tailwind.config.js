export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#0ea5e9', light: '#38bdf8', dark: '#0284c7' },
        accent: { DEFAULT: '#f59e0b', light: '#fbbf24' },
        surface: { DEFAULT: '#1e293b', light: '#334155', dark: '#0f172a' },
      }
    }
  },
  plugins: []
}
