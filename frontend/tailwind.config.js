/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'eurocar-blue': '#1B3A5C',
        'eurocar-light': '#5DADE2',
        'eurocar-green': '#2ECC71',
      }
    },
  },
  plugins: [],
}
