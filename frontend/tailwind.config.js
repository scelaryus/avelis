/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Burgundy-driven accent system
        iris: "#7f1d1d",
        lavender: "#b91c1c",
        "iris-bg": "#fef2f2",
        ocean: "#7f1d1d",
        mint: "#9f1239",
        honey: "#d97706",        // amber (keep)
        coral: "#dc2626",        // red (keep)
        teal: {
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },
        cyan: {
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },
        emerald: {
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },
        green: {
          50: "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },
        // Neutrals mapped to slate
        snow: "#f8fafc",         // slate-50
        midnight: "#0f172a",     // slate-900
        charcoal: "#0f172a",     // slate-900
        storm: "#64748b",        // slate-500
        silver: "#94a3b8",       // slate-400
        mist: "#e2e8f0",         // slate-200
        // RF colors
        rf1: "#9f1239", rf2: "#d97706", rf3: "#dc2626", rf4: "#64748b",
      },
      fontFamily: {
        sans: ["'Inter'", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      borderRadius: { card: "12px", button: "8px", input: "8px" },
      boxShadow: { card: "0 1px 3px rgba(0,0,0,0.04)", "card-hover": "0 4px 16px rgba(0,0,0,0.08)" },
    },
  },
  plugins: [],
}
