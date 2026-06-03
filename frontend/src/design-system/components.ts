/**
 * GFI v7.0 — Component Style Overrides for Shadcn/UI.
 *
 * These override Shadcn defaults to match the Luxury Minimal aesthetic.
 * Every component follows P1-P7 principles.
 */

import { colors, radii, shadows, spacing, transitions, fonts, fontSizes } from "./tokens";

// ── Button Variants ─────────────────────────────────────────────────────────
export const buttonStyles = {
  primary: {
    bg: colors.primary,
    text: "#FFFFFF",
    border: "none",
    radius: radii.md,
    padding: "10px 20px",
    fontSize: fontSizes.button,
    fontWeight: 600,
    minSize: "44px",
    hover: { bg: "#5B4BD5", shadow: shadows.cardHover },
    focus: { outline: `2px solid ${colors.primaryHover}`, outlineOffset: "2px" },
    disabled: { bg: colors.border, text: colors.textDisabled, cursor: "not-allowed" },
    loading: { text: "En cours..." },
  },
  secondary: {
    bg: "transparent",
    text: colors.primary,
    border: `1px solid ${colors.primary}`,
    hover: { bg: colors.primaryBg },
  },
  ghost: {
    bg: "transparent",
    text: colors.textSecondary,
    border: "none",
    hover: { bg: "#F0F0F0" },
  },
  danger: {
    bg: colors.error,
    text: "#FFFFFF",
    hover: { bg: "#E55A5A" },
  },
  success: {
    bg: colors.success,
    text: "#FFFFFF",
    hover: { bg: "#00A884" },
  },
} as const;

// ── Badge Variants ──────────────────────────────────────────────────────────
export const badgeStyles = {
  success: { bg: colors.successBg, text: colors.success, icon: "✓" },
  warning: { bg: colors.warningBg, text: "#E17055", icon: "⚠" },
  error:   { bg: colors.errorBg, text: colors.errorText, icon: "✗" },
  info:    { bg: colors.infoBg, text: colors.info, icon: "i" },
  neutral: { bg: colors.border, text: colors.textSecondary, icon: "" },
  // Per-RF badges
  rf1: { bg: "rgba(9, 132, 227, 0.15)", text: colors.rf1, icon: "RF1" },
  rf2: { bg: "rgba(108, 92, 231, 0.15)", text: colors.rf2, icon: "RF2" },
  rf3: { bg: "rgba(225, 112, 85, 0.15)", text: colors.rf3, icon: "RF3" },
  rf4: { bg: "rgba(99, 110, 114, 0.15)", text: colors.rf4, icon: "RF4" },
} as const;

// ── Card Styles ─────────────────────────────────────────────────────────────
export const cardStyles = {
  default: {
    bg: colors.card,
    border: `1px solid #E0E0E0`,
    radius: radii.lg,
    padding: spacing.cardPadding,
    shadow: shadows.card,
    hover: { shadow: shadows.cardHover },
  },
  clickable: {
    cursor: "pointer",
    hoverBorder: colors.primary,
    transition: transitions.normal,
  },
  kpi: {
    padding: "20px 24px",
    minHeight: "120px",
  },
} as const;

// ── Input Styles ────────────────────────────────────────────────────────────
export const inputStyles = {
  default: {
    bg: colors.card,
    border: `1px solid ${colors.border}`,
    radius: radii.md,
    padding: "12px 16px",
    fontSize: fontSizes.body,
    focus: { border: colors.primary, shadow: `0 0 0 3px ${colors.primaryBg}` },
    error: { border: colors.error },
    disabled: { bg: "#F5F5F5" },
  },
  label: {
    fontSize: fontSizes.label,
    fontWeight: 500,
    color: colors.textSecondary,
    marginBottom: "6px",
    position: "above", // NEVER beside
  },
} as const;

// ── Modal Styles ────────────────────────────────────────────────────────────
export const modalStyles = {
  overlay: { bg: "rgba(0,0,0,0.3)", backdropFilter: "blur(4px)" },
  container: {
    bg: colors.card,
    radius: radii.xl,
    maxWidth: "600px",
    padding: spacing.modalPadding,
    animation: "scale(0.95) → scale(1) 200ms ease-out",
  },
  close: ["X button", "overlay click", "Escape key"],
} as const;

// ── Toast Styles ────────────────────────────────────────────────────────────
export const toastStyles = {
  position: "top-right",
  stackGap: "8px",
  bg: colors.card,
  leftBorder: "4px",
  shadow: shadows.toast,
  autoDismiss: 5000, // ms — except critical = persistent
} as const;

// ── Alert Level Colors (from verification system) ───────────────────────────
export const alertLevelStyles = {
  INFO:      { bg: colors.infoBg, border: colors.info, icon: "ℹ" },
  ATTENTION: { bg: colors.warningBg, border: "#FDCB6E", icon: "⚡" },
  ALERTE:    { bg: "rgba(225, 112, 85, 0.15)", border: "#E17055", icon: "⚠" },
  CRITIQUE:  { bg: colors.errorBg, border: colors.error, icon: "🔴" },
  BLOQUANT:  { bg: "#2D3436", border: "#000000", icon: "⛔", textColor: "#FFFFFF" },
} as const;
