import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { formatDA, formatPct } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import api from '../../lib/api-client';

export function SpiDetail() {
  const { employeeId } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (employeeId) {
      api.get(`/drh/spi/${employeeId}`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
    }
  }, [employeeId]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Profil SPI introuvable</p>;

  const { employee, profile, history, current_evaluation, objectives, alerts } = data;
  const spi = current_evaluation ? parseFloat(current_evaluation.spi) : 0;

  const quantObjs = objectives.filter((o: any) => o.type === 'QUANTITATIF');
  const qualObjs = objectives.filter((o: any) => o.type === 'QUALITATIF');

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-6 mb-6">
        <div className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl font-bold ${
          spi >= 80 ? 'bg-mint' : spi >= 60 ? 'bg-honey' : 'bg-coral'}`}>
          {spi.toFixed(0)}
        </div>
        <div>
          <h1 className="text-[28px] font-bold">{employee.name}</h1>
          <p className="text-sm text-storm">{employee.matricule} — {employee.position}</p>
          <p className="text-xs text-storm">Salaire base: {formatDA(employee.salary_base)} — Taux prime: {profile.taux_prime}% — Type: {profile.role_type}</p>
        </div>
        {current_evaluation && (
          <div className="ml-auto text-right">
            <p className="text-sm text-storm">Prime Rendement</p>
            <p className="text-xl font-bold font-mono text-iris">{formatDA(current_evaluation.prime)}</p>
            <Badge variant={current_evaluation.status === 'VALIDE' ? 'success' : current_evaluation.status === 'CONTESTE' ? 'error' : 'warning'}>
              {current_evaluation.status}
            </Badge>
          </div>
        )}
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2 mb-6">
          {alerts.map((a: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg border-l-4 ${
              a.level === 'CRITIQUE' ? 'bg-[rgba(255,107,107,0.06)] border-coral' :
              a.level === 'ALERTE' ? 'bg-[rgba(225,112,85,0.06)] border-[#E17055]' :
              'bg-[rgba(0,184,148,0.06)] border-mint'}`}>
              <span className="text-xs font-bold">{a.level}:</span> <span className="text-sm">{a.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* 12-month chart */}
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Evolution SPI (12 mois)</h2>
          {history.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history}>
                <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#636E72' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#636E72' }} />
                <Tooltip formatter={(v: number) => `${v}/100`} />
                <ReferenceLine y={70} stroke="#FF6B6B" strokeDasharray="4 4" label={{ value: 'Seuil 70', fontSize: 10 }} />
                <ReferenceLine y={90} stroke="#00B894" strokeDasharray="4 4" label={{ value: 'Top 90', fontSize: 10 }} />
                <Line type="monotone" dataKey="spi" stroke="#6C5CE7" strokeWidth={3} dot={{ r: 5, fill: '#6C5CE7' }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-storm text-center py-8">Aucun historique</p>}
        </div>

        {/* Score summary */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Decomposition Score</h2>
          {current_evaluation ? (
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-storm">Quantitatif (60%)</span>
                  <span className="font-mono font-bold">{parseFloat(current_evaluation.quant).toFixed(1)}</span>
                </div>
                <div className="bg-mist rounded-full h-3 overflow-hidden">
                  <div className="bg-ocean h-full rounded-full" style={{ width: `${parseFloat(current_evaluation.quant)}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-storm">Qualitatif (40%)</span>
                  <span className="font-mono font-bold">{parseFloat(current_evaluation.qual).toFixed(1)}</span>
                </div>
                <div className="bg-mist rounded-full h-3 overflow-hidden">
                  <div className="bg-iris h-full rounded-full" style={{ width: `${parseFloat(current_evaluation.qual)}%` }} />
                </div>
              </div>
              <div className="border-t border-mist pt-3">
                <p className="text-xs text-storm">SPI = 60% x {parseFloat(current_evaluation.quant).toFixed(1)} + 40% x {parseFloat(current_evaluation.qual).toFixed(1)}</p>
                <p className="text-lg font-bold font-mono mt-1">{parseFloat(current_evaluation.spi).toFixed(2)} / 100</p>
              </div>
              <div className="border-t border-mist pt-3">
                <p className="text-xs text-storm">Prime = {formatDA(employee.salary_base)} x {profile.taux_prime}% x {parseFloat(current_evaluation.spi).toFixed(0)}/100</p>
                <p className="text-lg font-bold font-mono text-iris mt-1">{formatDA(current_evaluation.prime)}</p>
              </div>
            </div>
          ) : <p className="text-sm text-storm text-center py-8">Aucune evaluation</p>}
        </div>
      </div>

      {/* Objectives tables */}
      {quantObjs.length > 0 && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-6">
          <h2 className="text-base font-semibold mb-4">Objectifs Quantitatifs ({quantObjs.length})</h2>
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Objectif</th>
              <th className="py-2 text-center text-storm font-medium">Cible</th>
              <th className="py-2 text-center text-storm font-medium">Realise</th>
              <th className="py-2 text-center text-storm font-medium">Atteinte %</th>
              <th className="py-2 text-center text-storm font-medium">Poids</th>
              <th className="py-2 text-center text-storm font-medium">Score Pondere</th>
              <th className="py-2 text-center text-storm font-medium">Source</th>
            </tr></thead>
            <tbody>
              {quantObjs.map((o: any, i: number) => {
                const ach = parseFloat(o.achievement_pct);
                return (
                  <tr key={i} className="border-b border-mist">
                    <td className="py-2">{o.title}</td>
                    <td className="py-2 text-center font-mono">{o.target} {o.unit}</td>
                    <td className="py-2 text-center font-mono font-bold">{o.actual}</td>
                    <td className="py-2 text-center">
                      <span className={`font-mono font-bold ${ach >= 100 ? 'text-mint' : ach >= 70 ? 'text-honey' : 'text-coral'}`}>
                        {ach.toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-2 text-center text-storm">{o.weight}%</td>
                    <td className="py-2 text-center font-mono font-bold">{parseFloat(o.weighted_score).toFixed(1)}</td>
                    <td className="py-2 text-center">
                      <Badge variant={o.source === 'AUTOMATIQUE' ? 'info' : 'neutral'}>{o.source}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {qualObjs.length > 0 && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">Objectifs Qualitatifs ({qualObjs.length})</h2>
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Objectif</th>
              <th className="py-2 text-center text-storm font-medium">Cible</th>
              <th className="py-2 text-center text-storm font-medium">Realise</th>
              <th className="py-2 text-center text-storm font-medium">Atteinte %</th>
              <th className="py-2 text-center text-storm font-medium">Poids</th>
              <th className="py-2 text-center text-storm font-medium">Score Pondere</th>
              <th className="py-2 text-center text-storm font-medium">Source</th>
            </tr></thead>
            <tbody>
              {qualObjs.map((o: any, i: number) => {
                const ach = parseFloat(o.achievement_pct);
                return (
                  <tr key={i} className="border-b border-mist">
                    <td className="py-2">{o.title}</td>
                    <td className="py-2 text-center font-mono">{o.target}</td>
                    <td className="py-2 text-center font-mono font-bold">{o.actual}</td>
                    <td className="py-2 text-center">
                      <span className={`font-mono font-bold ${ach >= 100 ? 'text-mint' : ach >= 70 ? 'text-honey' : 'text-coral'}`}>{ach.toFixed(0)}%</span>
                    </td>
                    <td className="py-2 text-center text-storm">{o.weight}%</td>
                    <td className="py-2 text-center font-mono font-bold">{parseFloat(o.weighted_score).toFixed(1)}</td>
                    <td className="py-2 text-center"><Badge variant="neutral">{o.source}</Badge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
