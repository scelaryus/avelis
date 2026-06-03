export function formatDA(v: number | string): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (isNaN(n)) return '0 DA';
  return new Intl.NumberFormat('fr-DZ', { maximumFractionDigits: 0 }).format(n) + ' DA';
}
export const fmtDA = formatDA;

export function formatPct(v: number | string): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return n.toFixed(1) + '%';
}
export const fmtPct = formatPct;

export function formatDate(d: string): string {
  return new Date(d).toLocaleDateString('fr-DZ', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const RF_NAMES: Record<string, string> = {
  RF1: 'Reel Declare',
  RF2: 'Reel Non Declare',
  RF3: 'Fictif Declare',
  RF4: 'Fictif Non Declare',
};

export function rfName(code: string): string {
  return RF_NAMES[code] || code;
}

export function rfLabel(code: string): string {
  return `${code} — ${RF_NAMES[code] || ''}`;
}
