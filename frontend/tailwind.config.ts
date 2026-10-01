import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5",
          dark: "#4338CA",
        },
        ink: "#0F172A",
        ink2: "#475569",
        canvas: "#F8FAFC",
        surface: "#FFFFFF",
        line: "#E2E8F0",
        success: "#16A34A",
        warning: "#D97706",
        danger: "#DC2626",
        info: "#2563EB",
        muted: "#64748B",
      },
      fontFamily: {
        sans: ["-apple-system", "Segoe UI", "Inter", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
