/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#13a4ec",
          50: "#f0f9ff",
          100: "#e0f2fe",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
        },
        "primary-dark": "#0e8bc7",
        "primary-hover": "#1e3a8a",
        "primary-login": "#1E40AF",
        "primary-login-hover": "#1e3a8a",
        "background-main": "#F3F4F6",
        "background-login": "#F9FAFB",
        "sidebar-bg": "#FFFFFF",
        "slate-850": "#1f2937",
        "background-light": "#f6f7f8",
        "background-dark": "#101c22",
        "card-dark": "#192b33",
        "card-hover-dark": "#233c48",
      },
      fontFamily: {
        display: ["Inter", "sans-serif"],
        body: ["Noto Sans", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
      boxShadow: {
        soft: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
      },
    },
  },
  plugins: [],
};
