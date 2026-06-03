import { useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { formatDate } from '../../lib/format';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

const LEAVE_TYPES = [
  { value: 'annuel', label: 'Congé annuel', doc: false },
  { value: 'maladie', label: 'Congé maladie', doc: 'Certificat médical' },
  { value: 'maternite', label: 'Congé maternité', doc: 'Certificat + attestation CNAS' },
  { value: 'paternite', label: 'Congé paternité', doc: 'Acte de naissance' },
  { value: 'mariage', label: 'Congé mariage', doc: 'Acte de mariage' },
  { value: 'deces', label: 'Congé décès', doc: 'Acte de décès' },
  { value: 'circoncision', label: 'Congé circoncision', doc: false },
  { value: 'hajj', label: 'Congé hajj', doc: false },
  { value: 'sans_solde', label: 'Congé sans solde', doc: false },
];

export function LeaveManagement() {
  const [leaves, setLeaves] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<any>({ type: 'annuel' });
  const [proofId, setProofId] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get('/drh/leave/requests').then(r => { setLeaves(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const selectedType = LEAVE_TYPES.find(t => t.value === form.type);
  const needsDoc = selectedType?.doc;
  const needsJustification = form.type === 'sans_solde';

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post('/drh/leave/requests', { ...form, justificative_doc_id: proofId || undefined });
      const r = await api.get('/drh/leave/requests');
      setLeaves(r.data.data || []);
      setShowForm(false);
      setForm({ type: 'annuel' });
    } catch {} finally { setSubmitting(false); }
  };

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Congés</h1>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">Nouvelle demande</button>
      </div>

      {showForm && (
        <div className="bg-white rounded-card border border-iris p-6 shadow-card mb-6 space-y-4">
          <h2 className="font-semibold">Nouvelle demande de congé</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">Type <span className="text-coral">*</span></label>
              <select value={form.type} onChange={e => setForm((p: any) => ({ ...p, type: e.target.value }))}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                {LEAVE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">Date début <span className="text-coral">*</span></label>
              <input type="date" value={form.start || ''} onChange={e => setForm((p: any) => ({ ...p, start: e.target.value }))}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">Date fin <span className="text-coral">*</span></label>
              <input type="date" value={form.end || ''} onChange={e => setForm((p: any) => ({ ...p, end: e.target.value }))}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
          </div>
          {needsJustification && (
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">Justification <span className="text-coral">*</span> <span className="text-silver text-xs">(min 20 chars)</span></label>
              <textarea value={form.justification || ''} onChange={e => setForm((p: any) => ({ ...p, justification: e.target.value }))}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none resize-none h-20" />
            </div>
          )}
          {needsDoc && (
            <ProofUpload onUploaded={id => setProofId(id)} label={`${needsDoc} (OBLIGATOIRE)`} />
          )}
          <div className="flex gap-3">
            <button onClick={submit} disabled={!form.start || !form.end || submitting || (needsDoc && !proofId) || (needsJustification && (form.justification || '').length < 20)}
              className="px-6 py-2.5 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
              {submitting ? 'Envoi...' : 'Soumettre la demande'}
            </button>
            <button onClick={() => setShowForm(false)} className="px-6 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-gray-50">Annuler</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
            <th className="py-3 px-4 text-left font-medium text-storm">Employé</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Type</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Du</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Au</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Jours</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Statut</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Actions</th>
          </tr></thead>
          <tbody>
            {leaves.length === 0 ? (
              <tr><td colSpan={7} className="py-8 text-center text-storm">Aucune demande de congé</td></tr>
            ) : leaves.map((l: any, i: number) => (
              <tr key={i} className="border-b border-mist hover:bg-[#FAFAFA]">
                <td className="py-3 px-4 font-medium">{l.employee}</td>
                <td className="py-3 px-4"><Badge variant="info">{l.type}</Badge></td>
                <td className="py-3 px-4 font-mono text-xs">{formatDate(l.start)}</td>
                <td className="py-3 px-4 font-mono text-xs">{formatDate(l.end)}</td>
                <td className="py-3 px-4">{l.days}</td>
                <td className="py-3 px-4">
                  <Badge variant={l.status === 'APPROUVE' ? 'success' : l.status === 'REJETE' ? 'error' : l.status === 'FRAUD_ALERT' ? 'error' : 'warning'}>{l.status}</Badge>
                  {l.status === 'FRAUD_ALERT' && <p className="text-[10px] text-coral font-bold">Badge détecté pendant absence</p>}
                </td>
                <td className="py-3 px-4">
                  {l.status === 'EN_ATTENTE' && (
                    <div className="flex gap-2">
                      <button className="text-xs text-mint font-medium hover:underline">Approuver</button>
                      <button className="text-xs text-coral font-medium hover:underline">Rejeter</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
