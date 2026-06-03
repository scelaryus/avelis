import { fmtDA } from '../../lib/format';

interface KpiCardProps {
  title: string;
  value: string | number;
  format?: 'da' | 'number' | 'pct';
  trend?: number;
  color?: string;
}

export function KpiCard({ title, value, format = 'number', trend, color = 'iris' }: KpiCardProps) {
  const formatted = format === 'da' ? fmtDA(value) : format === 'pct' ? `${value}%` : value;
  const trendColor = trend && trend > 0 ? 'text-mint' : trend && trend < 0 ? 'text-coral' : 'text-storm';

  return (
    <div className="bg-white rounded-card border border-mist p-6 shadow-card hover:shadow-card-hover transition-shadow duration-200">
      <p className="text-sm text-storm font-medium mb-2">{title}</p>
      <p className="text-kpi font-bold text-charcoal">{formatted}</p>
      {trend !== undefined && (
        <p className={`text-sm mt-2 ${trendColor}`}>
          {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}% vs mois dernier
        </p>
      )}
    </div>
  );
}
