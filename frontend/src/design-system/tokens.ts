/**
 * GFI v7.0 — Design System Tokens: 'Luxury Minimal' aesthetic.
 *
 * 7 Principles: CALME, CLAIR, HIÉRARCHIE, FEEDBACK, ACCESSIBILITÉ, COHÉRENCE, RAPIDITÉ.
 * All 30 screens use these tokens exclusively.
 */

// ── Colors ──────────────────────────────────────────────────────────────────
export const colors = {
  // Backgrounds
  background: "#FAFAFA",    // Snow — page bg (NEVER pure white)
  card: "#FFFFFF",           // White — cards and modals ONLY
  darkBg: "#1E272E",        // Midnight — dark mode page
  darkCard: "#2C3A47",      // Slate — dark mode card

  // Text
  textPrimary: "#2D3436",   // Charcoal (NEVER pure black)
  textSecondary: "#636E72", // Storm
  textDisabled: "#B2BEC3",  // Silver

  // Borders
  border: "#DFE6E9",        // Mist
  borderHover: "#6C5CE7",   // Iris on hover

  // Semantic — Actions
  primary: "#6C5CE7",       // Iris — primary buttons, active indicators
  primaryHover: "#A29BFE",  // Lavender — hover states
  primaryBg: "#F0EFFE",     // Light iris — active sidebar item bg

  // Semantic — Status
  info: "#0984E3",          // Ocean
  infoBg: "rgba(116, 185, 255, 0.20)",
  success: "#00B894",       // Mint — PASS, VALIDÉ, online
  successBg: "rgba(85, 239, 196, 0.20)",
  warning: "#FDCB6E",       // Honey — FLAG, PENDING
  warningBg: "rgba(255, 234, 167, 0.30)",
  error: "#FF6B6B",         // Coral — FAIL, BLOCAGE, offline
  errorBg: "rgba(253, 121, 168, 0.20)",
  errorText: "#D63031",

  // RF Classification
  rf1: "#0984E3",           // Blue — declared
  rf2: "#6C5CE7",           // Violet — undeclared
  rf3: "#E17055",           // Orange — fictitious declared
  rf4: "#636E72",           // Gray — fictitious undeclared
} as const;

// ── Typography ──────────────────────────────────────────────────────────────
export const fonts = {
  primary: "'DM Sans', sans-serif",
  mono: "'JetBrains Mono', monospace",
} as const;

export const fontSizes = {
  h1: "32px",       // Bold
  h2: "24px",       // SemiBold
  h3: "18px",       // SemiBold
  body: "16px",     // Regular
  small: "14px",    // Regular
  caption: "12px",  // Minimum — no exceptions
  label: "14px",    // Medium
  button: "14px",   // SemiBold
  badge: "11px",    // SemiBold uppercase
  kpiNumber: "40px", // Bold
} as const;

// ── Spacing ─────────────────────────────────────────────────────────────────
export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "32px",
  xxl: "48px",
  contentPadding: "32px",
  cardPadding: "24px",
  modalPadding: "32px",
  sidebarWidth: "260px",
  headerHeight: "64px",
  maxContentWidth: "1400px",
} as const;

// ── Radii ───────────────────────────────────────────────────────────────────
export const radii = {
  sm: "6px",    // badges
  md: "8px",    // buttons, inputs
  lg: "12px",   // cards
  xl: "16px",   // modals
  full: "9999px", // pills
} as const;

// ── Shadows ─────────────────────────────────────────────────────────────────
export const shadows = {
  card: "0 1px 3px rgba(0,0,0,0.04)",
  cardHover: "0 4px 16px rgba(0,0,0,0.08)",
  modal: "0 16px 48px rgba(0,0,0,0.12)",
  dropdown: "0 4px 12px rgba(0,0,0,0.08)",
  toast: "0 4px 24px rgba(0,0,0,0.10)",
} as const;

// ── Transitions (P7: < 100ms response, 200-300ms animations) ────────────────
export const transitions = {
  fast: "150ms ease-out",
  normal: "200ms ease-out",
  slow: "300ms ease-out",
} as const;

// ── Z-Index Layers ──────────────────────────────────────────────────────────
export const zIndex = {
  sidebar: 40,
  header: 50,
  dropdown: 60,
  modal: 70,
  toast: 80,
  tooltip: 90,
} as const;

// ── Breakpoints ─────────────────────────────────────────────────────────────
export const breakpoints = {
  mobile: "375px",
  tablet: "768px",
  desktop: "1024px",
  wide: "1440px",
} as const;
