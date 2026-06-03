import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatPct } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line } from 'recharts';
import api from '../../lib/api-client';

export function SpiDashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));

  useEffect(() => {
    setLoading(true);
    api.get(`/drh/spi?period=${period}`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [period]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Aucune donnee SPI</p>;

  const { kpis, histogram, employees } = data;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">SPI Performance</h1>
          <p className="text-sm text-storm">Periode: {data.period || period}</p>
        </div>
        <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
          className="border border-mist rounded-input px-4 py-2 text-sm focus:border-iris outline-none" />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <div className="flex items-center gap-3">
            <div className="w-14 h-14 rounded-full bg-iris flex items-center justify-center">
              <span className="text-white text-xl font-bold font-mono">{kpis.spi_moyen}</span>
            </div>
            <div>
              <p className="text-sm text-storm">SPI Moyen</p>
              <p className="text-xs text-storm">/100</p>
            </div>
          </div>
          <div className="mt-3 bg-mist rounded-full h-2.5 overflow-hidden">
            <div className={`h-full rounded-full ${kpis.spi_moyen >= 80 ? 'bg-mint' : kpis.spi_moyen >= 60 ? 'bg-honey' : 'bg-coral'}`}
              style={{ width: `${kpis.spi_moyen}%` }} />
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <p className="text-sm text-storm mb-2">En Alerte (SPI &lt; 70)</p>
          <p className={`text-[28px] font-bold ${kpis.en_alerte > 0 ? 'text-coral' : 'text-mint'}`}>{kpis.en_alerte}</p>
          <p className="text-xs text-storm mt-1">/ {kpis.total_employees} employes</p>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <p className="text-sm text-storm mb-2">Top Performers (&gt; 90)</p>
          <p className="text-[28px] font-bold text-mint">{kpis.top_performers}</p>
          <p className="text-xs text-storm mt-1">Candidats promotion</p>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <p className="text-sm text-storm mb-2">Evaluations en Attente</p>
          <p className={`text-[28px] font-bold ${kpis.evaluations_pending > 0 ? 'text-honey' : 'text-mint'}`}>{kpis.evaluations_pending}</p>
          <p className="text-xs text-storm mt-1">A valider</p>
        </div>
      </div>

      {/* Histogram + Employee table */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* Distribution histogram */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Distribution SPI</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={histogram}>
              <XAxis dataKey="range" tick={{ fontSize: 12, fill: '#636E72' }} />
              <YAxis tick={{ fontSize: 12, fill: '#636E72' }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {histogram.map((h: any, i: number) => <Cell key={i} fill={h.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Employee scores */}
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Employes ({employees.length})</h2>
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Employe</th>
              <th className="py-2 text-left text-storm font-medium">Poste</th>
              <th className="py-2 text-center text-storm font-medium">SPI</th>
              <th className="py-2 text-center text-storm font-medium">Quant</th>
              <th className="py-2 text-center text-storm font-medium">Qual</th>
              <th className="py-2 text-right text-storm font-medium">Prime</th>
              <th className="py-2 text-center text-storm font-medium">Tendance</th>
            </tr></thead>
            <tbody>
              {employees.map((e: any) => {
                const spi = parseFloat(e.spi);
                return (
                  <tr key={e.employee_id} className="border-b border-mist hover:bg-[#FAFAFA] cursor-pointer">
                    <td className="py-3">
                      <Link to={`/rh/spi/${e.employee_id}`} className="font-medium text-iris hover:underline">{e.name}</Link>
                      <p className="text-xs text-storm">{e.matricule}</p>
                    </td>
                    <td className="py-3 text-xs text-storm">{e.position}</td>
                    <td className="py-3 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                          spi >= 80 ? 'bg-mint' : spi >= 60 ? 'bg-honey' : 'bg-coral'}`}>
                          {spi.toFixed(0)}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 text-center font-mono text-xs">{parseFloat(e.quant).toFixed(0)}</td>
                    <td className="py-3 text-center font-mono text-xs">{parseFloat(e.qual).toFixed(0)}</td>
                    <td className="py-3 text-right font-mono font-bold text-sm">{formatDA(e.prime)}</td>
                    <td className="py-3 text-center">
                      {e.trend !== null ? (
                        <span className={`text-xs font-bold ${e.trend > 0 ? 'text-mint' : e.trend < 0 ? 'text-coral' : 'text-storm'}`}>
                          {e.trend > 0 ? '+' : ''}{e.trend?.toFixed(1)}
                        </span>
                      ) : <span className="text-xs text-silver">--</span>}
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
