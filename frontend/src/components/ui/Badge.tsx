import { clsx } from 'clsx';

const variants = {
  success: 'bg-green-100 text-green-800',
  warning: 'bg-amber-100 text-amber-800',
  error: 'bg-red-100 text-red-800',
  info: 'bg-rose-100 text-rose-800',
  neutral: 'bg-slate-100 text-slate-700',
  rf1: 'bg-emerald-100 text-emerald-800',
  rf2: 'bg-amber-100 text-amber-800',
  rf3: 'bg-red-100 text-red-800',
};

interface BadgeProps { variant: keyof typeof variants; children: React.ReactNode; }

export function Badge({ variant, children }: BadgeProps) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', variants[variant])}>
      {children}
    </span>
  );
}
