import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, ReferenceLine } from 'recharts';
import api from '../../lib/api-client';

export function Spi360Dashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'tasks'>('overview');

  useEffect(() => {
    api.get('/drh/spi360/dashboard').then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Donnees SPI indisponibles</p>;

  const { kpis, histogram, employees, alerts } = data;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">SPI 360 Performance</h1>
          <p className="text-sm text-storm">Periode: {data.period} -- Score recalcule chaque 24h</p>
        </div>
        <div className="flex gap-2">
          <Link to="/rh/spi360/tasks/needs" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
            Gestion des taches
          </Link>
          <Link to="/rh/spi360/config" className="px-3 py-2 border border-mist rounded-button text-sm text-storm hover:border-iris">
            Configuration
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-2">SPI Global</p>
          <div className="flex items-center gap-3">
            <div className={`w-14 h-14 rounded-full flex items-center justify-center text-white text-xl font-bold ${
              kpis.spi_global >= 90 ? 'bg-mint' : kpis.spi_global >= 70 ? 'bg-honey' : 'bg-coral'}`}>
              {kpis.spi_global}
            </div>
            <div className="flex-1">
              <div className="bg-mist rounded-full h-2"><div className={`h-full rounded-full ${
                kpis.spi_global >= 90 ? 'bg-mint' : kpis.spi_global >= 70 ? 'bg-honey' : 'bg-coral'}`}
                style={{ width: `${Math.min(kpis.spi_global, 100)}%` }} /></div>
              <p className="text-[10px] text-storm mt-1">/100 (peut depasser)</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-2">En Bonus (SPI &ge; 90)</p>
          <p className="text-[28px] font-bold text-mint">{kpis.en_bonus}</p>
          <p className="text-xs text-storm">+20% a +50% salaire</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-2">En Malus (SPI &lt; 70)</p>
          <p className={`text-[28px] font-bold ${kpis.en_malus > 0 ? 'text-coral' : 'text-mint'}`}>{kpis.en_malus}</p>
          <p className="text-xs text-storm">-15% a -30% salaire</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-2">Salaires Geles</p>
          <p className={`text-[28px] font-bold ${kpis.salary_freeze > 0 ? 'text-coral animate-pulse' : ''}`}>{kpis.salary_freeze}</p>
          <p className="text-xs text-storm">5+ jours inactifs</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-2">Candidats Rupture</p>
          <p className={`text-[28px] font-bold ${kpis.termination_candidates > 0 ? 'text-[#D63031]' : 'text-mint'}`}>{kpis.termination_candidates}</p>
          <p className="text-xs text-storm">SPI &lt; 50 x 2 mois</p>
        </div>
      </div>

      {/* Histogram + Alerts */}
      <div className="grid grid-cols-3 gap-6 mb-6">
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Distribution SPI ({kpis.total_employees} employes)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={histogram}>
              <XAxis dataKey="range" tick={{ fontSize: 11, fill: '#636E72' }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#636E72' }} />
              <Tooltip formatter={(v: number, name: string, props: any) => [`${v} employes`, props.payload.label]} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {histogram.map((h: any, i: number) => <Cell key={i} fill={h.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 mt-2">
            {histogram.map((h: any) => (
              <span key={h.range} className="flex items-center gap-1 text-[10px]">
                <span className="w-2.5 h-2.5 rounded" style={{ background: h.color }} /> {h.label}
              </span>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Alertes ({alerts.length})</h2>
          {alerts.length === 0 ? (
            <div className="flex flex-col items-center py-8">
              <div className="w-12 h-12 rounded-full bg-[rgba(0,184,148,0.1)] flex items-center justify-center text-xl mb-2">&#10003;</div>
              <p className="text-sm text-mint font-medium">Aucune alerte</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((a: any, i: number) => (
                <div key={i} className={`p-2 rounded-lg text-xs ${
                  a.level === 'CRITIQUE' ? 'bg-[rgba(255,107,107,0.08)] border border-coral/30' : 'bg-[rgba(253,203,110,0.08)]'}`}>
                  <Badge variant={a.level === 'CRITIQUE' ? 'error' : 'warning'}>{a.level}</Badge>
                  <span className="ml-2 font-medium">{a.employee}</span>
                  <p className="text-storm mt-0.5">{a.message}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Employee Table */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h2 className="text-base font-semibold mb-4">Classement SPI</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">#</th>
              <th className="py-2 text-left text-storm font-medium">Employe</th>
              <th className="py-2 text-left text-storm font-medium">Poste</th>
              <th className="py-2 text-center text-storm font-medium">SPI Jour</th>
              <th className="py-2 text-center text-storm font-medium">SPI Mois</th>
              <th className="py-2 text-center text-storm font-medium">Min/Max</th>
              <th className="py-2 text-center text-storm font-medium">Tendance</th>
              <th className="py-2 text-center text-storm font-medium">Tier</th>
              <th className="py-2 text-right text-storm font-medium">Bonus</th>
              <th className="py-2 text-right text-storm font-medium">Malus</th>
              <th className="py-2 text-center text-storm font-medium">Statut</th>
            </tr></thead>
            <tbody>
              {employees.map((e: any, idx: number) => {
                const spi = parseFloat(e.spi_month);
                return (
                  <tr key={e.employee_id} className={`border-b border-mist hover:bg-[#FAFAFA] transition ${
                    e.salary_freeze ? 'bg-[rgba(255,107,107,0.04)]' : ''}`}>
                    <td className="py-3 text-xs text-storm font-bold">{idx + 1}</td>
                    <td className="py-3">
                      <Link to={`/rh/spi360/${e.employee_id}`} className="font-medium text-iris hover:underline">{e.name}</Link>
                      <p className="text-[10px] text-storm">{e.matricule} -- {e.entity}</p>
                    </td>
                    <td className="py-3 text-xs text-storm">{e.position}</td>
                    <td className="py-3 text-center">
                      <span className="font-mono font-bold">{e.spi_today}</span>
                    </td>
                    <td className="py-3 text-center">
                      <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-white text-xs font-bold ${
                        spi >= 90 ? 'bg-mint' : spi >= 70 ? 'bg-honey' : spi >= 50 ? 'bg-coral' : 'bg-[#D63031]'}`}>
                        {spi.toFixed(0)}
                      </div>
                    </td>
                    <td className="py-3 text-center text-[10px] font-mono text-storm">{parseFloat(e.min).toFixed(0)} / {parseFloat(e.max).toFixed(0)}</td>
                    <td className="py-3 text-center">
                      {e.trend !== null ? (
                        <span className={`text-xs font-bold ${e.trend > 0 ? 'text-mint' : e.trend < 0 ? 'text-coral' : 'text-storm'}`}>
                          {e.trend > 0 ? '+' : ''}{e.trend}
                        </span>
                      ) : <span className="text-xs text-silver">--</span>}
                    </td>
                    <td className="py-3 text-center">
                      <Badge variant={e.tier === 'BON' || e.tier === 'EXCELLENT' || e.tier === 'EXCEPTIONNEL' ? 'success' :
                                      e.tier === 'STANDARD' ? 'neutral' : 'error'}>
                        {e.tier}
                      </Badge>
                    </td>
                    <td className="py-3 text-right font-mono text-mint font-bold text-xs">
                      {parseFloat(e.bonus_amount) > 0 ? `+${formatDA(e.bonus_amount)}` : '--'}
                    </td>
                    <td className="py-3 text-right font-mono text-coral font-bold text-xs">
                      {parseFloat(e.malus_amount) > 0 ? `-${formatDA(e.malus_amount)}` : '--'}
                    </td>
                    <td className="py-3 text-center">
                      {e.salary_freeze && <Badge variant="error">GELE</Badge>}
                      {e.termination_candidate && <Badge variant="error">RUPTURE</Badge>}
                      {!e.salary_freeze && !e.termination_candidate && <Badge variant={e.status === 'VALIDE' ? 'success' : 'warning'}>{e.status}</Badge>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
