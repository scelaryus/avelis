import { useEffect, useState } from 'react';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import api from '../../lib/api-client';

export function GacebRap() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ brut: '', deduction: '' });
  const [proofId, setProofId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const reload = () => {
    setLoading(true);
    api.get('/cc/gaceb/rap').then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const submitSituation = async () => {
    setSubmitting(true);
    setFormError('');
    try {
      await api.post('/cc/gaceb/situations', {
        brut: parseFloat(form.brut),
        deduction: parseFloat(form.deduction),
        justificative_doc_id: proofId,
      });
      setShowForm(false);
      setForm({ brut: '', deduction: '' });
      setProofId('');
      reload();
    } catch (e: any) {
      setFormError(e.response?.data?.detail || 'Erreur serveur');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Aucune donnee GACEB disponible</p>;

  const adv = data.advance_120m;
  const pctUsed = (1 - Number(adv.residual) / Number(adv.initial)) * 100;
  const brut = parseFloat(form.brut) || 0;
  const ded = parseFloat(form.deduction) || 0;
  const dedMax = parseFloat(adv.residual);
  const dedError = ded > dedMax;
  const net = brut - ded;

  // Waterfall from REAL API data
  const totalMarches = parseFloat(data.total_marches || '0');
  const totalDedAvance = parseFloat(data.total_deductions_avance || '0');
  const vehiclesTotal = parseFloat(data.vehicles_total || '0');
  const cashPaye = parseFloat(data.total_cash_paye || '0');
  const rapNet = parseFloat(data.rap_net || '0');

  const waterfallData = [
    { name: 'Total marches', value: totalMarches, fill: '#6C5CE7' },
    { name: 'Deductions avance', value: -totalDedAvance, fill: '#E17055' },
    { name: 'Vehicules cedes', value: -vehiclesTotal, fill: '#E17055' },
    { name: 'Cash paye', value: -cashPaye, fill: '#0984E3' },
    { name: 'RAP Net', value: rapNet, fill: rapNet >= 0 ? '#00B894' : '#FF6B6B' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">GACEB - Reste A Payer</h1>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
          + Nouvelle situation
        </button>
      </div>

      {/* New situation form */}
      {showForm && (
        <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-8 space-y-4">
          <h2 className="font-semibold">Nouvelle situation de travaux GACEB</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">Montant brut (DA) <span className="text-coral">*</span></label>
              <input type="number" value={form.brut} onChange={e => setForm(f => ({ ...f, brut: e.target.value }))}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
                placeholder="Ex: 25000000" />
            </div>
            <div>
              <label className="text-sm font-medium text-storm block mb-1.5">
                Deduction sur avance 120M (DA) <span className="text-coral">*</span>
              </label>
              <input type="number" value={form.deduction} onChange={e => setForm(f => ({ ...f, deduction: e.target.value }))}
                className={`w-full border rounded-input px-4 py-2.5 text-sm font-mono outline-none ${dedError ? 'border-coral focus:ring-coral/20' : 'border-mist focus:border-iris'}`}
                placeholder={`Max: ${formatDA(adv.residual)}`} />
              {dedError && <p className="text-xs text-coral mt-1">Deduction {formatDA(ded)} depasse le solde avance {formatDA(adv.residual)}</p>}
              <p className="text-xs text-storm mt-1">Solde avance actuel: {formatDA(adv.residual)}</p>
            </div>
          </div>

          {/* Live preview */}
          {brut > 0 && (
            <div className="bg-[#FAFAFA] rounded-lg p-4 text-sm">
              <p className="font-semibold mb-2">Apercu:</p>
              <div className="grid grid-cols-4 gap-4">
                <div><p className="text-storm">Brut</p><p className="font-mono font-bold">{formatDA(brut)}</p></div>
                <div><p className="text-storm">Deduction</p><p className="font-mono font-bold text-coral">-{formatDA(ded)}</p></div>
                <div><p className="text-storm">Net cash a verser</p><p className="font-mono font-bold text-mint">{formatDA(net)}</p></div>
                <div><p className="text-storm">Nouveau solde avance</p><p className="font-mono font-bold">{formatDA(dedMax - ded)}</p></div>
              </div>
            </div>
          )}

          <ProofUpload onUploaded={id => setProofId(id)} label="Situation de travaux signee (scan PDF)" />

          {formError && <p className="text-sm text-coral font-medium">{formError}</p>}

          <div className="flex gap-3">
            <button onClick={submitSituation}
              disabled={!brut || !form.deduction || dedError || !proofId || submitting}
              className="px-6 py-2.5 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
              {submitting ? 'Enregistrement...' : 'Enregistrer la situation'}
            </button>
            <button onClick={() => { setShowForm(false); setFormError(''); }}
              className="px-6 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-gray-50">
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* RAP Card */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-sm text-storm font-medium">Avance Materiel 120M DA</p>
            <p className="text-[28px] font-bold text-iris font-mono mt-1">{formatDA(adv.residual)}</p>
            <p className="text-sm text-storm">restant sur {formatDA(adv.initial)}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-storm">Deduit: {formatDA(adv.deducted)}</p>
            <p className="text-xs text-mint font-medium mt-1">Aucun cash sorti - avance en nature</p>
          </div>
        </div>
        <div className="mt-4 bg-mist rounded-full h-4 overflow-hidden">
          <div className="bg-gradient-to-r from-iris to-lavender h-full rounded-full transition-all duration-500" style={{ width: `${pctUsed}%` }} />
        </div>
        <div className="flex justify-between text-xs text-storm mt-1">
          <span>{pctUsed.toFixed(0)}% consomme</span>
          <span>{(100 - pctUsed).toFixed(0)}% restant</span>
        </div>
      </div>

      {/* Waterfall Chart — ALL from API data */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <h2 className="text-lg font-semibold mb-4">Decomposition RAP</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={waterfallData} layout="vertical">
            <XAxis type="number" tickFormatter={(v) => `${(v / 1000000).toFixed(0)}M`} tick={{ fontSize: 11, fill: '#636E72' }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#2D3436' }} width={130} />
            <Tooltip formatter={(v: number) => formatDA(Math.abs(v))} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {waterfallData.map((d, i) => <Cell key={i} fill={d.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Situations Table */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Situations de Travaux ({data.situations.length})</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-3 text-left text-storm font-medium">N</th>
              <th className="py-3 text-left text-storm font-medium">Date</th>
              <th className="py-3 text-right text-storm font-medium">Montant Brut</th>
              <th className="py-3 text-right text-storm font-medium">Deduction Avance</th>
              <th className="py-3 text-right text-storm font-medium">Net Cash Verse</th>
              <th className="py-3 text-right text-storm font-medium">Solde Avance</th>
            </tr></thead>
            <tbody>
              {data.situations.map((s: any) => (
                <tr key={s.num} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                  <td className="py-3 font-mono font-bold text-iris">#{s.num}</td>
                  <td className="py-3 text-xs text-storm">{s.date || '-'}</td>
                  <td className="py-3 text-right font-mono">{formatDA(s.brut)}</td>
                  <td className="py-3 text-right font-mono text-coral">-{formatDA(s.deduction)}</td>
                  <td className="py-3 text-right font-mono text-mint">{formatDA(s.net)}</td>
                  <td className="py-3 text-right font-mono font-bold">{formatDA(s.solde)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Vehicles */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h2 className="text-lg font-semibold mb-4">Vehicules Cedes a GACEB</h2>
        <div className="grid grid-cols-2 gap-4">
          {data.vehicles.map((v: any) => (
            <div key={v.make} className="flex items-center justify-between p-4 rounded-lg border border-mist hover:border-iris transition">
              <div>
                <p className="font-semibold">{v.make}</p>
                <p className="text-sm font-mono text-storm">{formatDA(v.value)}</p>
                {v.associate && <p className="text-xs text-storm">Associe: {v.associate}</p>}
              </div>
              <div className="flex gap-1">
                {(v.steps || ['Achete', 'Immatricule', 'Cede', 'Deduit', 'Revendu']).map((step: string, i: number) => {
                  const done = i < (v.steps_done || 0);
                  return (
                    <div key={i} title={typeof step === 'string' ? step : `Etape ${i+1}`}
                      className={`w-7 h-7 rounded-full text-[9px] flex items-center justify-center font-bold ${done ? 'bg-mint text-white' : 'bg-mist text-silver'}`}>
                      {done ? '✓' : (i + 1)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
