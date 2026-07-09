import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A",
        sand: "#F8FAFC",
        moss: "#10B981",
        rust: "#EF4444",
        mist: "#94A3B8",
      },
      boxShadow: {
        floating: "0 10px 24px rgba(15,23,42,0.12)",
      },
    },
  },
  plugins: [],
};
export default config;
