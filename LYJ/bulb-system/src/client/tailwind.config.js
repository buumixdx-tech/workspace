/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        success: '#10B981',
        warning: '#F59E0B',
        danger: '#EF4444',
        border: '#E5E7EB',
        'text-primary': '#111827',
        'text-secondary': '#6B7280',
      },
      borderRadius: {
        'card': '12px',
        'btn': '8px',
        'input': '8px',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0,0,0,0.1)',
      }
    },
  },
  plugins: [],
}
