import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

export function LotCreate() {
  const nav = useNavigate();
  const { canSeeRF2 } = useStore();
  const [projects, setProjects] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ typology: 'F3', orientation: 'Sud', status: 'DISPONIBLE' });
  const [proofId, setProofId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { api.get('/foundation/projects?status=ACTIF').then(r => setProjects(r.data.data || [])).catch(() => {}); }, []);

  const set = (k: string, v: any) => setForm((p: any) => ({ ...p, [k]: v }));

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post('/adv/edd/lots', { ...form, justificative_doc_id: proofId });
      nav('/adv/lots');
    } catch {} finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-2xl">
      <Link to="/adv/lots" className="text-sm text-iris hover:underline">← Lots EDD</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouveau Lot EDD</h1>

      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Projet <span className="text-coral">*</span></label>
            <select value={form.project_id || ''} onChange={e => set('project_id', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
              <option value="">Sélectionnez</option>
              {projects.map(p => <option key={p.code} value={p.code}>{p.code} — {p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Typologie <span className="text-coral">*</span></label>
            <select value={form.typology} onChange={e => set('typology', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
              {['F2', 'F3', 'F4', 'F5', 'Duplex', 'Local Commercial', 'Parking', 'Cave'].map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Bloc <span className="text-coral">*</span></label>
            <input value={form.block || ''} onChange={e => set('block', e.target.value)} placeholder="A, B, C..."
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Étage <span className="text-coral">*</span></label>
            <input type="number" value={form.floor || ''} onChange={e => set('floor', parseInt(e.target.value))}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" placeholder="0 = RDC" />
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Surface (m²) <span className="text-coral">*</span></label>
            <input type="number" value={form.surface || ''} onChange={e => set('surface', parseFloat(e.target.value))}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Orientation</label>
            <select value={form.orientation} onChange={e => set('orientation', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
              {['Nord', 'Sud', 'Est', 'Ouest', 'Double'].map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Prix RF1 (DA) <span className="text-coral">*</span></label>
            <input type="number" value={form.rf1_price || ''} onChange={e => set('rf1_price', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
          </div>
          {canSeeRF2 && <div>
            <label className="text-sm font-medium text-storm block mb-1.5">Prix RF2 (DA)</label>
            <input type="number" value={form.rf2_price || ''} onChange={e => set('rf2_price', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
          </div>}
        </div>

        <ProofUpload onUploaded={id => setProofId(id)} label="Plan du lot ou fiche descriptive" required={false} />

        <button onClick={submit} disabled={!form.project_id || !form.typology || !form.surface || !form.rf1_price || submitting}
          className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Création...' : 'Créer le lot'}
        </button>
      </div>
    </div>
  );
}
