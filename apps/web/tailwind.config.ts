import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1a2332",
          50: "#f0f2f5",
          100: "#d9dde4",
          200: "#b3bbc9",
          300: "#8d99ae",
          400: "#667793",
          500: "#4a5b78",
          600: "#33435e",
          700: "#1a2332",
          800: "#0f1722",
          900: "#070b11",
        },
        accent: {
          DEFAULT: "#2563eb",
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af",
          800: "#1e3a8a",
          900: "#172554",
        },
        success: {
          DEFAULT: "#059669",
          50: "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          500: "#059669",
          700: "#047857",
          800: "#065f46",
        },
        warning: {
          DEFAULT: "#d97706",
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          500: "#d97706",
          700: "#b45309",
          800: "#92400e",
        },
        danger: {
          DEFAULT: "#dc2626",
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          500: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
        },
        surface: {
          DEFAULT: "#f8fafc",
          card: "#ffffff",
          border: "#e2e8f0",
        },
        ink: {
          DEFAULT: "#0f172a",
          secondary: "#475569",
          tertiary: "#94a3b8",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "PingFang SC",
          "Microsoft YaHei",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
        "legal": ["0.75rem", { lineHeight: "1.125rem" }],
        "body": ["0.875rem", { lineHeight: "1.5rem" }],
        "body-lg": ["0.9375rem", { lineHeight: "1.625rem" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(15 23 42 / 0.05), 0 0 0 1px rgb(15 23 42 / 0.04)",
        elevated: "0 4px 12px 0 rgb(15 23 42 / 0.08), 0 0 0 1px rgb(15 23 42 / 0.04)",
        floating: "0 10px 24px rgba(15,23,42,0.12)",
        sidebar: "inset -1px 0 0 0 rgb(255 255 255 / 0.06)",
      },
      animation: {
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        "fade-in": "fade-in 0.2s ease-out",
        "slide-up": "slide-up 0.25s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.3" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
