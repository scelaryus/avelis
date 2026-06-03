import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { validatePayment, getAllowedModes } from '../../lib/business-rules';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

export function PaymentForm() {
  const { id } = useParams();
  const nav = useNavigate();
  const { canSeeRF2 } = useStore();
  const [dossier, setDossier] = useState<any>(null);
  const [typeRf, setTypeRf] = useState<'RF1' | 'RF2'>('RF1');
  const [mode, setMode] = useState('CHEQUE');
  const [montant, setMontant] = useState('');
  const [reference, setReference] = useState('');
  const [proofId, setProofId] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');

  useEffect(() => {
    api.get(`/adv/dossiers/${id}`).then(r => setDossier(r.data.data)).catch(() => {});
  }, [id]);

  // Update mode when RF type changes
  useEffect(() => {
    const modes = getAllowedModes(typeRf);
    setMode(modes[0] || '');
  }, [typeRf]);

  // Live validation
  useEffect(() => {
    if (!dossier || !montant) { setErrors([]); return; }
    const amt = parseFloat(montant);
    if (isNaN(amt) || amt <= 0) { setErrors(['Montant invalide']); return; }
    const result = validatePayment(
      { type_rf: typeRf, mode_reglement: mode as any, montant: amt },
      {
        ...dossier,
        total_rf1_paid: parseFloat(dossier.total_rf1_paid || '0'),
        total_rf2_paid: parseFloat(dossier.total_rf2_paid || '0'),
        total_paid: parseFloat(dossier.total_rf1_paid || '0') + parseFloat(dossier.total_rf2_paid || '0'),
        prix_vente_rf1: parseFloat(dossier.rf1 || '0'),
        prix_vente_rf2: parseFloat(dossier.rf2 || '0'),
        prix_vente_reel: parseFloat(dossier.rf1 || '0') + parseFloat(dossier.rf2 || '0'),
        statut_rf2: dossier.rf2_status,
        montant_rf2_securise: parseFloat(dossier.montant_rf2_securise || '0'),
        type_paiement: dossier.type,
        fond_garantie_disponible: 0,
        montant_credit: 0,
      }
    );
    setErrors(result.errors);
  }, [typeRf, mode, montant, dossier]);

  const submit = async () => {
    if (errors.length > 0 || !proofId || !montant) return;
    setSubmitting(true);
    setSuccess('');
    try {
      const res = await api.post('/adv/payments', {
        dossier_id: dossier.numero,
        type_rf: typeRf,
        mode_reglement: mode,
        montant: parseFloat(montant),
        reference: reference || undefined,
      });
      setSuccess(`Paiement ${typeRf} de ${formatDA(montant)} enregistre en attente de validation. Un responsable doit le valider pour qu'il passe a ENCAISSE.`);
      // Reload dossier to update balances
      const updated = await api.get(`/adv/dossiers/${id}`);
      setDossier(updated.data.data);
      setMontant('');
      setReference('');
      setProofId('');
    } catch (e: any) {
      setErrors([e.response?.data?.detail || 'Erreur serveur']);
    } finally {
      setSubmitting(false);
    }
  };

  if (!dossier) return <div className="h-32 bg-mist rounded-card animate-pulse" />;

  const rf1Paid = parseFloat(dossier.total_rf1_paid || '0');
  const rf1Total = parseFloat(dossier.rf1 || '0');
  const rf1Remaining = rf1Total - rf1Paid;

  return (
    <div className="max-w-2xl">
      <Link to={`/adv/dossiers/${id}`} className="text-sm text-iris hover:underline">Dossier {dossier.numero}</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Enregistrer un Paiement</h1>

      {success && (
        <div className="bg-[rgba(85,239,196,0.1)] border border-mint rounded-lg p-3 mb-4 text-sm text-mint font-medium">{success}</div>
      )}

      {/* Dossier context */}
      <div className="bg-[#FAFAFA] rounded-lg p-4 mb-6 text-sm space-y-2">
        <div className="flex justify-between"><span className="text-storm">Client</span><span className="font-semibold">{dossier.client}</span></div>
        <div className="flex justify-between"><span className="text-storm">Lot</span><span className="font-mono">{dossier.lot} ({dossier.lot_typology} {dossier.lot_surface}m2)</span></div>
        <div className="flex justify-between">
          <span className="text-storm">RF1 verse / total</span>
          <span className="font-mono font-bold">{formatDA(rf1Paid)} / {formatDA(rf1Total)} <span className="text-storm font-normal">(reste {formatDA(rf1Remaining)})</span></span>
        </div>
        {canSeeRF2 && dossier.rf2 && (
          <div className="flex justify-between">
            <span className="text-storm">RF2 securise</span>
            <span className="font-mono">{formatDA(dossier.montant_rf2_securise || '0')} / {formatDA(dossier.rf2)}
              <Badge variant={dossier.rf2_status === 'SECURISE' ? 'success' : 'warning'} > {dossier.rf2_status}</Badge>
            </span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-5">

        {/* RF type selector */}
        <div>
          <label className="text-sm font-medium text-storm block mb-2">Type RF <span className="text-coral">*</span></label>
          <div className="flex gap-3">
            <button onClick={() => setTypeRf('RF1')} type="button"
              className={`flex-1 py-2.5 rounded-button text-sm font-medium border-2 transition ${typeRf === 'RF1' ? 'border-ocean bg-[rgba(9,132,227,0.08)] text-ocean' : 'border-mist text-storm'}`}>
              RF1 — Reel Declare (Cheque / Virement)
            </button>
            {canSeeRF2 && (
              <button onClick={() => setTypeRf('RF2')} type="button"
                className={`flex-1 py-2.5 rounded-button text-sm font-medium border-2 transition ${typeRf === 'RF2' ? 'border-iris bg-[rgba(108,92,231,0.08)] text-iris' : 'border-mist text-storm'}`}>
                RF2 — Reel Non Declare (Especes)
              </button>
            )}
          </div>
        </div>

        {/* Mode */}
        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Mode de reglement</label>
          <select value={mode} onChange={e => setMode(e.target.value)}
            className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
            {getAllowedModes(typeRf).map(m => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}
          </select>
          <p className="text-xs text-storm mt-1">
            {typeRf === 'RF1' ? 'PAY-C01: RF1 interdit en especes' : 'PAY-C02: RF2 uniquement en especes'}
          </p>
        </div>

        {/* Amount with smart defaults */}
        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Montant (DA) <span className="text-coral">*</span></label>
          <input type="number" value={montant} onChange={e => setMontant(e.target.value)}
            className={`w-full border rounded-input px-4 py-2.5 text-sm font-mono focus:ring-2 outline-none ${errors.length > 0 ? 'border-coral focus:ring-coral/20' : 'border-mist focus:border-iris focus:ring-lavender'}`}
            placeholder={typeRf === 'RF1' ? `Max: ${formatDA(rf1Remaining)}` : 'Montant en especes'} />
          {typeRf === 'RF1' && rf1Remaining > 0 && (
            <button onClick={() => setMontant(String(rf1Remaining))} type="button"
              className="text-xs text-iris hover:underline mt-1">Remplir le solde RF1 ({formatDA(rf1Remaining)})</button>
          )}
          {errors.map((e, i) => <p key={i} className="text-xs text-coral mt-1 font-medium">{e}</p>)}
        </div>

        {/* Reference */}
        <div>
          <label className="text-sm font-medium text-storm block mb-1.5">Reference {typeRf === 'RF1' ? '(N cheque / ref virement)' : '(N recu interne)'}</label>
          <input type="text" value={reference} onChange={e => setReference(e.target.value)}
            className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
            placeholder={typeRf === 'RF1' ? 'CHQ-XXXX ou VIR-XXXX' : 'REC-XXXX'} />
        </div>

        {/* Proof */}
        <ProofUpload
          onUploaded={id => setProofId(id)}
          label={typeRf === 'RF1' ? 'Scan du cheque ou avis de virement' : 'Recu interne (NON officiel, NON visible au client)'}
        />

        <button onClick={submit}
          disabled={!montant || parseFloat(montant) <= 0 || errors.length > 0 || !proofId || submitting}
          className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Enregistrement...' : `Enregistrer paiement ${typeRf} de ${montant ? formatDA(montant) : '...'}`}
        </button>
      </div>
    </div>
  );
}
