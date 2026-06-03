import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { validateCCAWithdrawal } from '../../lib/business-rules';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

export function CcaWithdraw() {
  const { associateId } = useParams();
  const nav = useNavigate();
  const [entities, setEntities] = useState<any[]>([]);
  const [entityId, setEntityId] = useState('');
  const [amount, setAmount] = useState(0);
  const [justification, setJustification] = useState('');
  const [proofId, setProofId] = useState('');
  const [ccaData, setCcaData] = useState<any>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/finance/cca/${associateId}`).then(r => {
      const d = r.data.data;
      setEntities(d?.entities || []);
      setCcaData(d);
    }).catch(() => {});
  }, [associateId]);

  useEffect(() => {
    if (!entityId || !amount) { setErrors([]); return; }
    const ent = entities.find(e => e.entity_id === entityId);
    if (!ent) return;
    const result = validateCCAWithdrawal(amount, parseFloat(ent.balance), parseFloat(ent.global_balance));
    setErrors(result.errors);
  }, [amount, entityId, entities]);

  const selectedEntity = entities.find(e => e.entity_id === entityId);
  const max50 = selectedEntity ? parseFloat(selectedEntity.balance) * 0.5 : 0;
  const globalNeg = selectedEntity ? parseFloat(selectedEntity.global_balance) <= 0 : false;

  const submit = async () => {
    if (errors.length > 0 || !proofId || justification.length < 20) return;
    setSubmitting(true);
    try {
      await api.post(`/finance/cca/${associateId}/withdraw`, { entity_id: entityId, amount, justification, justificative_doc_id: proofId });
      nav(`/finance/cca/${associateId}`);
    } catch (e: any) {
      setErrors([e.response?.data?.detail || 'Erreur serveur']);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <Link to={`/finance/cca`} className="text-sm text-iris hover:underline">← CCA Associés</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Demande de Retrait CCA</h1>

      {globalNeg && (
        <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-4 mb-6">
          <p className="text-sm text-coral font-bold">Solde global CCA négatif — retrait interdit.</p>
        </div>
      )}

      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-5">
        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Entité <span className="text-coral">*</span></label>
          <select value={entityId} onChange={e => setEntityId(e.target.value)} disabled={globalNeg}
            className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris focus:ring-2 focus:ring-lavender outline-none">
            <option value="">Sélectionnez une entité</option>
            {entities.map(e => (
              <option key={e.entity_id} value={e.entity_id}>{e.entity_name} — Solde: {formatDA(e.balance)}</option>
            ))}
          </select>
        </div>

        {selectedEntity && (
          <div className="bg-[#FAFAFA] rounded-lg p-4 space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-storm">Solde individuel</span><span className="font-mono font-bold">{formatDA(selectedEntity.balance)}</span></div>
            <div className="flex justify-between"><span className="text-storm">Maximum autorisé (50%)</span><span className="font-mono font-bold text-iris">{formatDA(max50)}</span></div>
            <div className="flex justify-between"><span className="text-storm">Solde global CCA entité</span><span className={`font-mono font-bold ${parseFloat(selectedEntity.global_balance) > 0 ? 'text-mint' : 'text-coral'}`}>{formatDA(selectedEntity.global_balance)}</span></div>
          </div>
        )}

        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Montant du retrait <span className="text-coral">*</span></label>
          <div className="relative">
            <input type="number" value={amount || ''} onChange={e => setAmount(parseFloat(e.target.value) || 0)}
              disabled={globalNeg}
              className={`w-full border rounded-input px-4 py-2.5 text-sm font-mono focus:ring-2 outline-none ${errors.length > 0 ? 'border-coral focus:ring-coral/20' : 'border-mist focus:border-iris focus:ring-lavender'}`}
              placeholder="0" />
            <span className="absolute right-4 top-2.5 text-sm text-storm">DA</span>
          </div>
          {errors.map((e, i) => <p key={i} className="text-xs text-coral mt-1">{e}</p>)}
        </div>

        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Justification <span className="text-coral">*</span> <span className="text-silver text-xs">({justification.length}/20 min)</span></label>
          <textarea value={justification} onChange={e => setJustification(e.target.value)}
            className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris focus:ring-2 focus:ring-lavender outline-none resize-none h-24"
            placeholder="Motif du retrait (minimum 20 caractères)" />
        </div>

        <ProofUpload onUploaded={(id) => setProofId(id)} label="Pièce justificative (ordre de virement ou PV signé)" />

        <button onClick={submit}
          disabled={!entityId || !amount || errors.length > 0 || !proofId || justification.length < 20 || submitting || globalNeg}
          className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Traitement...' : 'Demander le retrait'}
        </button>
      </div>
    </div>
  );
}
