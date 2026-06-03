import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

export function CffCreate() {
  const nav = useNavigate();
  const [entities, setEntities] = useState<any[]>([]);
  const [emitterId, setEmitterId] = useState('');
  const [receiverId, setReceiverId] = useState('');
  const [montantHt, setMontantHt] = useState(0);
  const [invoiceDate, setInvoiceDate] = useState('');
  const [proofId, setProofId] = useState('');
  const [preview, setPreview] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get('/foundation/entities').then(r => setEntities(r.data.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!emitterId || !montantHt || !invoiceDate) { setPreview(null); return; }
    const timer = setTimeout(() => {
      api.post('/finance/cff/calculate', { montant_ht: montantHt, emitter_entity_id: emitterId, receiver_entity_id: receiverId, invoice_date: invoiceDate })
        .then(r => setPreview(r.data.data))
        .catch(() => setPreview(null));
    }, 500);
    return () => clearTimeout(timer);
  }, [emitterId, receiverId, montantHt, invoiceDate]);

  const submit = async () => {
    setSubmitting(true);
    try {
      const res = await api.post('/finance/cff/create', {
        montant_ht: montantHt, emitter_entity_id: emitterId, receiver_entity_id: receiverId,
        invoice_date: invoiceDate, justificative_doc_id: proofId,
      });
      nav(`/finance/cff/${res.data.data?.id || ''}`);
    } catch { setSubmitting(false); }
  };

  const yaminaAlert = preview?.distribution?.find((d: any) => d.associate.includes('Yamina') && parseFloat(d.amount) > 0 && d.should_be_zero);

  return (
    <div className="max-w-3xl">
      <Link to="/finance/cff" className="text-sm text-iris hover:underline">← CFF</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouvelle Facture RF3 + Calcul CFF</h1>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-5">
          <h2 className="font-semibold">Facture RF3</h2>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Entité émettrice <span className="text-coral">*</span></label>
            <select value={emitterId} onChange={e => setEmitterId(e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
              <option value="">Sélectionnez</option>
              {entities.map(e => <option key={e.code} value={e.code}>{e.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Entité réceptrice <span className="text-coral">*</span></label>
            <select value={receiverId} onChange={e => setReceiverId(e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
              <option value="">Sélectionnez</option>
              {entities.filter(e => e.code !== emitterId).map(e => <option key={e.code} value={e.code}>{e.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Montant HT <span className="text-coral">*</span></label>
            <input type="number" value={montantHt || ''} onChange={e => setMontantHt(parseFloat(e.target.value) || 0)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" placeholder="0" />
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Date facture <span className="text-coral">*</span></label>
            <input type="date" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
          </div>
          <ProofUpload onUploaded={id => setProofId(id)} label="Scan de la facture RF3" />
        </div>

        <div className="space-y-4">
          {preview ? (
            <>
              {yaminaAlert && (
                <div className="bg-coral text-white rounded-lg p-4 animate-[flash_2s_infinite]">
                  <p className="font-bold">⚠ VIOLATION Y2/Y3/Y4</p>
                  <p className="text-sm mt-1">Yamina a un CFF imputé de {formatDA(yaminaAlert.amount)} sur une entité où elle est à 0%.</p>
                </div>
              )}
              <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
                <h2 className="font-semibold mb-4">Décomposition CFF</h2>
                <div className="space-y-2 text-sm">
                  {[['TVA (19%)', preview.tva], ['TAP', preview.tap], ['IBS base', preview.ibs_base], ['IBS', preview.ibs], ['Timbre', preview.stamp_duty]].map(([l, v]) => (
                    <div key={l as string} className="flex justify-between py-1 border-b border-mist">
                      <span className="text-storm">{l}</span><span className="font-mono font-bold">{formatDA(v as number)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between py-2 border-t-2 border-iris">
                    <span className="font-bold text-iris">CFF TOTAL</span><span className="font-mono font-bold text-iris text-lg">{formatDA(preview.cff_total)}</span>
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
                <h2 className="font-semibold mb-4">Distribution (% entreprise émettrice)</h2>
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-mist"><th className="py-2 text-left text-storm">Associé</th><th className="py-2 text-right text-storm">%</th><th className="py-2 text-right text-storm">Montant</th></tr></thead>
                  <tbody>
                    {(preview.distribution || []).map((d: any) => (
                      <tr key={d.associate} className={`border-b border-mist ${d.should_be_zero && parseFloat(d.amount) > 0 ? 'bg-[rgba(255,107,107,0.1)]' : ''}`}>
                        <td className="py-2 font-medium">{d.associate}</td>
                        <td className="py-2 text-right font-mono">{d.percentage}%</td>
                        <td className={`py-2 text-right font-mono font-bold ${parseFloat(d.amount) === 0 ? 'text-mint' : ''}`}>{formatDA(d.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button onClick={submit} disabled={!proofId || submitting || !!yaminaAlert}
                className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
                {submitting ? 'Enregistrement...' : 'Enregistrer RF3 + CFF'}
              </button>
            </>
          ) : (
            <div className="bg-white rounded-card border border-mist p-8 text-center text-storm">
              <p className="text-sm">Remplissez les champs pour voir le calcul CFF en temps réel</p>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes flash { 0%,100% { opacity:1 } 50% { opacity:0.5 } }`}</style>
    </div>
  );
}
