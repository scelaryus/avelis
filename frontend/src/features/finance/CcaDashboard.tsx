import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatDate } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import api from '../../lib/api-client';

export function CcaDashboard() {
  const [ccas, setCcas] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [movements, setMovements] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [movLoading, setMovLoading] = useState(false);

  useEffect(() => {
    api.get('/finance/cca').then(r => { setCcas(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const loadMovements = (assoc: any) => {
    setSelected(assoc);
    setMovLoading(true);
    api.get(`/finance/cca/${encodeURIComponent(assoc.associate)}/movements`).then(r => {
      setMovements(r.data.data || []);
      setMovLoading(false);
    }).catch(() => setMovLoading(false));
  };

  if (loading) return <div className="grid grid-cols-4 gap-6">{[1,2,3,4].map(i => <div key={i} className="h-40 bg-mist rounded-card animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">CCA Associes</h1>
      </div>

      <div className="grid grid-cols-4 gap-6 mb-8">
        {ccas.map(a => {
          const bal = parseFloat(a.total_balance);
          const isSelected = selected?.associate === a.associate;
          return (
            <div key={a.associate} onClick={() => loadMovements(a)}
              className={`bg-white rounded-card border-2 p-6 shadow-card hover:shadow-card-hover transition cursor-pointer ${
                isSelected ? 'border-iris' : 'border-[#E0E0E0]'}`}>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-iris text-white flex items-center justify-center font-bold text-sm">
                  {a.associate.split(' ').pop()?.[0] || '?'}
                </div>
                <div>
                  <p className="font-semibold text-sm">{a.associate}</p>
                  <p className="text-xs text-storm">{a.entities} entites</p>
                </div>
              </div>
              <p className={`text-[28px] font-bold font-mono ${bal >= 0 ? 'text-mint' : 'text-coral'}`}>
                {formatDA(a.total_balance)}
              </p>
              {a.per_entity && (
                <div className="mt-3 space-y-1">
                  {a.per_entity.map((e: any) => (
                    <div key={e.entity_code} className="flex justify-between text-xs">
                      <span className="text-storm">{e.entity_code}</span>
                      <span className={`font-mono ${parseFloat(e.balance) < 0 ? 'text-coral' : 'text-mint'}`}>{formatDA(e.balance)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {selected && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Mouvements - {selected.associate}</h2>
            <Link to={`/finance/cca/${encodeURIComponent(selected.associate)}/withdraw`}
              className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">Retrait CCA</Link>
          </div>
          {movLoading ? (
            <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-10 bg-mist rounded animate-pulse" />)}</div>
          ) : movements.length === 0 ? (
            <p className="text-sm text-storm py-4 text-center">Aucun mouvement enregistre</p>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="border-b-2 border-mist">
                <th className="py-2 text-left text-storm font-medium">Date</th>
                <th className="py-2 text-left text-storm font-medium">Type</th>
                <th className="py-2 text-left text-storm font-medium">Libelle</th>
                <th className="py-2 text-left text-storm font-medium">Entite</th>
                <th className="py-2 text-right text-storm font-medium">Montant</th>
              </tr></thead>
              <tbody>
                {movements.map((m: any) => (
                  <tr key={m.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                    <td className="py-2 font-mono text-xs">{formatDate(m.date)}</td>
                    <td className="py-2">
                      <Badge variant={m.type === 'DEPOT' || m.type === 'DISTRIBUTION' ? 'success' : m.type === 'CFF' ? 'warning' : 'error'}>
                        {m.type}
                      </Badge>
                    </td>
                    <td className="py-2 text-sm">{m.label}</td>
                    <td className="py-2 text-xs text-storm">{m.entity_code}</td>
                    <td className={`py-2 text-right font-mono font-bold ${parseFloat(m.montant) >= 0 ? 'text-mint' : 'text-coral'}`}>
                      {parseFloat(m.montant) >= 0 ? '+' : ''}{formatDA(m.montant)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
