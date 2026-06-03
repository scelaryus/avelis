import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatPct } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function OperationsList() {
  const [ops, setOps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/operations/').then(r => { setOps(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-20 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Engagements Operationnels</h1>
        <Link to="/operations/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">+ Nouvel engagement</Link>
      </div>
      {ops.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center text-storm">Aucune opération</div>
      ) : (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-3 px-4 text-left font-medium text-storm">Code</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Titre</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Catégorie</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Statut</th>
              <th className="py-3 px-4 text-right font-medium text-storm">Budget Contrat</th>
              <th className="py-3 px-4 text-right font-medium text-storm">Coût Réel</th>
              <th className="py-3 px-4 font-medium text-storm">Budget</th>
              <th className="py-3 px-4 font-medium text-storm">Avancement</th>
            </tr></thead>
            <tbody>
              {ops.map(op => {
                const budgetPct = op.budget_contrat && op.budget_reel ? (parseFloat(op.budget_reel) / parseFloat(op.budget_contrat) * 100) : 0;
                const overBudget = budgetPct > 100;
                return (
                  <tr key={op.code} onClick={() => window.location.href = `/operations/${op.id}`} className="border-b border-mist hover:bg-[#FAFAFA] transition cursor-pointer">
                    <td className="py-3 px-4 font-mono text-iris font-semibold text-xs">{op.code}</td>
                    <td className="py-3 px-4 font-medium">{op.title}</td>
                    <td className="py-3 px-4"><Badge variant="info">{op.category?.replace(/_/g, ' ')}</Badge></td>
                    <td className="py-3 px-4"><Badge variant={op.status === 'EN_COURS' ? 'success' : op.status === 'VALIDE' ? 'info' : 'neutral'}>{op.status}</Badge></td>
                    <td className="py-3 px-4 text-right font-mono">{formatDA(op.budget_contrat)}</td>
                    <td className={`py-3 px-4 text-right font-mono font-bold ${overBudget ? 'text-coral' : ''}`}>{formatDA(op.budget_reel)}</td>
                    <td className="py-3 px-4 w-32">
                      <div className="bg-mist rounded-full h-2.5 overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${overBudget ? 'bg-coral' : 'bg-iris'}`} style={{ width: `${Math.min(budgetPct, 100)}%` }} />
                      </div>
                      <span className="text-[10px] text-storm">{formatPct(budgetPct)}</span>
                    </td>
                    <td className="py-3 px-4 w-32">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-mist rounded-full h-2.5 overflow-hidden">
                          <div className="bg-mint h-full rounded-full" style={{ width: `${op.avancement_physique || 0}%` }} />
                        </div>
                        <span className="text-xs font-mono">{op.avancement_physique || 0}%</span>
                      </div>
                      {op.surpaiement_risk && <span className="text-[10px] text-coral font-bold">⚠ Surpaiement</span>}
                    </td>
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
