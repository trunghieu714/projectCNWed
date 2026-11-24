/** @type {import('tailwindcss').Config} */
// Mã màu dùng chung cho các trang mới được lưu tập trung trong src/theme/colors.json (Slide 36)
const colors = require("./src/theme/colors.json");

module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        ui: colors.ui,
      },
      boxShadow: {
        card: "0 10px 15px -3px rgba(0, 0, 0, 0.3)",
        pop: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
      },
      keyframes: {
        "slide-up": { "0%": { transform: "translateY(100%)" }, "100%": { transform: "translateY(0)" } },
        "fade-in": { "0%": { opacity: 0 }, "100%": { opacity: 1 } },
        "like-pop": { "0%,100%": { transform: "scale(1)" }, "50%": { transform: "scale(1.35)" } },
      },
      animation: {
        "slide-up": "slide-up 0.35s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
        "like-pop": "like-pop 0.3s ease-out",
      },
    }
  },
  plugins: [],
}
