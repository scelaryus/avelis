import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import api from '../../lib/api-client';

const CATEGORIES = [
  { value: 'GROS_OEUVRE', label: 'Gros oeuvre', desc: 'Fondations, structure, etancheite' },
  { value: 'SECOND_OEUVRE', label: 'Second oeuvre', desc: 'Cloisons, electricite, peinture' },
  { value: 'BET_ARCHITECTURE', label: 'BET Architecture', desc: 'Etudes, plans, suivi' },
  { value: 'MACHINE_OEM', label: 'Machine OEM', desc: 'Achat machine industrielle' },
  { value: 'FOURNITURE', label: 'Fourniture', desc: 'Achat materiaux ou equipements' },
  { value: 'PRESTATION', label: 'Prestation', desc: 'Service externe' },
  { value: 'MAINTENANCE', label: 'Maintenance', desc: 'Entretien et reparations' },
  { value: 'AUTRE', label: 'Autre', desc: 'Non categorise' },
];

export function OperationCreate() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<any[]>([]);
  const [contracts, setContracts] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ categorie: 'GROS_OEUVRE', montant_ht: '', title: '', project_id: '', date_debut: '', date_fin_prevue: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.get('/foundation/projects?status=ACTIF'),
      api.get('/juridique/contracts?status=actif'),
    ]).then(([pR, cR]) => {
      setProjects(pR.data.data || []);
      setContracts(cR.data.data || []);
    }).catch(() => {});
  }, []);

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title) { setError('Titre obligatoire'); return; }
    setSubmitting(true); setError('');
    try {
      const r = await api.post('/operations/', {
        ...form, montant_ht: form.montant_ht ? parseFloat(form.montant_ht) : 0,
        project_id: form.project_id || null,
      });
      nav(`/operations/${r.data.data.id}`);
    } catch (e: any) { setError(e.response?.data?.detail?.message || 'Erreur'); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-3xl">
      <Link to="/operations" className="text-sm text-iris hover:underline">&larr; Operations</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouvel Engagement</h1>

      {error && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{error}</div>}

      <div className="space-y-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-3">Categorie</h2>
          <div className="grid grid-cols-4 gap-2">
            {CATEGORIES.map(c => (
              <button key={c.value} onClick={() => set('categorie', c.value)}
                className={`p-3 rounded-lg border-2 text-left transition ${form.categorie === c.value ? 'border-iris bg-[rgba(108,92,231,0.05)]' : 'border-mist hover:border-lavender'}`}>
                <p className="text-sm font-semibold">{c.label}</p>
                <p className="text-[10px] text-storm">{c.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <h2 className="font-semibold">Details</h2>
          <div>
            <label className="text-xs font-medium text-storm block mb-1">Titre <span className="text-coral">*</span></label>
            <input value={form.title} onChange={e => set('title', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
              placeholder="Ex: Gros-oeuvre projet principal Batiment A" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Projet</label>
              <select value={form.project_id} onChange={e => set('project_id', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                <option value="">Aucun projet</option>
                {projects.map(p => <option key={p.code} value={p.id || p.code}>{p.code} — {p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Montant HT (DA)</label>
              <input type="number" value={form.montant_ht} onChange={e => set('montant_ht', e.target.value)}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" placeholder="85000000" />
              {form.montant_ht && <p className="text-xs text-storm mt-1">TTC (19%): {formatDA(parseFloat(form.montant_ht) * 1.19)}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Date debut</label>
              <input type="date" value={form.date_debut} onChange={e => set('date_debut', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Date fin prevue</label>
              <input type="date" value={form.date_fin_prevue} onChange={e => set('date_fin_prevue', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
          </div>
        </div>

        <button onClick={submit} disabled={!form.title || submitting}
          className="w-full py-3.5 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Creation...' : 'Creer l\'engagement'}
        </button>
      </div>
    </div>
  );
}
