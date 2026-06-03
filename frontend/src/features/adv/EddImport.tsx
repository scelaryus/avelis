import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

export function EddImport() {
  const nav = useNavigate();
  const { canSeeRF2 } = useStore();
  const [step, setStep] = useState<'upload' | 'analyzing' | 'review' | 'saving' | 'done'>('upload');
  const [projects, setProjects] = useState<any[]>([]);
  const [projectCode, setProjectCode] = useState('');
  const [aiData, setAiData] = useState<any>(null);
  const [lots, setLots] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    api.get('/foundation/projects?status=ACTIF').then(r => setProjects(r.data.data || [])).catch(() => {});
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!projectCode) { setError('Selectionnez un projet d\'abord'); return; }
    setStep('analyzing');
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/adv/edd/read-document', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      const d = res.data.data;
      setAiData(d);
      if (d.error) setError(d.error);
      setLots((d.lots || []).map((l: any, i: number) => ({ ...l, _include: true, _idx: i })));
      setStep('review');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur analyse');
      setStep('upload');
    }
  };

  const updateLot = (idx: number, field: string, value: any) => {
    setLots(prev => prev.map(l => l._idx === idx ? { ...l, [field]: value } : l));
  };

  const toggleLot = (idx: number) => {
    setLots(prev => prev.map(l => l._idx === idx ? { ...l, _include: !l._include } : l));
  };

  const confirmImport = async () => {
    const selected = lots.filter(l => l._include);
    if (selected.length === 0) { setError('Aucun lot selectionne'); return; }
    setStep('saving');
    try {
      const res = await api.post('/adv/edd/lots/import-ai', {
        project_code: projectCode,
        lots: selected.map(l => ({
          typology: l.typology, surface: l.surface, floor: l.floor,
          block: l.block, orientation: l.orientation,
          rf1_price: l.rf1_price, rf2_price: l.rf2_price,
          description: l.description,
        })),
      });
      setResult(res.data.data);
      setStep('done');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur creation');
      setStep('review');
    }
  };

  const selectedCount = lots.filter(l => l._include).length;
  const totalRf1 = lots.filter(l => l._include).reduce((s, l) => s + (parseFloat(l.rf1_price) || 0), 0);

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-[32px] font-bold mb-2">Importer un EDD</h1>
      <p className="text-sm text-storm mb-6">Uploadez un document EDD — l'IA extrait les lots automatiquement pour revision.</p>

      {/* Step bar */}
      <div className="flex gap-1 mb-6">
        {['Upload', 'Analyse AI', 'Revision', 'Importe'].map((s, i) => {
          const steps = ['upload', 'analyzing', 'review', 'done'];
          const current = steps.indexOf(step);
          return <div key={s} className={`flex-1 h-1.5 rounded-full ${i <= current ? 'bg-iris' : 'bg-mist'}`} />;
        })}
      </div>

      {error && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{error}</div>}

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <div className="space-y-4">
          <div className="bg-white rounded-card border border-mist p-6 shadow-card">
            <label className="text-sm font-medium text-storm block mb-2">Projet cible <span className="text-coral">*</span></label>
            <select value={projectCode} onChange={e => setProjectCode(e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none mb-4">
              <option value="">Selectionner le projet...</option>
              {projects.map((p: any) => <option key={p.code} value={p.code}>{p.code} — {p.name}</option>)}
            </select>

            <label className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer block transition ${projectCode ? 'border-iris hover:bg-[rgba(108,92,231,0.03)]' : 'border-mist opacity-50 cursor-not-allowed'}`}>
              <div className="text-4xl mb-3">&#128196;</div>
              <p className="text-sm font-medium">Uploader le document EDD</p>
              <p className="text-xs text-storm mt-1">PDF, image (JPG/PNG), CSV, fichier texte — en francais ou arabe</p>
              <p className="text-xs text-storm mt-1">L'IA extrait automatiquement tous les lots avec surfaces, etages et prix</p>
              <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png,.webp,.csv,.txt,.tsv" onChange={handleUpload} disabled={!projectCode} />
            </label>
          </div>
        </div>
      )}

      {/* Step 2: Analyzing */}
      {step === 'analyzing' && (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <div className="w-12 h-12 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-medium">Analyse du document EDD en cours...</p>
          <p className="text-xs text-storm mt-1">L'IA lit le document et extrait les lots, surfaces, etages et prix</p>
        </div>
      )}

      {/* Step 3: Review */}
      {step === 'review' && (
        <div className="space-y-4">
          {/* AI summary */}
          {aiData && (
            <div className={`flex items-center gap-3 p-3 rounded-lg text-sm ${
              (aiData.confidence || 0) >= 80 ? 'bg-[rgba(85,239,196,0.1)] border border-mint' :
              (aiData.confidence || 0) >= 50 ? 'bg-[#FFF8E1] border border-honey' :
              'bg-[rgba(255,107,107,0.08)] border border-coral'
            }`}>
              <Badge variant={(aiData.confidence || 0) >= 80 ? 'success' : (aiData.confidence || 0) >= 50 ? 'warning' : 'error'}>
                {aiData.confidence || 0}%
              </Badge>
              <span>
                {aiData.total_lots} lot(s) extraits
                {aiData.project_name && ` — Projet: ${aiData.project_name}`}
                {aiData.document_type && ` — Type: ${aiData.document_type}`}
              </span>
            </div>
          )}
          {aiData?.notes && <p className="text-xs text-storm bg-[#FAFAFA] rounded-lg p-2">{aiData.notes}</p>}

          {/* Summary bar */}
          <div className="flex items-center justify-between bg-white rounded-card border border-mist p-3">
            <span className="text-sm">{selectedCount}/{lots.length} lots selectionnes — Total RF1: <span className="font-mono font-bold">{formatDA(totalRf1)}</span></span>
            <div className="flex gap-2">
              <button onClick={() => setLots(l => l.map(x => ({ ...x, _include: true })))} className="text-xs text-iris hover:underline">Tout selectionner</button>
              <button onClick={() => setLots(l => l.map(x => ({ ...x, _include: false })))} className="text-xs text-storm hover:underline">Tout deselectionner</button>
            </div>
          </div>

          {/* Lots table */}
          <div className="bg-white rounded-card border border-mist shadow-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                <th className="py-2 px-2 w-8"></th>
                <th className="py-2 px-2 text-left text-storm">Ref</th>
                <th className="py-2 px-2 text-left text-storm">Type</th>
                <th className="py-2 px-2 text-right text-storm">Surface</th>
                <th className="py-2 px-2 text-right text-storm">Etage</th>
                <th className="py-2 px-2 text-left text-storm">Bloc</th>
                <th className="py-2 px-2 text-left text-storm">Orient.</th>
                <th className="py-2 px-2 text-right text-storm">Prix RF1</th>
                {canSeeRF2 && <th className="py-2 px-2 text-right text-storm">Prix RF2</th>}
                <th className="py-2 px-2 text-left text-storm">Notes</th>
              </tr></thead>
              <tbody>
                {lots.map((l: any) => (
                  <tr key={l._idx} className={`border-b border-mist ${l._include ? 'bg-white' : 'bg-[#FAFAFA] opacity-50'}`}>
                    <td className="py-1.5 px-2 text-center">
                      <input type="checkbox" checked={l._include} onChange={() => toggleLot(l._idx)} />
                    </td>
                    <td className="py-1.5 px-2 font-mono text-xs">{l.lot_ref || '-'}</td>
                    <td className="py-1.5 px-2">
                      <select value={l.typology || 'F3'} onChange={e => updateLot(l._idx, 'typology', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs w-20">
                        {['F2','F3','F4','F5','DUPLEX','LOCAL_COMMERCIAL','PARKING','CAVE'].map(t => <option key={t}>{t}</option>)}
                      </select>
                    </td>
                    <td className="py-1.5 px-2">
                      <input type="number" value={l.surface || ''} onChange={e => updateLot(l._idx, 'surface', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs font-mono w-16 text-right" />
                    </td>
                    <td className="py-1.5 px-2">
                      <input type="number" value={l.floor ?? ''} onChange={e => updateLot(l._idx, 'floor', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs font-mono w-12 text-right" />
                    </td>
                    <td className="py-1.5 px-2">
                      <input type="text" value={l.block || ''} onChange={e => updateLot(l._idx, 'block', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs w-12" />
                    </td>
                    <td className="py-1.5 px-2">
                      <select value={l.orientation || ''} onChange={e => updateLot(l._idx, 'orientation', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs w-16">
                        <option value="">—</option>
                        {['NORD','SUD','EST','OUEST','DOUBLE'].map(o => <option key={o}>{o}</option>)}
                      </select>
                    </td>
                    <td className="py-1.5 px-2">
                      <input type="number" value={l.rf1_price || ''} onChange={e => updateLot(l._idx, 'rf1_price', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs font-mono w-24 text-right" />
                    </td>
                    {canSeeRF2 && <td className="py-1.5 px-2">
                      <input type="number" value={l.rf2_price || ''} onChange={e => updateLot(l._idx, 'rf2_price', e.target.value)}
                        className="border border-mist rounded px-1 py-0.5 text-xs font-mono w-24 text-right" />
                    </td>}
                    <td className="py-1.5 px-2 text-xs text-storm max-w-[150px] truncate">{l.description || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button onClick={() => { setStep('upload'); setLots([]); setAiData(null); }}
              className="px-6 py-3 border border-mist rounded-button text-sm text-storm">Recommencer</button>
            <button onClick={confirmImport} disabled={selectedCount === 0}
              className="flex-1 py-3 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
              Importer {selectedCount} lot(s) dans {projectCode}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Saving */}
      {step === 'saving' && (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <div className="w-12 h-12 border-3 border-mint border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-medium">Creation des lots en cours...</p>
        </div>
      )}

      {/* Step 5: Done */}
      {step === 'done' && result && (
        <div className="bg-white rounded-card border border-mint p-8 text-center space-y-4">
          <div className="text-5xl">&#10003;</div>
          <h2 className="text-xl font-bold">{result.lots_created} lot(s) importes</h2>
          {result.errors?.length > 0 && (
            <div className="text-xs text-coral">{result.errors.length} erreur(s): {result.errors.slice(0, 3).join('; ')}</div>
          )}
          <div className="flex gap-3 justify-center mt-4">
            <button onClick={() => nav('/adv/lots')} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">Voir les lots</button>
            <button onClick={() => { setStep('upload'); setLots([]); setAiData(null); setResult(null); }}
              className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-rose-50">Importer un autre EDD</button>
          </div>
        </div>
      )}
    </div>
  );
}
