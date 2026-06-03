import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatDate } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function CffList() {
  const [cffs, setCffs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get('/finance/cff/history').then(r => { setCffs(r.data.data || []); setLoading(false); }).catch(() => setLoading(false)); }, []);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-[32px] font-bold">CFF — Coût Fiscal Fictif</h1>
          <p className="text-sm text-storm">Factures RF3 inter-groupe et leur coût fiscal réel</p></div>
        <Link to="/finance/cff/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">Nouvelle facture RF3</Link>
      </div>

      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
            <th className="py-3 px-4 text-left text-storm font-medium">Date</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Émetteur</th>
            <th className="py-3 px-4 text-left text-storm font-medium">→ Récepteur</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Projet</th>
            <th className="py-3 px-4 text-right text-storm font-medium">Montant HT</th>
            <th className="py-3 px-4 text-right text-storm font-medium">CFF Total</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Statut</th>
          </tr></thead>
          <tbody>
            {cffs.map((c: any) => (
              <tr key={c.id} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                <td className="py-3 px-4 font-mono text-xs">{formatDate(c.date)}</td>
                <td className="py-3 px-4"><span className="font-medium">{c.emitter}</span><br/><span className="text-xs text-storm font-mono">{c.emitter_code}</span></td>
                <td className="py-3 px-4"><span className="font-medium">{c.receiver}</span><br/><span className="text-xs text-storm font-mono">{c.receiver_code}</span></td>
                <td className="py-3 px-4">{c.project}</td>
                <td className="py-3 px-4 text-right font-mono">{formatDA(c.montant_ht)}</td>
                <td className="py-3 px-4 text-right font-mono font-bold text-iris">{formatDA(c.cff_total)}</td>
                <td className="py-3 px-4">
                  <Badge variant={c.status === 'IMPUTÉ' ? 'success' : c.status === 'BLOQUÉ' ? 'error' : 'warning'}>{c.status}</Badge>
                  {c.blocked_reason && <p className="text-[10px] text-coral mt-0.5">{c.blocked_reason}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {cffs.length > 0 && cffs[0].distribution && (
        <div className="mt-6 bg-white rounded-card border border-mist p-6 shadow-card">
          <h2 className="font-semibold mb-4">Distribution — {cffs[0].emitter} (dernière facture)</h2>
          <div className="grid grid-cols-4 gap-4">
            {cffs[0].distribution.map((d: any) => (
              <div key={d.associate} className={`p-4 rounded-lg border ${parseFloat(d.amount) === 0 ? 'border-mint bg-[rgba(85,239,196,0.04)]' : 'border-mist'}`}>
                <p className="font-semibold">{d.associate}</p>
                <p className="text-sm text-storm">{d.pct}% entreprise émettrice</p>
                <p className={`text-lg font-mono font-bold mt-1 ${parseFloat(d.amount) === 0 ? 'text-mint' : 'text-charcoal'}`}>{formatDA(d.amount)}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-storm mt-3">⚠ La distribution utilise les % de l'entreprise ÉMETTRICE, jamais les % du projet. Yamina = 0 car elle n'est pas dans AMENFORT.</p>
        </div>
      )}
    </div>
  );
}
