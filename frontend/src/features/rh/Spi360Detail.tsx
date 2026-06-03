import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';
import api from '../../lib/api-client';

export function Spi360Detail() {
  const { employeeId } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (employeeId) {
      api.get(`/drh/spi360/employee/${employeeId}`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
    }
  }, [employeeId]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Employe SPI introuvable</p>;

  const { employee, weights, daily_chart, monthly, counter, tasks, deliverables, projection } = data;
  const spi = parseFloat(monthly.avg_spi);

  return (
    <div>
      <Link to="/rh/spi360" className="text-sm text-iris hover:underline">&larr; SPI 360</Link>

      {/* Header */}
      <div className="flex items-center gap-6 mt-4 mb-6">
        <div className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl font-bold ${
          spi >= 90 ? 'bg-mint' : spi >= 70 ? 'bg-honey' : spi >= 50 ? 'bg-coral' : 'bg-[#D63031]'}`}>
          {spi.toFixed(0)}
        </div>
        <div>
          <h1 className="text-[28px] font-bold">{employee.name}</h1>
          <p className="text-sm text-storm">{employee.matricule} -- {employee.position} -- Base: {formatDA(employee.salary_base)}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-sm text-storm">Projection Salaire</p>
          <p className={`text-xl font-bold font-mono ${parseFloat(projection.amount) >= 0 ? 'text-mint' : 'text-coral'}`}>
            {parseFloat(projection.amount) >= 0 ? '+' : ''}{formatDA(projection.amount)}
          </p>
          <Badge variant={monthly.tier === 'BON' || monthly.tier === 'EXCELLENT' ? 'success' : monthly.tier === 'STANDARD' ? 'neutral' : 'error'}>
            {monthly.tier} ({projection.impact})
          </Badge>
        </div>
      </div>

      {/* 30-day chart + Pillar cards */}
      <div className="grid grid-cols-3 gap-6 mb-6">
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">SPI 30 Derniers Jours</h2>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={daily_chart}>
              <defs>
                <linearGradient id="spiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6C5CE7" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6C5CE7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#636E72' }} interval={4} />
              <YAxis domain={[0, 150]} tick={{ fontSize: 10, fill: '#636E72' }} />
              <Tooltip formatter={(v: number) => `${v}/100+`} />
              <ReferenceLine y={90} stroke="#00B894" strokeDasharray="4 4" label={{ value: 'Bonus 90', fontSize: 9, fill: '#00B894' }} />
              <ReferenceLine y={70} stroke="#FDCB6E" strokeDasharray="4 4" label={{ value: 'Standard 70', fontSize: 9, fill: '#E17055' }} />
              <ReferenceLine y={50} stroke="#FF6B6B" strokeDasharray="4 4" label={{ value: 'Malus 50', fontSize: 9, fill: '#FF6B6B' }} />
              <Area type="monotone" dataKey="spi" stroke="#6C5CE7" strokeWidth={2} fill="url(#spiGrad)" dot={{ r: 2, fill: '#6C5CE7' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 4 Pillar gauges */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <h2 className="text-base font-semibold">4 Piliers (poids: {JSON.stringify(weights).replace(/[{}"]/g, '')})</h2>
          {[
            { key: 'p1', label: 'Planification', weight: weights.planification, color: '#0984E3' },
            { key: 'p2', label: 'Qualite', weight: weights.qualite, color: '#6C5CE7' },
            { key: 'p3', label: 'Comportement', weight: weights.comportement, color: '#00B894' },
            { key: 'p4', label: 'Performance', weight: weights.performance, color: '#E17055' },
          ].map(pillar => {
            const latest = daily_chart.length > 0 ? daily_chart[daily_chart.length - 1] : null;
            const val = latest ? parseFloat(latest[pillar.key]) : 0;
            return (
              <div key={pillar.key}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-storm">{pillar.label} ({pillar.weight}%)</span>
                  <span className="font-mono font-bold">{val.toFixed(0)}/100+</span>
                </div>
                <div className="bg-mist rounded-full h-2.5 overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(val, 100)}%`, background: pillar.color }} />
                </div>
              </div>
            );
          })}
          <div className="border-t border-mist pt-3 text-xs">
            <div className="flex justify-between"><span className="text-storm">Compteur bonus</span><span className="text-mint font-bold">+{counter.bonus_total}</span></div>
            <div className="flex justify-between"><span className="text-storm">Compteur malus</span><span className="text-coral font-bold">-{counter.malus_total}</span></div>
            <div className="flex justify-between"><span className="text-storm">Jours inactifs</span><span className={counter.inactive_days > 3 ? 'text-coral font-bold' : 'text-storm'}>{counter.inactive_days}</span></div>
          </div>
        </div>
      </div>

      {/* Tasks + Deliverables */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Taches ce mois ({tasks.length})</h2>
          {tasks.length === 0 ? <p className="text-sm text-storm text-center py-4">Aucune tache</p> : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {tasks.map((t: any) => (
                <div key={t.id} className={`p-3 rounded-lg border ${t.counts ? 'border-mint bg-[rgba(0,184,148,0.04)]' : 'border-mist'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{t.title}</span>
                    <Badge variant={t.status === 'COMPLETEE' ? 'success' : t.status === 'EN_RETARD' ? 'error' : t.status === 'ASSIGNEE' ? 'info' : 'warning'}>
                      {t.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-storm">
                    <span>Due: {t.due}</span>
                    {t.completed && <span>Fait: {t.completed}</span>}
                    <span className={`font-bold ${t.val_algo === 'PASS' ? 'text-mint' : t.val_algo === 'FAIL' ? 'text-coral' : 'text-honey'}`}>
                      Algo: {t.val_algo}
                    </span>
                    <span className={`font-bold ${t.val_manager === 'VALIDE' ? 'text-mint' : t.val_manager === 'REFUSE' ? 'text-coral' : 'text-honey'}`}>
                      Mgr: {t.val_manager}
                    </span>
                    {t.counts && <span className="text-iris font-bold">+{t.points} pts</span>}
                    {!t.has_proof && <span className="text-coral">Sans preuve</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Livrables ce mois ({deliverables.length})</h2>
          {deliverables.length === 0 ? <p className="text-sm text-storm text-center py-4">Aucun livrable</p> : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {deliverables.map((d: any) => {
                const score = parseFloat(d.score);
                return (
                  <div key={d.id} className="p-3 rounded-lg border border-mist">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">{d.title}</span>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-[10px] font-bold ${
                        score >= 100 ? 'bg-mint' : score >= 70 ? 'bg-honey' : score >= 50 ? 'bg-[#E17055]' : 'bg-coral'}`}>
                        {score}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-storm">
                      <span>{d.submitted}</span>
                      <Badge variant={d.status === 'VALIDE_SANS_RETOUR' ? 'success' : d.status === 'VALIDE_AVEC_RETOUR' ? 'warning' : 'error'}>
                        {d.status.replace(/_/g, ' ')}
                      </Badge>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
