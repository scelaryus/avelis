/**
 * GFI v7.0 — Tailwind CSS Preset.
 *
 * Drop-in replacement for Shadcn defaults. Import in tailwind.config.ts:
 *   presets: [require('./src/design-system/tailwind-preset')]
 */

import type { Config } from "tailwindcss";

const preset: Config = {
  content: [],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        snow: "#FAFAFA",
        midnight: "#1E272E",
        slate: "#2C3A47",

        // Text
        charcoal: "#2D3436",
        storm: "#636E72",
        silver: "#B2BEC3",

        // Borders
        mist: "#DFE6E9",

        // Primary
        iris: "#6C5CE7",
        lavender: "#A29BFE",
        "iris-bg": "#F0EFFE",

        // Semantic
        ocean: "#0984E3",
        mint: "#00B894",
        honey: "#FDCB6E",
        coral: "#FF6B6B",

        // RF
        rf1: "#0984E3",
        rf2: "#6C5CE7",
        rf3: "#E17055",
        rf4: "#636E72",
      },
      fontFamily: {
        sans: ["'DM Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      fontSize: {
        "kpi": ["40px", { lineHeight: "1.1", fontWeight: "700" }],
        "h1": ["32px", { lineHeight: "1.2", fontWeight: "700" }],
        "h2": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
        "h3": ["18px", { lineHeight: "1.4", fontWeight: "600" }],
        "body": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
        "small": ["14px", { lineHeight: "1.5", fontWeight: "400" }],
        "caption": ["12px", { lineHeight: "1.4", fontWeight: "400" }],
        "badge": ["11px", { lineHeight: "1", fontWeight: "600", letterSpacing: "0.05em" }],
      },
      borderRadius: {
        "card": "12px",
        "modal": "16px",
        "badge": "6px",
      },
      boxShadow: {
        "card": "0 1px 3px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 16px rgba(0,0,0,0.08)",
        "modal": "0 16px 48px rgba(0,0,0,0.12)",
        "toast": "0 4px 24px rgba(0,0,0,0.10)",
      },
      spacing: {
        "sidebar": "260px",
        "header": "64px",
      },
      maxWidth: {
        "content": "1400px",
        "modal": "600px",
      },
      transitionDuration: {
        "fast": "150ms",
        "normal": "200ms",
        "slow": "300ms",
      },
      animation: {
        "modal-in": "modalIn 200ms ease-out",
        "toast-in": "toastIn 300ms ease-out",
        "fade-in": "fadeIn 200ms ease-out",
      },
      keyframes: {
        modalIn: {
          "0%": { transform: "scale(0.95)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        toastIn: {
          "0%": { transform: "translateX(100%)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default preset;
