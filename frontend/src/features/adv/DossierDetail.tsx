import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA, formatDate, rfLabel } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { PreconditionChecklist } from '../../components/shared/PreconditionChecklist';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

const TABS = ['Resume', 'Paiements', 'Echeancier', 'Documents', 'Deblocages', 'Notaire', 'Historique'];

export function DossierDetail() {
  const { id } = useParams();
  const { canSeeRF2 } = useStore();
  const [dossier, setDossier] = useState<any>(null);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [transitionModal, setTransitionModal] = useState<any>(null);

  const reload = useCallback(() => {
    api.get(`/adv/dossiers/${id}`).then(r => { setDossier(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);
  useEffect(() => { reload(); }, [reload]);

  const doTransition = async (target: string) => {
    try {
      await api.patch(`/adv/dossiers/${id}/transition`, { target_state: target });
      reload();
      setTransitionModal(null);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Transition echouee');
    }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!dossier) return <p className="text-storm">Dossier introuvable</p>;

  const rf1Pct = dossier.rf1 && parseFloat(dossier.rf1) > 0 ? (parseFloat(dossier.total_rf1_paid) / parseFloat(dossier.rf1) * 100) : 0;
  const rf2Pct = canSeeRF2 && dossier.rf2 && parseFloat(dossier.rf2) > 0 ? (parseFloat(dossier.montant_rf2_securise || '0') / parseFloat(dossier.rf2) * 100) : 0;

  return (
    <div>
      <Link to="/adv/lots" className="text-sm text-iris hover:underline">Lots EDD</Link>
      <div className="flex items-center gap-4 mt-2 mb-4">
        <h1 className="text-[32px] font-bold">{dossier.numero}</h1>
        <Badge variant={dossier.status === 'ENGAGE' ? 'info' : dossier.status === 'CLOTURE' ? 'success' : 'warning'}>{dossier.status?.replace(/_/g, ' ')}</Badge>
        <Badge variant="neutral">{dossier.type?.replace(/_/g, ' ')}</Badge>
      </div>

      {/* Info row */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <div className="bg-white rounded-card border border-mist p-3 shadow-card"><p className="text-xs text-storm">Client</p><p className="text-sm font-semibold">{dossier.client}</p></div>
        <div className="bg-white rounded-card border border-mist p-3 shadow-card"><p className="text-xs text-storm">Lot</p><p className="text-sm font-mono">{dossier.lot} ({dossier.lot_typology} {dossier.lot_surface}m2)</p></div>
        <div className="bg-white rounded-card border border-mist p-3 shadow-card"><p className="text-xs text-storm">Projet</p><p className="text-sm font-semibold">{dossier.project_name}</p></div>
        <div className="bg-white rounded-card border border-mist p-3 shadow-card"><p className="text-xs text-storm">Prix RF1</p><p className="text-sm font-mono font-bold">{formatDA(dossier.rf1)}</p></div>
        {canSeeRF2 && dossier.rf2 && <div className="bg-white rounded-card border border-mist p-3 shadow-card"><p className="text-xs text-storm">Prix Reel</p><p className="text-sm font-mono font-bold">{formatDA(dossier.prix_reel)}</p></div>}
      </div>

      {/* Transitions */}
      {dossier.transitions?.length > 0 && (
        <div className="flex gap-2 mb-6">
          <span className="text-xs text-storm self-center mr-2">Actions:</span>
          {dossier.transitions.map((t: any) => (
            <button key={t.target}
              onClick={() => t.allowed ? doTransition(t.target) : setTransitionModal(t)}
              className={`px-3 py-1.5 rounded-button text-xs font-medium transition ${
                t.allowed ? 'bg-iris text-white hover:bg-rose-800' : 'bg-mist text-storm border border-mist'
              }`}>
              {t.target.replace(/_/g, ' ')} {!t.allowed && '(bloque)'}
            </button>
          ))}
          <Link to={`/adv/dossiers/${id}/payment`} className="px-3 py-1.5 bg-mint text-white rounded-button text-xs font-medium hover:bg-[#00A884]">+ Paiement</Link>
        </div>
      )}

      {/* Transition blocker modal */}
      {transitionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setTransitionModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[500px] shadow-xl">
            <h3 className="text-lg font-bold mb-4">Transition {transitionModal.target.replace(/_/g, ' ')}</h3>
            <PreconditionChecklist
              title="Conditions requises"
              conditions={transitionModal.blockers.map((b: string) => ({ label: b, met: false }))}
            />
            <button onClick={() => setTransitionModal(null)} className="mt-4 w-full py-2 border border-mist rounded-button text-sm text-storm">Fermer</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-mist mb-6">
        {TABS.map((t, i) => (
          (t !== 'Deblocages' || dossier.type === 'CREDIT_BANCAIRE') && (
            <button key={t} onClick={() => setTab(i)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition ${tab === i ? 'border-iris text-iris' : 'border-transparent text-storm hover:text-charcoal'}`}>
              {t}
            </button>
          )
        ))}
      </div>

      {/* Tab 0: Resume */}
      {tab === 0 && <TabResume dossier={dossier} canSeeRF2={canSeeRF2} rf1Pct={rf1Pct} rf2Pct={rf2Pct} />}
      {/* Tab 1: Paiements */}
      {tab === 1 && <TabPaiements dossier={dossier} id={id!} />}
      {/* Tab 2: Echeancier */}
      {tab === 2 && <TabEcheancier dossier={dossier} id={id!} />}
      {/* Tab 3: Documents */}
      {tab === 3 && <TabDocuments id={id!} />}
      {/* Tab 4: Deblocages */}
      {tab === 4 && dossier.type === 'CREDIT_BANCAIRE' && <TabDeblocages id={id!} dossier={dossier} />}
      {/* Tab 5: Notaire */}
      {tab === 5 && <TabNotaire id={id!} />}
      {/* Tab 6: Historique */}
      {tab === 6 && <TabHistorique id={id!} />}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 0: Resume
// ═══════════════════════════════════════════════════════════════════════════════

function TabResume({ dossier, canSeeRF2, rf1Pct, rf2Pct }: any) {
  return (
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-white rounded-card border border-mist p-6 space-y-4">
        <h3 className="font-semibold">Paiements RF1</h3>
        <div className="bg-mist rounded-full h-3"><div className="bg-iris h-full rounded-full transition-all" style={{ width: `${Math.min(100, rf1Pct)}%` }} /></div>
        <p className="text-sm font-mono">{formatDA(dossier.total_rf1_paid)} / {formatDA(dossier.rf1)} ({rf1Pct.toFixed(0)}%)</p>
        {canSeeRF2 && dossier.rf2 && parseFloat(dossier.rf2) > 0 && (
          <>
            <h3 className="font-semibold mt-4">Securisation RF2</h3>
            <div className="bg-mist rounded-full h-3"><div className={`h-full rounded-full ${rf2Pct >= 100 ? 'bg-mint' : 'bg-honey'}`} style={{ width: `${Math.min(100, rf2Pct)}%` }} /></div>
            <p className="text-sm">{dossier.rf2_status === 'SECURISE' ? 'Securise' : `${rf2Pct.toFixed(0)}% — ${formatDA(dossier.montant_rf2_securise)} / ${formatDA(dossier.rf2)}`}</p>
          </>
        )}
      </div>
      <div className="bg-white rounded-card border border-mist p-6">
        <h3 className="font-semibold mb-3">Informations</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-storm">Date creation</span><span>{dossier.created_at}</span></div>
          <div className="flex justify-between"><span className="text-storm">Type paiement</span><span className="font-medium">{dossier.type?.replace(/_/g, ' ')}</span></div>
          <div className="flex justify-between"><span className="text-storm">Statut RF2</span>
            <Badge variant={dossier.rf2_status === 'SECURISE' ? 'success' : 'warning'}>{dossier.rf2_status}</Badge></div>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 1: Paiements
// ═══════════════════════════════════════════════════════════════════════════════

function TabPaiements({ dossier, id }: { dossier: any; id: string }) {
  const [validateModal, setValidateModal] = useState<any>(null);
  const [valStep, setValStep] = useState<'upload' | 'analyzing' | 'confirm'>('upload');
  const [valAiData, setValAiData] = useState<any>(null);
  const [valAiError, setValAiError] = useState('');
  const [valSubmitting, setValSubmitting] = useState(false);
  const [amountMismatch, setAmountMismatch] = useState(false);

  const openValidateModal = (payment: any) => {
    setValidateModal(payment);
    setValStep('upload');
    setValAiData(null);
    setValAiError('');
    setAmountMismatch(false);
  };

  const handleProofUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setValStep('analyzing');
    setValAiError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/adv/payments/analyze-cheque', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const d = res.data.data;
      setValAiData(d);
      if (d.error) setValAiError(d.error);
      // Check amount mismatch
      if (d.amount && validateModal) {
        const expected = parseFloat(validateModal.montant);
        const extracted = parseFloat(d.amount);
        setAmountMismatch(Math.abs(expected - extracted) > 1);
      }
      setValStep('confirm');
    } catch (err: any) {
      setValAiError(err.response?.data?.detail || 'Erreur analyse');
      setValStep('confirm');
    }
  };

  const handleProofDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.createElement('input');
      input.files = dt.files;
      handleProofUpload({ target: input } as any);
    }
  };

  const submitValidation = async () => {
    if (!validateModal) return;
    setValSubmitting(true);
    try {
      await api.post(`/adv/payments/${validateModal.id}/validate`);
      setValidateModal(null);
      window.location.reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur validation');
    } finally {
      setValSubmitting(false);
    }
  };

  const submitReject = async (reason: string) => {
    if (!validateModal) return;
    setValSubmitting(true);
    try {
      await api.post(`/adv/payments/${validateModal.id}/reject`, { reason });
      setValidateModal(null);
      window.location.reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur rejet');
    } finally {
      setValSubmitting(false);
    }
  };

  return (
    <div>
      {/* Validate modal */}
      {validateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setValidateModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[540px] shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-1">Valider le paiement</h3>
            <p className="text-sm text-storm mb-1">
              {rfLabel(validateModal.type_rf)} — <span className="font-mono font-bold">{formatDA(validateModal.montant)}</span> — {validateModal.mode}
            </p>
            {validateModal.reference && <p className="text-xs text-storm mb-4">Ref: {validateModal.reference}</p>}

            <div className="bg-[#EDE7F6] border border-iris rounded-lg p-3 mb-5 text-xs text-storm">
              <strong>Maker/Checker :</strong> Scannez la preuve du paiement (cheque, bordereau, recu).
              L'IA verifiera la correspondance avec le paiement enregistre.
            </div>

            {/* Step 1: Upload */}
            {valStep === 'upload' && (
              <div
                onDragOver={e => e.preventDefault()}
                onDrop={handleProofDrop}
                className="border-2 border-dashed border-iris rounded-lg p-8 text-center cursor-pointer hover:bg-[rgba(108,92,231,0.03)] transition"
              >
                <div className="text-4xl mb-3">&#128269;</div>
                <p className="text-sm font-medium mb-1">Scanner la preuve de paiement</p>
                <p className="text-xs text-storm mb-3">
                  {validateModal.mode === 'CHEQUE' ? 'Photo ou scan du cheque encaisse' :
                   validateModal.mode === 'VIREMENT' ? 'Avis de virement / bordereau bancaire' :
                   'Recu ou justificatif du paiement'}
                </p>
                <label className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium cursor-pointer hover:bg-rose-800">
                  Choisir un fichier
                  <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={handleProofUpload} />
                </label>
                <p className="text-xs text-silver mt-3">JPG, PNG, WEBP, PDF — Max 10 Mo</p>
              </div>
            )}

            {/* Step 2: Analyzing */}
            {valStep === 'analyzing' && (
              <div className="p-8 text-center">
                <div className="w-10 h-10 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm font-medium">Analyse de la preuve en cours...</p>
                <p className="text-xs text-storm mt-1">Verification du montant, de la reference et de la banque</p>
              </div>
            )}

            {/* Step 3: Confirm */}
            {valStep === 'confirm' && (
              <div className="space-y-4">
                {/* AI confidence */}
                {valAiData?.confidence > 0 && (
                  <div className={`flex items-center gap-2 p-3 rounded-lg text-xs ${
                    valAiData.confidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] text-mint border border-mint' :
                    valAiData.confidence >= 50 ? 'bg-[#FFF8E1] text-honey border border-honey' :
                    'bg-[rgba(255,107,107,0.08)] text-coral border border-coral'
                  }`}>
                    <span className="font-bold">{valAiData.confidence}%</span>
                    <span>
                      {valAiData.confidence >= 80 ? 'Correspondance fiable avec le paiement' :
                       valAiData.confidence >= 50 ? 'Correspondance partielle — verifiez les details' :
                       'Correspondance faible — verifiez attentivement'}
                    </span>
                  </div>
                )}

                {valAiData?.scan_filename && (
                  <div className="flex items-center gap-2 p-2 bg-[#FAFAFA] rounded-lg text-xs">
                    <span className="text-mint">&#10003;</span>
                    <span className="font-medium">{valAiData.scan_filename}</span>
                    <span className="text-storm">— preuve enregistree</span>
                  </div>
                )}

                {valAiError && (
                  <div className="p-2 bg-[rgba(255,107,107,0.08)] rounded-lg text-xs text-coral">{valAiError}</div>
                )}

                {/* Amount mismatch */}
                {amountMismatch && valAiData?.amount && (
                  <div className="p-3 bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg text-xs text-coral">
                    <strong>Ecart de montant :</strong> La preuve indique {formatDA(valAiData.amount)} DA
                    mais le paiement est de {formatDA(validateModal.montant)} DA.
                  </div>
                )}

                {/* Extracted vs expected comparison */}
                <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm space-y-2">
                  <p className="font-semibold text-xs text-storm mb-2">Comparaison paiement / preuve :</p>
                  <div className="flex justify-between">
                    <span className="text-storm">Montant enregistre</span>
                    <span className="font-mono font-bold">{formatDA(validateModal.montant)}</span>
                  </div>
                  {valAiData?.amount && (
                    <div className="flex justify-between">
                      <span className="text-storm">Montant sur preuve</span>
                      <span className={`font-mono font-bold ${amountMismatch ? 'text-coral' : 'text-mint'}`}>
                        {formatDA(valAiData.amount)}
                        {!amountMismatch && ' ✓'}
                      </span>
                    </div>
                  )}
                  {valAiData?.cheque_number && (
                    <div className="flex justify-between">
                      <span className="text-storm">N cheque (preuve)</span>
                      <span className="font-mono">{valAiData.cheque_number}</span>
                    </div>
                  )}
                  {validateModal.reference && (
                    <div className="flex justify-between">
                      <span className="text-storm">Ref enregistree</span>
                      <span className="font-mono">{validateModal.reference}</span>
                    </div>
                  )}
                  {valAiData?.bank_name && (
                    <div className="flex justify-between">
                      <span className="text-storm">Banque (preuve)</span>
                      <span>{valAiData.bank_name}</span>
                    </div>
                  )}
                  {valAiData?.emitter && (
                    <div className="flex justify-between">
                      <span className="text-storm">Emetteur (preuve)</span>
                      <span>{valAiData.emitter}</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-3 mt-2">
                  <button onClick={() => setValidateModal(null)}
                    className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">
                    Annuler
                  </button>
                  <button onClick={() => submitReject('Preuve non conforme')}
                    disabled={valSubmitting}
                    className="py-2.5 px-4 border border-coral text-coral rounded-button text-sm font-medium hover:bg-[rgba(255,107,107,0.05)] disabled:opacity-50">
                    Rejeter
                  </button>
                  <button onClick={submitValidation}
                    disabled={valSubmitting || (amountMismatch && (valAiData?.confidence || 0) < 50)}
                    className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                    {valSubmitting ? 'Validation...' : 'Valider le paiement'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Payments table */}
      <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-mist">
          <h3 className="font-semibold">Paiements ({dossier.payments?.length || 0})</h3>
          <Link to={`/adv/dossiers/${id}/payment`} className="text-sm text-iris font-medium hover:underline">+ Enregistrer paiement</Link>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-4 text-left text-storm">Date</th>
            <th className="py-2 px-4 text-left text-storm">RF</th>
            <th className="py-2 px-4 text-left text-storm">Mode</th>
            <th className="py-2 px-4 text-left text-storm">Reference</th>
            <th className="py-2 px-4 text-right text-storm">Montant</th>
            <th className="py-2 px-4 text-left text-storm">Statut</th>
            <th className="py-2 px-4 text-left text-storm">Action</th>
          </tr></thead>
          <tbody>
            {(dossier.payments || []).length === 0 ? (
              <tr><td colSpan={7} className="py-6 text-center text-storm">Aucun paiement enregistre</td></tr>
            ) : (dossier.payments || []).map((p: any, i: number) => (
              <tr key={i} className="border-b border-mist hover:bg-[#FAFAFA]">
                <td className="py-2 px-4 font-mono text-xs">{formatDate(p.date)}</td>
                <td className="py-2 px-4"><Badge variant={p.type_rf === 'RF2' ? 'warning' : 'info'}>{rfLabel(p.type_rf)}</Badge></td>
                <td className="py-2 px-4 text-xs">{p.mode}</td>
                <td className="py-2 px-4 text-xs font-mono">{p.reference || '-'}</td>
                <td className="py-2 px-4 text-right font-mono font-bold">{formatDA(p.montant)}</td>
                <td className="py-2 px-4"><Badge variant={p.status === 'ENCAISSE' ? 'success' : p.status === 'REJETE' ? 'error' : 'warning'}>{p.status}</Badge></td>
                <td className="py-2 px-4">
                  {p.status === 'EN_ATTENTE' && (
                    <button onClick={() => openValidateModal(p)}
                      className="text-xs text-mint font-medium hover:underline">
                      Valider
                    </button>
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


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 2: Echeancier
// ═══════════════════════════════════════════════════════════════════════════════

function TabEcheancier({ dossier, id }: { dossier: any; id: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [dateLiv, setDateLiv] = useState('2028-01-01');
  // Payment modal state
  const [payModal, setPayModal] = useState<any>(null);
  const [payStep, setPayStep] = useState<'upload' | 'analyzing' | 'confirm'>('upload');
  const [payRef, setPayRef] = useState('');
  const [payBanque, setPayBanque] = useState('');
  const [payMontantExtracted, setPayMontantExtracted] = useState('');
  const [payEmitter, setPayEmitter] = useState('');
  const [payDate, setPayDate] = useState('');
  const [payConfidence, setPayConfidence] = useState(0);
  const [payScanFile, setPayScanFile] = useState('');
  const [payAiError, setPayAiError] = useState('');
  const [paySubmitting, setPaySubmitting] = useState(false);
  const [amountMismatch, setAmountMismatch] = useState(false);

  const reload = () => {
    api.get(`/adv/dossiers/${id}/echeancier`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { reload(); }, [id]);

  const generate = async () => {
    setGenerating(true);
    try {
      await api.post(`/adv/dossiers/${id}/echeancier`, {
        date_engagement: new Date().toISOString().split('T')[0],
        date_livraison: dateLiv,
        frequence: 'MENSUEL',
      });
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur generation');
    } finally {
      setGenerating(false);
    }
  };

  const openPayModal = (echeance: any) => {
    setPayModal(echeance);
    setPayStep('upload');
    setPayRef('');
    setPayBanque('');
    setPayMontantExtracted('');
    setPayEmitter('');
    setPayDate('');
    setPayConfidence(0);
    setPayScanFile('');
    setPayAiError('');
    setAmountMismatch(false);
  };

  const handleScanUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPayStep('analyzing');
    setPayAiError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/adv/payments/analyze-cheque', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const d = res.data.data;
      setPayRef(d.cheque_number || '');
      setPayBanque(d.bank_name || '');
      setPayMontantExtracted(d.amount ? String(d.amount) : '');
      setPayEmitter(d.emitter || '');
      setPayDate(d.date || '');
      setPayConfidence(d.confidence || 0);
      setPayScanFile(d.scan_filename || file.name);
      if (d.error) {
        setPayAiError(d.error);
      }
      // Check amount mismatch
      if (d.amount && payModal) {
        const expected = parseFloat(payModal.montant);
        const extracted = parseFloat(d.amount);
        setAmountMismatch(Math.abs(expected - extracted) > 1);
      }
      setPayStep('confirm');
    } catch (err: any) {
      setPayAiError(err.response?.data?.detail || 'Erreur analyse');
      setPayStep('confirm');
    }
  };

  const handleScanDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      // Create a synthetic event
      const input = document.createElement('input');
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      handleScanUpload({ target: input } as any);
    }
  };

  const submitPayment = async () => {
    if (!payModal) return;
    setPaySubmitting(true);
    try {
      await api.post(`/adv/dossiers/${id}/echeancier/${payModal.id}/pay`, {
        mode_reglement: 'CHEQUE',
        reference: payRef,
        banque: payBanque,
        scan_file: payScanFile,
      });
      setPayModal(null);
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur paiement');
    } finally {
      setPaySubmitting(false);
    }
  };

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;

  if (!data) {
    return (
      <div className="bg-white rounded-card border border-mist p-6">
        <h3 className="font-semibold mb-4">Generer un echeancier</h3>
        {dossier.type !== 'FONDS_PROPRES' && dossier.type !== 'MIXTE' ? (
          <p className="text-sm text-storm">Echeancier disponible uniquement pour les dossiers fonds propres.</p>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-sm text-storm block mb-1">Date livraison prevue</label>
              <input type="date" value={dateLiv} onChange={e => setDateLiv(e.target.value)}
                className="border border-mist rounded-input px-3 py-2 text-sm" />
            </div>
            <button onClick={generate} disabled={generating}
              className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist">
              {generating ? 'Generation...' : 'Generer echeancier'}
            </button>
          </div>
        )}
      </div>
    );
  }

  const paidCount = data.echeances.filter((e: any) => e.status === 'PAYEE').length;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-card border border-mist p-3"><p className="text-xs text-storm">Echeances</p><p className="text-lg font-bold">{data.nb_echeances}</p></div>
        <div className="bg-white rounded-card border border-mist p-3"><p className="text-xs text-storm">Montant / ech.</p><p className="text-lg font-bold font-mono">{formatDA(data.montant_echeance)}</p></div>
        <div className="bg-white rounded-card border border-mist p-3"><p className="text-xs text-storm">Payees</p><p className="text-lg font-bold text-mint">{paidCount} / {data.nb_echeances}</p></div>
        <div className="bg-white rounded-card border border-mist p-3"><p className="text-xs text-storm">Penalites</p><p className="text-lg font-bold text-coral">{formatDA(data.total_penalites)}</p></div>
      </div>

      {/* Payment modal */}
      {payModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setPayModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[540px] shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-1">Payer echeance #{payModal.numero}</h3>
            <p className="text-sm text-storm mb-4">
              Montant attendu : <span className="font-mono font-bold">{formatDA(payModal.montant)}</span> — Echeance du {payModal.date}
            </p>

            <div className="bg-[#FFF8E1] border border-honey rounded-lg p-3 mb-5 text-xs text-storm">
              FP-003 : Cheque uniquement. Scannez le cheque — l'IA extraira automatiquement les informations.
            </div>

            {/* Step 1: Upload scan */}
            {payStep === 'upload' && (
              <div
                onDragOver={e => e.preventDefault()}
                onDrop={handleScanDrop}
                className="border-2 border-dashed border-iris rounded-lg p-8 text-center cursor-pointer hover:bg-[rgba(108,92,231,0.03)] transition"
              >
                <div className="text-4xl mb-3">&#128247;</div>
                <p className="text-sm font-medium mb-1">Scanner le cheque du client</p>
                <p className="text-xs text-storm mb-3">Glissez l'image ici ou cliquez pour parcourir</p>
                <label className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium cursor-pointer hover:bg-rose-800">
                  Choisir un fichier
                  <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={handleScanUpload} />
                </label>
                <p className="text-xs text-silver mt-3">JPG, PNG, WEBP, PDF — Max 10 Mo</p>
                <button onClick={() => { setPayStep('confirm'); setPayAiError('Saisie manuelle'); }}
                  className="text-xs text-storm hover:text-iris mt-4 underline">
                  Saisie manuelle sans scan
                </button>
              </div>
            )}

            {/* Step 2: Analyzing */}
            {payStep === 'analyzing' && (
              <div className="p-8 text-center">
                <div className="w-10 h-10 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm font-medium">Analyse du cheque en cours...</p>
                <p className="text-xs text-storm mt-1">L'IA extrait le numero, la banque et le montant</p>
              </div>
            )}

            {/* Step 3: Confirm extracted data */}
            {payStep === 'confirm' && (
              <div className="space-y-4">
                {/* AI confidence indicator */}
                {payConfidence > 0 && (
                  <div className={`flex items-center gap-2 p-3 rounded-lg text-xs ${
                    payConfidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] text-mint border border-mint' :
                    payConfidence >= 50 ? 'bg-[#FFF8E1] text-honey border border-honey' :
                    'bg-[rgba(255,107,107,0.08)] text-coral border border-coral'
                  }`}>
                    <span className="font-bold">{payConfidence}%</span>
                    <span>
                      {payConfidence >= 80 ? 'Extraction fiable — verifiez et confirmez' :
                       payConfidence >= 50 ? 'Extraction partielle — completez les champs manquants' :
                       'Extraction faible — verifiez tous les champs'}
                    </span>
                  </div>
                )}

                {payScanFile && (
                  <div className="flex items-center gap-2 p-2 bg-[#FAFAFA] rounded-lg text-xs">
                    <span className="text-mint">&#10003;</span>
                    <span className="font-medium">{payScanFile}</span>
                    <span className="text-storm">— scan enregistre</span>
                  </div>
                )}

                {payAiError && (
                  <div className="p-2 bg-[rgba(255,107,107,0.08)] rounded-lg text-xs text-coral">{payAiError}</div>
                )}

                {/* Amount mismatch warning */}
                {amountMismatch && payMontantExtracted && (
                  <div className="p-3 bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg text-xs text-coral">
                    <strong>Ecart de montant detecte :</strong> le cheque indique {formatDA(payMontantExtracted)} mais l'echeance attend {formatDA(payModal.montant)}.
                    Verifiez que le bon cheque a ete scanne.
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-storm block mb-1">Mode de reglement</label>
                  <div className="border border-mist rounded-input px-4 py-2.5 text-sm bg-[#FAFAFA] text-storm">CHEQUE (obligatoire — FP-003)</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-storm block mb-1">Numero de cheque <span className="text-coral">*</span></label>
                  <input type="text" value={payRef} onChange={e => setPayRef(e.target.value)} autoFocus
                    className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                    placeholder="CHQ-XXXX-XXXX" />
                </div>
                <div>
                  <label className="text-sm font-medium text-storm block mb-1">Banque emettrice</label>
                  <input type="text" value={payBanque} onChange={e => setPayBanque(e.target.value)}
                    className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                    placeholder="BNA, CPA, BDL..." />
                </div>
                {payEmitter && (
                  <div>
                    <label className="text-sm font-medium text-storm block mb-1">Emetteur (extrait)</label>
                    <div className="border border-mist rounded-input px-4 py-2.5 text-sm bg-[#FAFAFA]">{payEmitter}</div>
                  </div>
                )}
                {payMontantExtracted && (
                  <div>
                    <label className="text-sm font-medium text-storm block mb-1">Montant extrait du cheque</label>
                    <div className={`border rounded-input px-4 py-2.5 text-sm font-mono font-bold ${amountMismatch ? 'border-coral bg-[rgba(255,107,107,0.05)] text-coral' : 'border-mist bg-[#FAFAFA]'}`}>
                      {formatDA(payMontantExtracted)} {amountMismatch && `(attendu: ${formatDA(payModal.montant)})`}
                    </div>
                  </div>
                )}

                <div className="flex gap-3 mt-2">
                  <button onClick={() => setPayModal(null)}
                    className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">
                    Annuler
                  </button>
                  <button onClick={submitPayment}
                    disabled={!payRef.trim() || paySubmitting}
                    className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                    {paySubmitting ? 'Enregistrement...' : `Confirmer — ${formatDA(payModal.montant)}`}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-3 text-left text-storm">#</th>
            <th className="py-2 px-3 text-left text-storm">Date</th>
            <th className="py-2 px-3 text-right text-storm">Montant</th>
            <th className="py-2 px-3 text-left text-storm">Statut</th>
            <th className="py-2 px-3 text-right text-storm">Retard</th>
            <th className="py-2 px-3 text-right text-storm">Penalite</th>
            <th className="py-2 px-3 text-left text-storm">Action</th>
          </tr></thead>
          <tbody>
            {data.echeances.map((e: any) => (
              <tr key={e.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                <td className="py-2 px-3 font-mono text-xs">{e.numero}</td>
                <td className="py-2 px-3 text-xs">{e.date}</td>
                <td className="py-2 px-3 text-right font-mono font-bold">{formatDA(e.montant)}</td>
                <td className="py-2 px-3">
                  <Badge variant={e.status === 'PAYEE' ? 'success' : e.status === 'EN_RETARD' ? 'error' : e.status === 'DUE' ? 'warning' : 'neutral'}>
                    {e.status}
                  </Badge>
                </td>
                <td className="py-2 px-3 text-right text-xs">{e.jours_retard > 0 ? `${e.jours_retard}j` : '-'}</td>
                <td className="py-2 px-3 text-right font-mono text-xs text-coral">{parseFloat(e.penalite) > 0 ? formatDA(e.penalite) : '-'}</td>
                <td className="py-2 px-3">
                  {(e.status === 'DUE' || e.status === 'EN_RETARD' || e.status === 'A_VENIR') && (
                    <button onClick={() => openPayModal(e)}
                      className="text-xs text-mint font-medium hover:underline">Payer</button>
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


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 3: Documents
// ═══════════════════════════════════════════════════════════════════════════════

function TabDocuments({ id }: { id: string }) {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDocs = () => {
    api.get(`/adv/dossiers/${id}/documents`).then(r => { setDocs(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { loadDocs(); }, [id]);

  const markReceived = async (docId: string) => {
    try {
      await api.post(`/adv/dossiers/${id}/documents/${docId}/receive`, { document_url: 'uploaded' });
      loadDocs();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;
  if (docs.length === 0) return <div className="bg-white rounded-card border border-mist p-6"><p className="text-sm text-storm">Aucun document requis. La checklist sera generee a l'engagement.</p></div>;

  const received = docs.filter(d => d.received).length;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-card border border-mist p-3 flex items-center gap-4">
        <div className="bg-mist rounded-full h-3 flex-1"><div className="bg-iris h-full rounded-full" style={{ width: `${(received / docs.length) * 100}%` }} /></div>
        <span className="text-sm font-medium">{received}/{docs.length} recus</span>
      </div>
      <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-4 text-left text-storm">Document</th>
            <th className="py-2 px-4 text-left text-storm">Source</th>
            <th className="py-2 px-4 text-left text-storm">Statut</th>
            <th className="py-2 px-4 text-left text-storm">Alerte</th>
            <th className="py-2 px-4 text-left text-storm">Action</th>
          </tr></thead>
          <tbody>
            {docs.map((d: any) => (
              <tr key={d.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                <td className="py-2 px-4 font-medium">{d.label}</td>
                <td className="py-2 px-4 text-xs"><Badge variant="neutral">{d.source}</Badge></td>
                <td className="py-2 px-4">
                  {d.received
                    ? <Badge variant="success">RECU</Badge>
                    : <Badge variant="warning">MANQUANT ({d.days_waiting}j)</Badge>}
                </td>
                <td className="py-2 px-4">
                  {d.alert_level && <Badge variant={d.alert_level === 'BLOQUANT' ? 'error' : d.alert_level === 'ALERTE' ? 'warning' : 'info'}>{d.alert_level}</Badge>}
                </td>
                <td className="py-2 px-4">
                  {!d.received && (
                    <button onClick={() => markReceived(d.id)} className="text-xs text-mint font-medium hover:underline">Marquer recu</button>
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


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 4: Deblocages (Credit tiers)
// ═══════════════════════════════════════════════════════════════════════════════

function TabDeblocages({ id, dossier }: { id: string; dossier: any }) {
  const [tiers, setTiers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  // Expert report modal
  const [expertModal, setExpertModal] = useState<any>(null);  // tier object or null
  const [expertName, setExpertName] = useState('');
  const [expertDate, setExpertDate] = useState(new Date().toISOString().split('T')[0]);
  const [expertPct, setExpertPct] = useState('');
  const [expertObs, setExpertObs] = useState('');
  const [expertSubmitting, setExpertSubmitting] = useState(false);
  // Validate report modal
  const [validateReportModal, setValidateReportModal] = useState<any>(null);
  // PV release 5% modal
  const [pvModal, setPvModal] = useState(false);
  const [pvFile, setPvFile] = useState<string | null>(null);
  const [pvSubmitting, setPvSubmitting] = useState(false);

  const loadTiers = () => {
    api.get(`/adv/dossiers/${id}/credit-tiers`).then(r => { setTiers(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { loadTiers(); }, [id]);

  const initTiers = async () => {
    try {
      await api.post(`/adv/dossiers/${id}/credit-tiers/init`);
      loadTiers();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  // ── Proof modal for VSP / disburse / 5% ──────────────────────────────
  const [proofModal, setProofModal] = useState<{ action: string; tier: any } | null>(null);
  const [proofStep, setProofStep] = useState<'upload' | 'analyzing' | 'confirm'>('upload');
  const [proofAiData, setProofAiData] = useState<any>(null);
  const [proofAiError, setProofAiError] = useState('');
  const [proofSubmitting, setProofSubmitting] = useState(false);
  const [proofAmountMismatch, setProofAmountMismatch] = useState(false);

  const openProofModal = (action: string, tier: any) => {
    setProofModal({ action, tier });
    setProofStep('upload');
    setProofAiData(null);
    setProofAiError('');
    setProofAmountMismatch(false);
  };

  const handleProofScan = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !proofModal) return;
    setProofStep('analyzing');
    setProofAiError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/adv/payments/analyze-cheque', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const d = res.data.data;
      setProofAiData(d);
      if (d.error) setProofAiError(d.error);
      if (d.amount && proofModal.tier) {
        const expected = parseFloat(proofModal.tier.montant);
        setProofAmountMismatch(Math.abs(expected - parseFloat(d.amount)) > 1);
      }
      setProofStep('confirm');
    } catch (err: any) {
      setProofAiError(err.response?.data?.detail || 'Erreur analyse');
      setProofStep('confirm');
    }
  };

  const confirmProofAction = async () => {
    if (!proofModal) return;
    setProofSubmitting(true);
    try {
      if (proofModal.action === 'vsp') {
        await api.post(`/adv/dossiers/${id}/escrow/vsp-20`, {
          scan_path: proofAiData?.scan_path,
        });
      } else if (proofModal.action === 'disburse') {
        await api.post(`/adv/dossiers/${id}/credit-tiers/${proofModal.tier.tier_number}/disburse`, {
          scan_path: proofAiData?.scan_path,
        });
      }
      setProofModal(null);
      loadTiers();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    } finally {
      setProofSubmitting(false);
    }
  };

  const proofLabels: Record<string, { title: string; docType: string; rule: string }> = {
    vsp: {
      title: 'VSP 20% — Transit notaire',
      docType: 'Avis de deblocage bancaire / cheque notaire',
      rule: 'CRE-004 : Le palier 20% doit transiter par le compte sequestre du notaire.',
    },
    disburse: {
      title: 'Deblocage palier',
      docType: 'Avis de virement bancaire / bordereau de deblocage',
      rule: 'CRE-005 : Preuve du virement bancaire requise pour enregistrer le deblocage.',
    },
  };

  const submitExpertReport = async () => {
    if (!expertModal || !expertName.trim()) return;
    setExpertSubmitting(true);
    try {
      await api.post(`/adv/dossiers/${id}/expert-report`, {
        tier_percentage: parseFloat(expertModal.percentage),
        expert_name: expertName,
        report_date: expertDate,
        completion_pct: expertPct ? parseFloat(expertPct) : null,
        observations: expertObs || null,
        conformity: true,
      });
      setExpertModal(null);
      loadTiers();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setExpertSubmitting(false); }
  };

  const validateReport = async (tier: any) => {
    if (!tier.expert_report) return;
    try {
      await api.post(`/adv/dossiers/${id}/expert-report/${tier.expert_report.id}/validate`);
      loadTiers();
      setValidateReportModal(null);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  // PV 5%: also uses AI scan
  const [pvAiData, setPvAiData] = useState<any>(null);
  const [pvStep, setPvStep] = useState<'upload' | 'analyzing' | 'confirm'>('upload');
  const [pvAiError, setPvAiError] = useState('');

  const openPvModal = () => {
    setPvModal(true);
    setPvFile(null);
    setPvAiData(null);
    setPvStep('upload');
    setPvAiError('');
  };

  const handlePvScan = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPvStep('analyzing');
    setPvAiError('');
    setPvFile(file.name);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/adv/payments/analyze-cheque', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPvAiData(res.data.data);
      if (res.data.data?.error) setPvAiError(res.data.data.error);
      setPvStep('confirm');
    } catch (err: any) {
      setPvAiError(err.response?.data?.detail || 'Analyse AI indisponible');
      setPvStep('confirm');
    }
  };

  const release5pct = async () => {
    setPvSubmitting(true);
    try {
      await api.post(`/adv/dossiers/${id}/escrow/release-5`, {
        pv_url: pvAiData?.scan_path || pvFile || 'uploaded',
      });
      setPvModal(false);
      loadTiers();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setPvSubmitting(false); }
  };

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;

  if (tiers.length === 0) {
    return (
      <div className="bg-white rounded-card border border-mist p-6">
        <p className="text-sm text-storm mb-3">Les paliers de deblocage n'ont pas encore ete initialises.</p>
        <button onClick={initTiers} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">
          Initialiser les 5 paliers
        </button>
      </div>
    );
  }

  const statusColor = (s: string) => s === 'DEBLOQUE' ? 'success' : s === 'EXPERT_VALIDE' ? 'info' : s === 'EXPERT_RECU' ? 'warning' : 'neutral';
  const totalDebloque = tiers.filter(t => t.status === 'DEBLOQUE').length;

  return (
    <div className="space-y-4">
      {/* Progress */}
      <div className="bg-white rounded-card border border-mist p-3 flex items-center gap-4">
        <div className="bg-mist rounded-full h-3 flex-1"><div className="bg-mint h-full rounded-full" style={{ width: `${(totalDebloque / 5) * 100}%` }} /></div>
        <span className="text-sm font-medium">{totalDebloque}/5 debloques</span>
      </div>

      {/* ── Expert report upload modal ─────────────────────────────────── */}
      {expertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setExpertModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[480px] shadow-xl">
            <h3 className="text-lg font-bold mb-1">Rapport expert — Palier {expertModal.percentage}%</h3>
            <p className="text-sm text-storm mb-5">
              Montant du palier : <span className="font-mono font-bold">{formatDA(expertModal.montant)}</span>
            </p>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Nom de l'expert <span className="text-coral">*</span></label>
                <input type="text" value={expertName} onChange={e => setExpertName(e.target.value)} autoFocus
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                  placeholder="Expert Bouzid, Expert Mansouri..." />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Date du rapport</label>
                <input type="date" value={expertDate} onChange={e => setExpertDate(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Avancement constate (%)</label>
                <input type="number" value={expertPct} onChange={e => setExpertPct(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                  placeholder="85" min="0" max="100" />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Observations</label>
                <textarea value={expertObs} onChange={e => setExpertObs(e.target.value)} rows={3}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none resize-none"
                  placeholder="Conformite des travaux, remarques..." />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setExpertModal(null)}
                className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">Annuler</button>
              <button onClick={submitExpertReport} disabled={!expertName.trim() || expertSubmitting}
                className="flex-1 py-2.5 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
                {expertSubmitting ? 'Envoi...' : 'Enregistrer rapport'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Validate report confirmation modal ─────────────────────────── */}
      {validateReportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setValidateReportModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[480px] shadow-xl">
            <h3 className="text-lg font-bold mb-3">Valider le rapport expert</h3>
            <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm space-y-2 mb-5">
              <div className="flex justify-between"><span className="text-storm">Palier</span><span className="font-bold">{validateReportModal.percentage}% — {formatDA(validateReportModal.montant)}</span></div>
              <div className="flex justify-between"><span className="text-storm">Expert</span><span>{validateReportModal.expert_report?.expert}</span></div>
              <div className="flex justify-between"><span className="text-storm">Avancement</span><span className="font-mono">{validateReportModal.expert_report?.completion_pct}%</span></div>
              <div className="flex justify-between"><span className="text-storm">Date</span><span>{validateReportModal.expert_report?.date}</span></div>
            </div>
            <div className="bg-[#FFF8E1] border border-honey rounded-lg p-3 mb-5 text-xs text-storm">
              <strong>CRE-005 :</strong> La validation du rapport expert debloque la generation de la demande de deblocage vers la banque.
              Cette action est irreversible.
            </div>
            <div className="flex gap-3">
              <button onClick={() => setValidateReportModal(null)}
                className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">Annuler</button>
              <button onClick={() => validateReport(validateReportModal)}
                className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884]">
                Valider le rapport
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Proof modal for VSP 20% / Disburse 15-35-25% ────────────────── */}
      {proofModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setProofModal(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[540px] shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-1">{proofLabels[proofModal.action]?.title || 'Deblocage'}</h3>
            <p className="text-sm text-storm mb-4">
              Palier {proofModal.tier.percentage}% — <span className="font-mono font-bold">{formatDA(proofModal.tier.montant)}</span>
            </p>
            <div className="bg-[#EDE7F6] border border-iris rounded-lg p-3 mb-5 text-xs text-storm">
              {proofLabels[proofModal.action]?.rule}
            </div>

            {proofStep === 'upload' && (
              <div className="border-2 border-dashed border-iris rounded-lg p-8 text-center cursor-pointer hover:bg-[rgba(108,92,231,0.03)] transition">
                <div className="text-4xl mb-3">&#128269;</div>
                <p className="text-sm font-medium mb-1">Scanner la preuve bancaire</p>
                <p className="text-xs text-storm mb-3">{proofLabels[proofModal.action]?.docType}</p>
                <label className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium cursor-pointer hover:bg-rose-800">
                  Choisir un fichier
                  <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={handleProofScan} />
                </label>
                <p className="text-xs text-silver mt-3">JPG, PNG, PDF — Max 10 Mo</p>
                <button onClick={() => { setProofAiData({ scan_filename: 'saisie_manuelle' }); setProofAiError('Saisie manuelle'); setProofStep('confirm'); }}
                  className="text-xs text-storm hover:text-iris mt-4 underline">Continuer sans scan</button>
              </div>
            )}

            {proofStep === 'analyzing' && (
              <div className="p-8 text-center">
                <div className="w-10 h-10 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm font-medium">Analyse du document bancaire...</p>
                <p className="text-xs text-storm mt-1">Verification du montant et de la reference</p>
              </div>
            )}

            {proofStep === 'confirm' && (
              <div className="space-y-4">
                {proofAiData?.confidence > 0 && (
                  <div className={`flex items-center gap-2 p-3 rounded-lg text-xs ${
                    proofAiData.confidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] text-mint border border-mint' :
                    proofAiData.confidence >= 50 ? 'bg-[#FFF8E1] text-honey border border-honey' :
                    'bg-[rgba(255,107,107,0.08)] text-coral border border-coral'
                  }`}>
                    <span className="font-bold">{proofAiData.confidence}%</span>
                    <span>{proofAiData.confidence >= 80 ? 'Document conforme' : proofAiData.confidence >= 50 ? 'Correspondance partielle' : 'Verifiez attentivement'}</span>
                  </div>
                )}
                {proofAiData?.scan_filename && (
                  <div className="flex items-center gap-2 p-2 bg-[#FAFAFA] rounded-lg text-xs">
                    <span className="text-mint">&#10003;</span>
                    <span className="font-medium">{proofAiData.scan_filename}</span>
                  </div>
                )}
                {proofAiError && <div className="p-2 bg-[rgba(255,107,107,0.08)] rounded-lg text-xs text-coral">{proofAiError}</div>}
                {proofAmountMismatch && proofAiData?.amount && (
                  <div className="p-3 bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg text-xs text-coral">
                    <strong>Ecart :</strong> Document indique {formatDA(proofAiData.amount)} — palier attend {formatDA(proofModal.tier.montant)}
                  </div>
                )}
                <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm space-y-2">
                  <div className="flex justify-between"><span className="text-storm">Montant palier</span><span className="font-mono font-bold">{formatDA(proofModal.tier.montant)}</span></div>
                  {proofAiData?.amount && <div className="flex justify-between"><span className="text-storm">Montant document</span><span className={`font-mono font-bold ${proofAmountMismatch ? 'text-coral' : 'text-mint'}`}>{formatDA(proofAiData.amount)} {!proofAmountMismatch && '✓'}</span></div>}
                  {proofAiData?.bank_name && <div className="flex justify-between"><span className="text-storm">Banque</span><span>{proofAiData.bank_name}</span></div>}
                  {proofAiData?.cheque_number && <div className="flex justify-between"><span className="text-storm">Reference</span><span className="font-mono">{proofAiData.cheque_number}</span></div>}
                  {proofAiData?.beneficiary && <div className="flex justify-between"><span className="text-storm">Beneficiaire</span><span>{proofAiData.beneficiary}</span></div>}
                </div>
                <div className="flex gap-3 mt-2">
                  <button onClick={() => setProofModal(null)} className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">Annuler</button>
                  <button onClick={confirmProofAction} disabled={proofSubmitting}
                    className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                    {proofSubmitting ? 'Traitement...' : 'Confirmer le deblocage'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── PV remise des cles modal (5%) — with AI scan ───────────────── */}
      {pvModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setPvModal(false)} />
          <div className="relative bg-white rounded-2xl p-8 w-[540px] shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-3">Liberation du 5% — Remise des cles</h3>
            <div className="bg-[#EDE7F6] border border-iris rounded-lg p-3 mb-5 text-xs text-storm">
              <strong>CRE-006 :</strong> Le PV de remise des cles signe par le client et l'entreprise est
              <strong> obligatoire</strong>. L'IA verifiera les signatures et le contenu du PV.
            </div>

            {pvStep === 'upload' && (
              <div className="border-2 border-dashed border-iris rounded-lg p-8 text-center cursor-pointer hover:bg-[rgba(108,92,231,0.03)] transition">
                <div className="text-4xl mb-3">&#128273;</div>
                <p className="text-sm font-medium mb-1">Scanner le PV de remise des cles</p>
                <p className="text-xs text-storm mb-3">Document signe par le client et le representant de l'entreprise</p>
                <label className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium cursor-pointer hover:bg-rose-800">
                  Choisir un fichier
                  <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={handlePvScan} />
                </label>
                <p className="text-xs text-silver mt-3">JPG, PNG, PDF — Max 10 Mo</p>
              </div>
            )}

            {pvStep === 'analyzing' && (
              <div className="p-8 text-center">
                <div className="w-10 h-10 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm font-medium">Analyse du PV en cours...</p>
                <p className="text-xs text-storm mt-1">Verification des signatures et du contenu</p>
              </div>
            )}

            {pvStep === 'confirm' && (
              <div className="space-y-4">
                {pvAiData?.confidence > 0 && (
                  <div className={`flex items-center gap-2 p-3 rounded-lg text-xs ${
                    pvAiData.confidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] text-mint border border-mint' :
                    'bg-[#FFF8E1] text-honey border border-honey'
                  }`}>
                    <span className="font-bold">{pvAiData.confidence}%</span>
                    <span>{pvAiData.confidence >= 80 ? 'PV conforme' : 'Verifiez le document'}</span>
                  </div>
                )}
                {pvFile && (
                  <div className="flex items-center gap-2 p-2 bg-[#FAFAFA] rounded-lg text-xs">
                    <span className="text-mint">&#10003;</span>
                    <span className="font-medium">{pvFile}</span>
                    <span className="text-storm">— PV enregistre</span>
                  </div>
                )}
                {pvAiError && <div className="p-2 bg-[rgba(255,107,107,0.08)] rounded-lg text-xs text-coral">{pvAiError}</div>}
                {pvAiData?.beneficiary && (
                  <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm space-y-2">
                    {pvAiData.beneficiary && <div className="flex justify-between"><span className="text-storm">Beneficiaire</span><span>{pvAiData.beneficiary}</span></div>}
                    {pvAiData.emitter && <div className="flex justify-between"><span className="text-storm">Client</span><span>{pvAiData.emitter}</span></div>}
                    {pvAiData.date && <div className="flex justify-between"><span className="text-storm">Date</span><span>{pvAiData.date}</span></div>}
                  </div>
                )}
                <div className="flex gap-3 mt-2">
                  <button onClick={() => setPvModal(false)} className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">Annuler</button>
                  <button onClick={release5pct} disabled={!pvFile || pvSubmitting}
                    className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                    {pvSubmitting ? 'Liberation...' : 'Liberer 5% via notaire'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tier list */}
      <div className="space-y-3">
        {tiers.map((t: any) => {
          const needsReport = t.tier_number >= 1 && t.tier_number <= 3 && !t.expert_report && t.status === 'EN_ATTENTE';
          const needsValidation = t.expert_report?.status === 'RECU' && t.status === 'EXPERT_RECU';
          const readyToDisburse = t.tier_number >= 1 && t.tier_number <= 3 && t.status === 'EXPERT_VALIDE';
          const is5pct = t.tier_number === 4 && t.status !== 'DEBLOQUE';
          const isVsp = t.tier_number === 0 && t.status !== 'DEBLOQUE';

          return (
            <div key={t.id} className={`bg-white rounded-card border p-4 shadow-card ${t.status === 'DEBLOQUE' ? 'border-mint' : 'border-mist'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className={`text-xl font-bold ${t.status === 'DEBLOQUE' ? 'text-mint' : 'text-iris'}`}>{t.percentage}%</span>
                  <span className="text-sm font-medium">{t.label}</span>
                  <Badge variant="neutral">{t.routing === 'VIA_NOTAIRE' ? 'Via notaire' : 'Virement direct'}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-bold">{formatDA(t.montant)}</span>
                  <Badge variant={statusColor(t.status)}>{t.status}</Badge>
                </div>
              </div>

              {/* Expert report info */}
              {t.expert_report && (
                <div className={`text-xs mt-2 p-3 rounded-lg ${
                  t.expert_report.status === 'VALIDE' ? 'bg-[rgba(85,239,196,0.08)] border border-mint' :
                  'bg-[#FFF8E1] border border-honey'
                }`}>
                  <div className="flex items-center justify-between">
                    <span>
                      Rapport expert : <strong>{t.expert_report.expert}</strong> — {t.expert_report.completion_pct}% avancement
                    </span>
                    <Badge variant={t.expert_report.status === 'VALIDE' ? 'success' : 'warning'}>{t.expert_report.status}</Badge>
                  </div>
                  {t.expert_report.date && <p className="text-storm mt-1">Date : {t.expert_report.date}</p>}
                </div>
              )}

              {/* Wire order info */}
              {t.wire_order && (
                <div className="text-xs text-storm mt-1 p-2 bg-[#FAFAFA] rounded">
                  Ordre virement : {t.wire_order.status} {t.wire_order.signed ? `(signe ${t.wire_order.signed})` : ''}
                </div>
              )}

              {/* Actions — contextual per tier state */}
              {t.status !== 'DEBLOQUE' && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {/* Tier 0 (20%): VSP transit notaire — requires proof */}
                  {isVsp && (
                    <button onClick={() => openProofModal('vsp', t)}
                      className="px-3 py-1.5 bg-iris text-white rounded-button text-xs font-medium hover:bg-rose-800">
                      VSP 20% — Transit notaire
                    </button>
                  )}

                  {/* Tiers 1-3: Upload expert report if none exists */}
                  {needsReport && (
                    <button onClick={() => { setExpertModal(t); setExpertName(''); setExpertPct(''); setExpertObs(''); }}
                      className="px-3 py-1.5 bg-ocean text-white rounded-button text-xs font-medium hover:bg-[#0878C8]">
                      Enregistrer rapport expert
                    </button>
                  )}

                  {/* Tiers 1-3: Validate expert report if RECU */}
                  {needsValidation && (
                    <button onClick={() => setValidateReportModal(t)}
                      className="px-3 py-1.5 bg-honey text-white rounded-button text-xs font-medium hover:bg-[#D4A017]">
                      Valider rapport expert (CRE-005)
                    </button>
                  )}

                  {/* Tiers 1-3: Disburse if EXPERT_VALIDE — requires proof */}
                  {readyToDisburse && (
                    <button onClick={() => openProofModal('disburse', t)}
                      className="px-3 py-1.5 bg-mint text-white rounded-button text-xs font-medium hover:bg-[#00A884]">
                      Enregistrer deblocage
                    </button>
                  )}

                  {/* Tier 4 (5%): Release via notaire with PV scan */}
                  {is5pct && (
                    <button onClick={openPvModal}
                      className="px-3 py-1.5 bg-iris text-white rounded-button text-xs font-medium hover:bg-rose-800">
                      Liberer 5% — PV remise des cles
                    </button>
                  )}
                </div>
              )}

              {t.debloque_at && <p className="text-xs text-mint mt-2 font-medium">Debloque le {new Date(t.debloque_at).toLocaleDateString('fr-DZ')}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 5: Notaire (Escrow)
// ═══════════════════════════════════════════════════════════════════════════════

function TabNotaire({ id }: { id: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/adv/dossiers/${id}/escrow`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;
  if (!data || (!data.escrow && data.movements?.length === 0)) {
    return <div className="bg-white rounded-card border border-mist p-6"><p className="text-sm text-storm">Aucun compte sequestre actif pour ce dossier. Le sequestre sera cree lors du premier deblocage via notaire.</p></div>;
  }

  return (
    <div className="space-y-4">
      {/* Escrow account summary */}
      {data.escrow && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white rounded-card border border-mist p-3">
            <p className="text-xs text-storm">Solde transitoire</p>
            <p className={`text-lg font-bold font-mono ${parseFloat(data.escrow.solde) > 0 ? 'text-honey' : 'text-mint'}`}>
              {formatDA(data.escrow.solde)}
            </p>
          </div>
          <div className="bg-white rounded-card border border-mist p-3">
            <p className="text-xs text-storm">Reserve 5%</p>
            <p className="text-lg font-bold font-mono">{formatDA(data.escrow.reserve_5pct)}</p>
          </div>
          <div className="bg-white rounded-card border border-mist p-3">
            <p className="text-xs text-storm">Notaire</p>
            <p className="text-sm font-semibold">{data.escrow.notaire || 'Non renseigne'}</p>
          </div>
        </div>
      )}
      {/* Movement history */}
      <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
        <div className="p-4 border-b border-mist"><h3 className="font-semibold">Mouvements ({data.movements?.length || 0})</h3></div>
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-4 text-left text-storm">Date</th>
            <th className="py-2 px-4 text-left text-storm">Type</th>
            <th className="py-2 px-4 text-right text-storm">Montant</th>
            <th className="py-2 px-4 text-right text-storm">Solde apres</th>
            <th className="py-2 px-4 text-left text-storm">Motif</th>
            <th className="py-2 px-4 text-left text-storm">Source / Dest</th>
          </tr></thead>
          <tbody>
            {(data.movements || []).length === 0 ? (
              <tr><td colSpan={6} className="py-6 text-center text-storm">Aucun mouvement</td></tr>
            ) : data.movements.map((m: any) => (
              <tr key={m.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                <td className="py-2 px-4 text-xs font-mono">{new Date(m.date).toLocaleDateString('fr-DZ')}</td>
                <td className="py-2 px-4">
                  <Badge variant={m.type === 'CREDIT' ? 'success' : 'warning'}>{m.type}</Badge>
                </td>
                <td className="py-2 px-4 text-right font-mono font-bold">{formatDA(m.montant)}</td>
                <td className="py-2 px-4 text-right font-mono">{formatDA(m.balance_after)}</td>
                <td className="py-2 px-4 text-xs">{m.motif}</td>
                <td className="py-2 px-4 text-xs text-storm">{m.type === 'CREDIT' ? m.source : m.destination}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Tab 6: Historique (transitions audit trail)
// ═══════════════════════════════════════════════════════════════════════════════

function TabHistorique({ id }: { id: string }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/adv/dossiers/${id}/transitions`).then(r => { setLogs(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;
  if (logs.length === 0) return <div className="bg-white rounded-card border border-mist p-6"><p className="text-sm text-storm">Aucun evenement enregistre. L'historique commencera a se remplir lors des prochaines transitions.</p></div>;

  return (
    <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
      <div className="p-4 border-b border-mist"><h3 className="font-semibold">Historique des transitions ({logs.length})</h3></div>
      <div className="divide-y divide-mist">
        {logs.map((l: any) => (
          <div key={l.id} className="p-4 flex items-center gap-4">
            <div className="w-2 h-2 rounded-full bg-iris" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Badge variant="neutral">{l.from}</Badge>
                <span className="text-storm text-xs">&rarr;</span>
                <Badge variant="info">{l.to}</Badge>
              </div>
              {l.notes && <p className="text-xs text-storm mt-1">{l.notes}</p>}
            </div>
            <div className="text-right">
              <p className="text-xs text-storm">{new Date(l.date).toLocaleDateString('fr-DZ')} {new Date(l.date).toLocaleTimeString('fr-DZ', { hour: '2-digit', minute: '2-digit' })}</p>
              <p className="text-xs font-medium">{l.by}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
