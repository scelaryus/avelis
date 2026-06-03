import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { Badge } from '../../components/ui/Badge';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

interface TierCalc {
  tier_pct: number; discount_pct: string; base_rf1: string; base_rf2: string | null;
  base_total: string; applied_rf1: string; applied_rf2: string | null;
  applied_total: string; savings: string;
}

export function DossierCreate() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const { canSeeRF2 } = useStore();
  const preselectedLot = searchParams.get('lot') || '';

  const [lots, setLots] = useState<any[]>([]);
  const [selectedLotRef, setSelectedLotRef] = useState(preselectedLot);
  const [clientName, setClientName] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [typePaiement, setTypePaiement] = useState('FONDS_PROPRES');
  const [selectedTier, setSelectedTier] = useState(30);
  const [tierCalcs, setTierCalcs] = useState<TierCalc[]>([]);
  const [tierLoading, setTierLoading] = useState(false);
  const [proofId, setProofId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Load available lots
  useEffect(() => {
    Promise.all([
      api.get('/adv/edd/lots?status=DISPONIBLE'),
      api.get('/adv/edd/lots?status=VERROUILLE'),
    ]).then(([r1, r2]) => setLots([...(r1.data.data || []), ...(r2.data.data || [])])).catch(() => {});
  }, []);

  const selectedLot = lots.find(l => l.ref === selectedLotRef);

  // When lot changes, fetch tier calculations for all 4 tiers
  useEffect(() => {
    if (!selectedLotRef) { setTierCalcs([]); return; }
    setTierLoading(true);
    Promise.all(
      [30, 50, 70, 100].map(pct =>
        api.post('/adv/edd/pricing-grid/calculate', { lot_ref: selectedLotRef, tier_pct: pct })
          .then(r => ({ ...r.data.data, tier_pct: pct }))
          .catch(() => null)
      )
    ).then(results => {
      setTierCalcs(results.filter(Boolean) as TierCalc[]);
      setTierLoading(false);
    });
  }, [selectedLotRef]);

  const activeTier = tierCalcs.find(t => t.tier_pct === selectedTier);
  const appliedRF1 = activeTier ? parseFloat(activeTier.applied_rf1) : (selectedLot ? parseFloat(selectedLot.rf1_price) : 0);
  const appliedRF2 = activeTier && activeTier.applied_rf2 ? parseFloat(activeTier.applied_rf2) : (selectedLot ? parseFloat(selectedLot.rf2_price || '0') : 0);
  const appliedTotal = appliedRF1 + appliedRF2;
  const savings = activeTier ? parseFloat(activeTier.savings) : 0;

  // Calculate minimum SPOT payment based on tier + type
  const minSpotRF2 = appliedRF2; // RF2 always 100% cash upfront
  let minSpotRF1 = 0;
  if (typePaiement === 'SPOT') {
    minSpotRF1 = appliedRF1; // 100%
  } else if (typePaiement === 'FONDS_PROPRES') {
    minSpotRF1 = appliedTotal * 0.3 - minSpotRF2; // 30% of prix reel minus RF2
    if (minSpotRF1 < 0) minSpotRF1 = 0;
  } else if (typePaiement === 'CREDIT_BANCAIRE') {
    minSpotRF1 = 0; // apport 20% comes later at VSP
  }

  const submit = async () => {
    if (!selectedLotRef || !clientName) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await api.post('/adv/dossiers', {
        lot_ref: selectedLotRef,
        client_name: clientName,
        client_phone: clientPhone,
        type_paiement: typePaiement,
        tier_engagement_pct: selectedTier,
        tier_discount_pct: activeTier?.discount_pct || '0',
        prix_rf1: appliedRF1,
        prix_rf2: appliedRF2,
        prix_base_rf1: activeTier?.base_rf1,
        prix_base_rf2: activeTier?.base_rf2,
        justificative_doc_id: proofId,
      });
      nav(`/adv/dossiers/${res.data.data?.numero || ''}`);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erreur creation dossier');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <Link to="/adv/lots" className="text-sm text-iris hover:underline">&larr; Lots EDD</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouveau Dossier ADV</h1>

      {error && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{error}</div>}

      <div className="space-y-6">

        {/* Step 1: Lot selection */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-4">1. Lot a reserver</h2>
          <select value={selectedLotRef} onChange={e => { setSelectedLotRef(e.target.value); setSelectedTier(30); }}
            className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
            <option value="">Selectionnez un lot disponible</option>
            {lots.map(l => (
              <option key={l.ref} value={l.ref}>
                {l.ref} -- {l.typology} {l.surface}m2 -- {l.project_code} -- {formatDA(l.rf1_price)}
              </option>
            ))}
          </select>
          {selectedLot && (
            <div className="bg-[#FAFAFA] rounded-lg p-4 mt-3 text-sm grid grid-cols-3 gap-3">
              <div><p className="text-storm">Lot</p><p className="font-mono font-bold text-iris">{selectedLot.ref}</p></div>
              <div><p className="text-storm">Projet</p><p className="font-semibold">{selectedLot.project_code}</p></div>
              <div><p className="text-storm">Type</p><p>{selectedLot.typology} -- {selectedLot.surface}m2 -- Et.{selectedLot.floor}</p></div>
            </div>
          )}
        </div>

        {/* Step 2: Tier selection — THE KEY DECISION */}
        {selectedLotRef && (
          <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card">
            <h2 className="text-base font-semibold mb-2">2. Palier de versement initial</h2>
            <p className="text-sm text-storm mb-4">
              Plus le client verse a la reservation, plus le prix baisse. Ce choix determine le prix definitif de l'appartement.
            </p>

            {tierLoading ? (
              <div className="grid grid-cols-4 gap-3">{[1,2,3,4].map(i => <div key={i} className="h-40 bg-mist rounded-lg animate-pulse" />)}</div>
            ) : tierCalcs.length === 0 ? (
              <div className="bg-[rgba(255,107,107,0.06)] rounded-lg p-4 text-sm text-coral">
                Aucune grille tarifaire configuree pour ce projet/typologie. Le DAF doit configurer la grille (FC-014).
              </div>
            ) : (
              <div className="grid grid-cols-4 gap-3">
                {tierCalcs.map(tier => {
                  const isSelected = selectedTier === tier.tier_pct;
                  const tierSavings = parseFloat(tier.savings);
                  const tierTotal = parseFloat(tier.applied_total);
                  return (
                    <button key={tier.tier_pct} onClick={() => setSelectedTier(tier.tier_pct)} type="button"
                      className={`p-4 rounded-lg border-2 text-left transition relative overflow-hidden ${
                        isSelected ? 'border-iris bg-[rgba(108,92,231,0.06)] shadow-md' : 'border-mist hover:border-lavender'}`}>
                      {/* Discount ribbon */}
                      {tierSavings > 0 && (
                        <div className="absolute top-0 right-0 bg-mint text-white text-[10px] font-bold px-2 py-0.5 rounded-bl">
                          -{tier.discount_pct}%
                        </div>
                      )}
                      <p className="text-xl font-bold text-iris mb-1">{tier.tier_pct}%</p>
                      <p className="text-[10px] text-storm uppercase tracking-wider mb-3">versement initial</p>

                      <div className="space-y-1.5">
                        <div>
                          <p className="text-[10px] text-storm">Prix RF1 (declare)</p>
                          <p className="text-sm font-mono font-bold">{formatDA(tier.applied_rf1)}</p>
                        </div>
                        {canSeeRF2 && tier.applied_rf2 && (
                          <div>
                            <p className="text-[10px] text-storm">Prix RF2 (non declare)</p>
                            <p className="text-sm font-mono font-bold">{formatDA(tier.applied_rf2)}</p>
                          </div>
                        )}
                        <div className="border-t border-mist pt-1.5">
                          <p className="text-[10px] text-storm">Prix total</p>
                          <p className={`text-base font-mono font-bold ${isSelected ? 'text-iris' : ''}`}>{formatDA(tierTotal)}</p>
                        </div>
                      </div>

                      {tierSavings > 0 && (
                        <div className="mt-2 bg-[rgba(0,184,148,0.1)] rounded px-2 py-1 text-center">
                          <p className="text-xs text-mint font-bold">Economie: {formatDA(tierSavings)}</p>
                        </div>
                      )}
                      {tierSavings === 0 && (
                        <p className="mt-2 text-[10px] text-storm text-center italic">Tarif de base</p>
                      )}

                      {isSelected && (
                        <div className="absolute top-2 left-2 w-5 h-5 rounded-full bg-iris text-white flex items-center justify-center text-xs">&#10003;</div>
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Selected tier summary */}
            {activeTier && savings > 0 && (
              <div className="mt-4 bg-[rgba(0,184,148,0.06)] rounded-lg p-3 flex items-center justify-between">
                <div className="text-sm">
                  <span className="text-storm">Prix base: <span className="line-through font-mono">{formatDA(activeTier.base_total)}</span></span>
                  <span className="mx-2">&#8594;</span>
                  <span className="font-bold font-mono text-iris">{formatDA(activeTier.applied_total)}</span>
                </div>
                <Badge variant="success">Economie {formatDA(savings)}</Badge>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Client info */}
        {selectedLotRef && (
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="text-base font-semibold mb-4">3. Informations client</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-storm block mb-1.5">Nom complet <span className="text-coral">*</span></label>
                <input value={clientName} onChange={e => setClientName(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" placeholder="Nom complet du client" />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1.5">Telephone</label>
                <input value={clientPhone} onChange={e => setClientPhone(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" placeholder="+213..." />
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Payment type */}
        {selectedLotRef && (
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="text-base font-semibold mb-4">4. Mode de paiement</h2>
            <div className="grid grid-cols-2 gap-3 mb-4">
              {[
                { val: 'FONDS_PROPRES', label: 'Fonds propres', desc: '30% min du prix reel a la reservation, echeancier mensuel pour le reste' },
                { val: 'CREDIT_BANCAIRE', label: 'Credit bancaire', desc: 'RF2 en especes + apport 20% RF1 au VSP, banque finance 80% RF1' },
                { val: 'SPOT', label: 'Comptant (SPOT)', desc: `Paiement integral des ${formatDA(appliedTotal)} a la reservation` },
                { val: 'MIXTE', label: 'Mixte', desc: 'Combinaison credit partiel + fonds propres' },
              ].map(tp => (
                <button key={tp.val} onClick={() => setTypePaiement(tp.val)} type="button"
                  className={`p-3 rounded-lg border-2 text-left transition ${typePaiement === tp.val ? 'border-iris bg-[rgba(108,92,231,0.05)]' : 'border-mist hover:border-silver'}`}>
                  <p className="text-sm font-semibold">{tp.label}</p>
                  <p className="text-xs text-storm mt-0.5">{tp.desc}</p>
                </button>
              ))}
            </div>

            {/* Payment breakdown based on tier + type */}
            <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm space-y-2">
              <h3 className="font-semibold text-sm mb-2">Decomposition du paiement a la reservation</h3>

              {/* RF2 always cash upfront */}
              {canSeeRF2 && appliedRF2 > 0 && (
                <div className="flex justify-between items-center">
                  <div><span className="text-storm">RF2 integral</span> <Badge variant="warning">ESPECES</Badge></div>
                  <span className="font-mono font-bold">{formatDA(appliedRF2)}</span>
                </div>
              )}

              {/* RF1 SPOT amount based on type */}
              {typePaiement === 'SPOT' && (
                <div className="flex justify-between items-center">
                  <div><span className="text-storm">RF1 integral</span> <Badge variant="info">CHEQUE</Badge></div>
                  <span className="font-mono font-bold">{formatDA(appliedRF1)}</span>
                </div>
              )}
              {typePaiement === 'FONDS_PROPRES' && (
                <>
                  <div className="flex justify-between items-center">
                    <div><span className="text-storm">Minimum 30% prix reel</span></div>
                    <span className="font-mono font-bold">{formatDA(appliedTotal * 0.3)}</span>
                  </div>
                  {minSpotRF1 > 0 && (
                    <div className="flex justify-between items-center">
                      <div><span className="text-storm">Dont part RF1</span> <Badge variant="info">CHEQUE</Badge></div>
                      <span className="font-mono">{formatDA(minSpotRF1)}</span>
                    </div>
                  )}
                  <div className="flex justify-between items-center text-storm">
                    <span>Reste en echeances mensuelles</span>
                    <span className="font-mono">{formatDA(appliedTotal * 0.7)}</span>
                  </div>
                </>
              )}
              {typePaiement === 'CREDIT_BANCAIRE' && (
                <>
                  <div className="flex justify-between items-center">
                    <div><span className="text-storm">Apport 20% RF1 (au VSP)</span> <Badge variant="info">CHEQUE</Badge></div>
                    <span className="font-mono">{formatDA(appliedRF1 * 0.2)}</span>
                  </div>
                  <div className="flex justify-between items-center text-storm">
                    <span>Credit bancaire (80% RF1)</span>
                    <span className="font-mono">{formatDA(appliedRF1 * 0.8)}</span>
                  </div>
                </>
              )}

              <div className="border-t border-mist pt-2 flex justify-between font-bold">
                <span>Total a la reservation</span>
                <span className="font-mono text-iris">
                  {typePaiement === 'SPOT' ? formatDA(appliedTotal) :
                   typePaiement === 'FONDS_PROPRES' ? formatDA(Math.max(appliedTotal * 0.3, appliedRF2)) :
                   formatDA(appliedRF2)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Proof upload */}
        {selectedLotRef && (
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="text-base font-semibold mb-4">5. Justificatif SPOT</h2>
            <ProofUpload onUploaded={id => setProofId(id)} label="Copie cheque RF1 + recu especes RF2" />
          </div>
        )}

        {/* Submit */}
        {selectedLotRef && (
          <button onClick={submit}
            disabled={!selectedLotRef || !clientName || !proofId || submitting || tierCalcs.length === 0}
            className="w-full py-3.5 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
            {submitting ? 'Creation en cours...' : `Creer le dossier -- Palier ${selectedTier}% -- ${formatDA(appliedTotal)}`}
          </button>
        )}
      </div>
    </div>
  );
}
