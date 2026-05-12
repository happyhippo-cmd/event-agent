/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/app/**/*.{js,jsx}',
    './src/components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#ffffff',
        surface: '#f5f5f7',
        border: 'rgba(0,0,0,0.08)',
        text: '#111111',
        muted: '#888888',
        accent: '#00A8E8',
        'accent-dark': '#0088bd',
        'accent-soft': 'rgba(0,168,232,0.1)',
        'accent-border': 'rgba(0,168,232,0.24)',
        'accent-shadow': 'rgba(0,168,232,0.34)',
        heart: '#EC3535',
        'heart-shadow': 'rgba(236,53,53,0.24)',
      },
      fontFamily: {
        pretendard: ['Pretendard', 'sans-serif'],
        serif: ['"DM Serif Display"', 'serif'],
      },
    },
  },
  plugins: [],
};
