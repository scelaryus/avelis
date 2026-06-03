import { useEffect, useState } from 'react';
import { formatDA, formatDate } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const DOC_TYPES = ['FACTURE_FOURNISSEUR','FACTURE_CLIENT','BON_COMMANDE','DEVIS','CONTRAT','AVENANT_CONTRAT','SITUATION_TRAVAUX','PV_RECEPTION','PV_CHANTIER','PLAN_TECHNIQUE','PHOTO_CHANTIER','FICHE_PAIE','RAPPORT_INTERNE','COURRIER','PERMIS_AUTORISATION','ACTE_NOTARIE','RELEVE_BANCAIRE','ACCORD_PRET','AUTRE'];
const ENTITES = ['ETS-DK','SARL-DP','SARL-DBPI','SARL-OC','SARL-EP','SARL-SEN','EURL-BIM','GROUPE'];
const PROJETS = ['EDEN','AUREA','IRENE','JASMIN','OPERA','BAYTI','ALLO_MAISON','LYS','MAGNOLIA','GROUPE'];
const PROJECT_LABELS: Record<string, string> = {
  EDEN: 'HORIZON',
  AUREA: 'EMERAUDE',
  IRENE: 'RUBIS',
  JASMIN: 'AZURA',
  OPERA: 'NOVA',
  LYS: 'SIGMA',
  BAYTI: 'ORION',
  ALLO_MAISON: 'ATLAS',
  MAGNOLIA: 'CELESTE',
  GROUPE: 'GROUPE',
};
const displayProjectName = (projectCode?: string) => (projectCode ? (PROJECT_LABELS[projectCode] || projectCode) : '-');
const STATUS_V: Record<string, 'success'|'warning'|'error'|'info'|'neutral'> = {
  ARCHIVED: 'success', AWAITING_REVIEW: 'warning', DRAFT: 'info', QUARANTINE: 'error', PENDING: 'neutral',
};

export function DocumentLibrary() {
  const [tab, setTab] = useState<'library'|'upload'|'review'>('library');
  const [docs, setDocs] = useState<any[]>([]);
  const [facets, setFacets] = useState<any>({});
  const [stats, setStats] = useState<any>({});
  const [filters, setFilters] = useState({ q: '', entite: '', projet: '', doc_type: '', status: '', annee: '' });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [reviewQueue, setReviewQueue] = useState<any[]>([]);
  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [contextHint, setContextHint] = useState('');
  // Batch state
  const [batchQueue, setBatchQueue] = useState<File[]>([]);
  const [batchDone, setBatchDone] = useState(0);
  const [batchResults, setBatchResults] = useState<any[]>([]);
  // Drive
  const [driveFolder, setDriveFolder] = useState('');
  // Confirm modal
  const [confirming, setConfirming] = useState<any>(null);
  const [confirmForm, setConfirmForm] = useState<any>({});

  const loadDocs = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.entite) params.set('entite', filters.entite);
    if (filters.projet) params.set('projet', filters.projet);
    if (filters.doc_type) params.set('doc_type', filters.doc_type);
    if (filters.status) params.set('status', filters.status);
    if (filters.annee) { params.set('annee_min', filters.annee); params.set('annee_max', filters.annee); }
    Promise.all([
      api.get(`/dis/search?${params}`),
      api.get('/dis/stats'),
      api.get('/dis/review-queue'),
    ]).then(([docR, statR, revR]) => {
      setDocs(docR.data.data?.documents || []);
      setFacets(docR.data.data?.facets || {});
      setStats(statR.data.data || {});
      setReviewQueue(revR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { loadDocs(); }, [filters.entite, filters.projet, filters.doc_type, filters.status, filters.annee]);

  const uploadFile = async (file: File) => {
    setUploading(true);
    setUploadResult(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('context_hint', contextHint);
    try {
      const r = await api.post('/dis/ingest', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadResult(r.data.data);
      if (r.data.data.status === 'AWAITING_REVIEW') {
        // Open confirmation modal
        setConfirming(r.data.data);
        setConfirmForm(r.data.data.classification || {});
      }
      loadDocs();
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (typeof detail === 'object' && detail.code === 'DIS_002') {
        setUploadResult({ status: 'DUPLICATE', ...detail });
      } else {
        setUploadResult({ status: 'ERROR', message: typeof detail === 'string' ? detail : JSON.stringify(detail) });
      }
    } finally { setUploading(false); }
  };

  // Batch upload: process files one by one sequentially
  const handleBatchFiles = async (files: FileList) => {
    const fileArray = Array.from(files);
    setBatchQueue(fileArray);
    setBatchDone(0);
    setBatchResults([]);
    setUploading(true);
    setUploadResult(null);

    const results: any[] = [];
    for (let i = 0; i < fileArray.length; i++) {
      const file = fileArray[i];
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('context_hint', contextHint);
        const r = await api.post('/dis/ingest', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        results.push({ ...r.data.data, filename: file.name });
      } catch (e: any) {
        const detail = e.response?.data?.detail;
        if (typeof detail === 'object' && detail.code === 'DIS_002') {
          results.push({ status: 'DUPLICATE', filename: file.name, message: detail.message });
        } else {
          results.push({ status: 'ERROR', filename: file.name, message: typeof detail === 'string' ? detail : 'Erreur' });
        }
      }
      setBatchDone(i + 1);
      setBatchResults([...results]);
    }
    setUploading(false);
    loadDocs();
  };

  // Google Drive ingest
  const ingestDrive = async () => {
    if (!driveFolder) return;
    setUploading(true);
    try {
      const r = await api.post('/dis/ingest-drive', { folder_id: driveFolder, recursive: true });
      setUploadResult({ status: 'QUEUED', ...r.data.data });
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur connexion Drive');
    } finally { setUploading(false); }
  };

  const confirmDoc = async () => {
    if (!confirming) return;
    try {
      const res = await api.patch(`/dis/${confirming.id}/confirm`, confirmForm);
      const result = res.data.data;
      // Show routing results
      const routes = result.routed_to || [];
      if (routes.length > 0) {
        const msgs = routes.map((r: any) => {
          if (r.target === 'CENTRE_DE_COUT') return `Centre de Cout: ${r.montant} DA → ${r.node_code}`;
          if (r.target === 'JURIDIQUE') return `Juridique: ${r.doc_type}`;
          if (r.target === 'RH') return `RH: ${r.employee_name || 'a identifier'}`;
          if (r.target === 'OPERATIONS') return `Operations: ${r.doc_type}`;
          return r.target;
        });
        alert(`Document archive et route:\n\n${msgs.join('\n')}`);
      }
      setConfirming(null);
      setConfirmForm({});
      loadDocs();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const confScore = (field: string) => confirming?.classification?.confidence?.[field] || 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Bibliotheque Documentaire</h1>
        <div className="flex bg-mist rounded-lg p-0.5">
          {[['library','Bibliotheque'],['upload','Upload'],['review',`Revision (${stats.awaiting_review || 0})`]].map(([k,l]) => (
            <button key={k} onClick={() => setTab(k as any)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${tab === k ? 'bg-iris text-white' : 'text-storm'}`}>{l}</button>
          ))}
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
          <p className="text-xs text-storm">Total</p><p className="text-xl font-bold">{stats.total || 0}</p>
        </div>
        <div className="bg-white rounded-card border border-mint p-4 shadow-card text-center">
          <p className="text-xs text-storm">Archives</p><p className="text-xl font-bold text-mint">{stats.archived || 0}</p>
        </div>
        <div className="bg-white rounded-card border border-honey p-4 shadow-card text-center">
          <p className="text-xs text-storm">En revision</p><p className="text-xl font-bold text-[#E17055]">{stats.awaiting_review || 0}</p>
        </div>
        <div className="bg-white rounded-card border border-coral p-4 shadow-card text-center">
          <p className="text-xs text-storm">Quarantaine</p><p className="text-xl font-bold text-coral">{stats.quarantine || 0}</p>
        </div>
      </div>

      {/* ═══ UPLOAD TAB ═══ */}
      {tab === 'upload' && (
        <div className="space-y-6 mb-6">
          {/* Context hint */}
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="font-semibold mb-3">Ingestion de documents</h2>
            <p className="text-xs text-storm mb-3">L'IA analyse, classifie et archive automatiquement chaque fichier. Plusieurs modes d'injection disponibles.</p>
            <label className="text-xs font-medium text-storm block mb-1">Contexte global (optionnel — aide l'IA a classifier)</label>
            <input value={contextHint} onChange={e => setContextHint(e.target.value)}
              className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
              placeholder="Ex: Dossier projet principal 2024, factures fournisseurs beton, plans architecte phase APD..." />
          </div>

          {/* 3 injection modes */}
          <div className="grid grid-cols-3 gap-4">
            {/* Mode 1: Single file */}
            <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card">
              <h3 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-7 h-7 rounded-full bg-iris text-white text-xs flex items-center justify-center font-bold">1</span>
                Fichier unique
              </h3>
              <p className="text-xs text-storm mb-3">Un seul document a analyser immediatement.</p>
              <div className="border-2 border-dashed border-mist rounded-lg p-4 text-center hover:border-iris transition cursor-pointer"
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); }}
                onClick={() => document.getElementById('dis-single')?.click()}>
                <input id="dis-single" type="file" className="hidden" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])} />
                <p className="text-xl mb-1">📄</p>
                <p className="text-xs font-medium">Glisser ou cliquer</p>
              </div>
            </div>

            {/* Mode 2: Multi-file batch */}
            <div className="bg-white rounded-card border-2 border-ocean p-6 shadow-card">
              <h3 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-7 h-7 rounded-full bg-ocean text-white text-xs flex items-center justify-center font-bold">2</span>
                Lot de fichiers
              </h3>
              <p className="text-xs text-storm mb-3">Selectionnez plusieurs fichiers — chacun sera traite individuellement.</p>
              <div className="border-2 border-dashed border-mist rounded-lg p-4 text-center hover:border-ocean transition cursor-pointer"
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleBatchFiles(e.dataTransfer.files); }}
                onClick={() => document.getElementById('dis-batch')?.click()}>
                <input id="dis-batch" type="file" multiple className="hidden" onChange={e => e.target.files && handleBatchFiles(e.target.files)} />
                <p className="text-xl mb-1">📁</p>
                <p className="text-xs font-medium">Multi-selection</p>
              </div>
            </div>

            {/* Mode 3: Google Drive */}
            <div className="bg-white rounded-card border-2 border-mint p-6 shadow-card">
              <h3 className="font-semibold mb-2 flex items-center gap-2">
                <span className="w-7 h-7 rounded-full bg-mint text-white text-xs flex items-center justify-center font-bold">3</span>
                Google Drive
              </h3>
              <p className="text-xs text-storm mb-3">Connectez un dossier Drive complet — scan recursif de tous les fichiers.</p>
              <input value={driveFolder} onChange={e => setDriveFolder(e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2 text-xs font-mono focus:border-mint outline-none mb-2"
                placeholder="ID du dossier Drive (ex: 1abc...xyz)" />
              <button onClick={ingestDrive} disabled={!driveFolder || uploading}
                className="w-full py-2 bg-mint text-white rounded-button text-xs font-medium hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                Scanner le Drive
              </button>
            </div>
          </div>

          {/* Batch progress */}
          {batchQueue.length > 0 && (
            <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold">Progression du lot ({batchDone}/{batchQueue.length})</h3>
                <span className="text-xs text-storm">{Math.round(batchDone / batchQueue.length * 100)}%</span>
              </div>
              <div className="bg-mist rounded-full h-3 mb-4">
                <div className="bg-iris h-full rounded-full transition-all duration-300" style={{ width: `${batchDone / batchQueue.length * 100}%` }} />
              </div>
              <div className="grid grid-cols-4 gap-2 mb-3">
                <div className="text-center"><p className="text-[10px] text-storm">Total</p><p className="font-bold">{batchQueue.length}</p></div>
                <div className="text-center"><p className="text-[10px] text-storm">Archives</p><p className="font-bold text-mint">{batchResults.filter(r => r.status === 'ARCHIVED').length}</p></div>
                <div className="text-center"><p className="text-[10px] text-storm">En revision</p><p className="font-bold text-[#E17055]">{batchResults.filter(r => r.status === 'AWAITING_REVIEW').length}</p></div>
                <div className="text-center"><p className="text-[10px] text-storm">Erreurs</p><p className="font-bold text-coral">{batchResults.filter(r => r.status === 'ERROR' || r.status === 'DUPLICATE').length}</p></div>
              </div>
              <div className="max-h-40 overflow-y-auto space-y-1">
                {batchResults.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Badge variant={r.status === 'ARCHIVED' ? 'success' : r.status === 'AWAITING_REVIEW' ? 'warning' : r.status === 'DUPLICATE' ? 'info' : 'error'}>
                      {r.status === 'DUPLICATE' ? 'DOUBLON' : r.status}
                    </Badge>
                    <span className="truncate flex-1">{r.filename}</span>
                    {r.canonical_path && <span className="font-mono text-storm truncate max-w-[200px]">{r.canonical_path}</span>}
                    {r.processing_ms && <span className="text-storm">{r.processing_ms}ms</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Single upload result */}
          {uploadResult && batchQueue.length === 0 && (
            <div className={`rounded-lg p-4 ${
              uploadResult.status === 'ARCHIVED' ? 'bg-[rgba(0,184,148,0.08)] border border-mint' :
              uploadResult.status === 'AWAITING_REVIEW' ? 'bg-[rgba(253,203,110,0.08)] border border-honey' :
              uploadResult.status === 'DUPLICATE' ? 'bg-[rgba(9,132,227,0.08)] border border-ocean' :
              'bg-[rgba(255,107,107,0.08)] border border-coral'}`}>
              <Badge variant={uploadResult.status === 'ARCHIVED' ? 'success' : uploadResult.status === 'DUPLICATE' ? 'info' : uploadResult.status === 'AWAITING_REVIEW' ? 'warning' : 'error'}>
                {uploadResult.status === 'DUPLICATE' ? 'DOUBLON' : uploadResult.status}
              </Badge>
              {uploadResult.status === 'ARCHIVED' && (
                <div className="mt-2">
                  <p className="text-sm font-medium text-mint">Archive automatiquement en {uploadResult.processing_ms}ms</p>
                  <p className="text-xs font-mono text-storm mt-1">{uploadResult.canonical_path}</p>
                  {uploadResult.classification?.resume && <p className="text-sm mt-2">{uploadResult.classification.resume}</p>}
                </div>
              )}
              {uploadResult.status === 'AWAITING_REVIEW' && (
                <div className="mt-2">
                  <p className="text-sm font-medium text-[#E17055]">{uploadResult.message}</p>
                  <p className="text-xs text-storm mt-1">Champs incertains: {Object.keys(uploadResult.low_fields || {}).join(', ')}</p>
                  <button onClick={() => { setConfirming(uploadResult); setConfirmForm(uploadResult.classification || {}); }}
                    className="mt-2 px-4 py-2 bg-iris text-white rounded-button text-sm font-medium">Ouvrir le formulaire</button>
                </div>
              )}
              {uploadResult.status === 'DUPLICATE' && (
                <div className="mt-2">
                  <p className="text-sm">{uploadResult.message}</p>
                  <p className="text-xs font-mono text-storm mt-1">{uploadResult.existing_path}</p>
                </div>
              )}
              {uploadResult.status === 'ERROR' && <p className="text-sm text-coral mt-2">{uploadResult.message}</p>}
            </div>
          )}
        </div>
      )}

      {/* ═══ REVIEW QUEUE TAB ═══ */}
      {tab === 'review' && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-6">
          <h2 className="font-semibold mb-4">File de revision ({reviewQueue.length} documents)</h2>
          {reviewQueue.length === 0 ? (
            <p className="text-sm text-storm text-center py-8">Aucun document en attente de revision</p>
          ) : (
            <div className="space-y-2">
              {reviewQueue.map(d => (
                <div key={d.id} onClick={() => {
                  api.get(`/dis/${d.id}`).then(r => {
                    const doc = r.data.data;
                    setConfirming({ id: d.id, classification: doc });
                    setConfirmForm(doc);
                  });
                }}
                  className="flex items-center gap-4 p-3 rounded-lg border border-mist hover:border-iris cursor-pointer transition">
                  <Badge variant={STATUS_V[d.status] || 'neutral'}>{d.status}</Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{d.filename}</p>
                    <p className="text-xs text-storm">{d.resume?.slice(0, 80) || 'Pas de resume'}</p>
                  </div>
                  <div className="flex gap-1">
                    {Object.entries(d.low_fields || {}).map(([k, v]) => (
                      <span key={k} className="text-[9px] bg-[rgba(255,107,107,0.1)] text-coral px-1.5 py-0.5 rounded">{k}: {((v as number) * 100).toFixed(0)}%</span>
                    ))}
                  </div>
                  <span className="text-xs text-storm">{d.ingested_at?.slice(0, 10)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ LIBRARY TAB ═══ */}
      {tab === 'library' && (
        <>
          {/* Filters */}
          <div className="flex gap-2 mb-4 flex-wrap">
            <input value={filters.q} onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && loadDocs()} placeholder="Recherche texte..."
              className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none w-64" />
            <select value={filters.entite} onChange={e => setFilters(f => ({ ...f, entite: e.target.value }))}
              className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
              <option value="">Toutes entites</option>{ENTITES.map(e => <option key={e}>{e}</option>)}
            </select>
            <select value={filters.projet} onChange={e => setFilters(f => ({ ...f, projet: e.target.value }))}
              className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
              <option value="">Tous projets</option>{PROJETS.map(p => <option key={p} value={p}>{PROJECT_LABELS[p] || p}</option>)}
            </select>
            <select value={filters.doc_type} onChange={e => setFilters(f => ({ ...f, doc_type: e.target.value }))}
              className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
              <option value="">Tous types</option>{DOC_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <select value={filters.annee} onChange={e => setFilters(f => ({ ...f, annee: e.target.value }))}
              className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
              <option value="">Toutes annees</option>
              {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(y => (
                <option key={y} value={String(y)}>{y}</option>
              ))}
            </select>
            <button onClick={loadDocs} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium">Rechercher</button>
          </div>

          {/* Results */}
          <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
                <th className="py-2 px-3 text-left text-storm font-medium">Type</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Fichier</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Entite</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Projet</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Tiers</th>
                <th className="py-2 px-3 text-right text-storm font-medium">Montant</th>
                <th className="py-2 px-3 text-center text-storm font-medium">Annee</th>
                <th className="py-2 px-3 text-center text-storm font-medium">Statut</th>
              </tr></thead>
              <tbody>
                {docs.length === 0 ? (
                  <tr><td colSpan={8} className="py-8 text-center text-storm">{loading ? 'Chargement...' : 'Aucun document'}</td></tr>
                ) : docs.map(d => (
                  <tr key={d.id} className="border-b border-mist hover:bg-[#FAFAFA] cursor-pointer" onClick={() => setSelected(d)}>
                    <td className="py-2 px-3"><Badge variant="info">{(d.doc_type || 'AUTRE').replace(/_/g, ' ').slice(0, 15)}</Badge></td>
                    <td className="py-2 px-3">
                      <p className="text-sm font-medium truncate max-w-[200px]">{d.filename}</p>
                      {d.resume && <p className="text-[10px] text-storm truncate max-w-[200px]">{d.resume}</p>}
                    </td>
                    <td className="py-2 px-3 text-xs">{d.entite}</td>
                    <td className="py-2 px-3 text-xs">{displayProjectName(d.projet)}</td>
                    <td className="py-2 px-3 text-xs truncate max-w-[120px]">{d.tiers || '-'}</td>
                    <td className="py-2 px-3 text-right font-mono text-xs">{d.montant_da ? formatDA(d.montant_da) : '-'}</td>
                    <td className="py-2 px-3 text-center text-xs">{d.annee || '-'}</td>
                    <td className="py-2 px-3 text-center"><Badge variant={STATUS_V[d.status] || 'neutral'}>{d.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ═══ CONFIRMATION MODAL ═══ */}
      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[4px]" onClick={() => setConfirming(null)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-[1100px] max-h-[90vh] overflow-y-auto p-8">
            <h2 className="text-xl font-bold mb-1">Classification — Validation requise</h2>
            <p className="text-sm text-storm mb-4">Verifiez le document et corrigez les champs avant archivage. Le document sera automatiquement route vers les modules concernes.</p>

            {/* Document preview + form side by side */}
            <div className="grid grid-cols-5 gap-6 mb-6">
              {/* LEFT: Document preview */}
              <div className="col-span-2 space-y-3">
                <p className="text-xs font-medium text-storm">Apercu du document</p>
                {/* File preview iframe/image */}
                <div className="border border-mist rounded-lg overflow-hidden bg-[#FAFAFA]" style={{ height: 400 }}>
                  {confirming.id && (() => {
                    const mime = confirming.classification?.mime_type || confirming.mime_type || '';
                    const isImage = mime.startsWith('image/') || /\.(jpg|jpeg|png|webp)$/i.test(confirming.classification?.filename || confirming.filename || '');
                    const isPdf = mime === 'application/pdf' || /\.pdf$/i.test(confirming.classification?.filename || confirming.filename || '');
                    const previewUrl = `/api/v1/dis/${confirming.id}/preview`;
                    if (isImage) {
                      return <img src={previewUrl} alt="Document" className="w-full h-full object-contain" />;
                    } else if (isPdf) {
                      return <iframe src={previewUrl} className="w-full h-full" title="PDF preview" />;
                    } else {
                      return (
                        <div className="flex flex-col items-center justify-center h-full text-storm">
                          <div className="text-4xl mb-2">&#128196;</div>
                          <p className="text-sm">{confirming.classification?.filename || confirming.filename}</p>
                          <a href={previewUrl} target="_blank" rel="noreferrer" className="text-xs text-iris hover:underline mt-2">Telecharger pour voir</a>
                        </div>
                      );
                    }
                  })()}
                </div>
                {/* Extracted text */}
                {(confirming.extracted_text_preview || confirming.classification?.raw_text_excerpt) && (
                  <div>
                    <p className="text-xs font-medium text-storm flex items-center gap-2 mb-1">
                      Texte extrait
                      <span className="text-[9px] bg-iris text-white px-1.5 py-0.5 rounded">AI OCR</span>
                    </p>
                    <div className="border border-mist rounded-lg bg-white p-3 max-h-32 overflow-y-auto text-[11px] font-mono text-storm whitespace-pre-wrap leading-relaxed">
                      {confirming.extracted_text_preview || confirming.classification?.raw_text_excerpt}
                    </div>
                  </div>
                )}
              </div>

              {/* RIGHT: Classification form */}
              <div className="col-span-3">

            <div className="grid grid-cols-2 gap-4 mb-6">
              {/* doc_type */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">
                  Type de document <span className="text-coral">*</span>
                  <ConfBadge score={confScore('doc_type')} />
                </label>
                <select value={confirmForm.doc_type || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, doc_type: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
                  <option value="">Selectionner...</option>{DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              {/* entite */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">
                  Entite legale <span className="text-coral">*</span>
                  <ConfBadge score={confScore('entite')} />
                </label>
                <select value={confirmForm.entite || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, entite: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
                  <option value="">Selectionner...</option>{ENTITES.map(e => <option key={e}>{e}</option>)}
                </select>
              </div>
              {/* projet */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">
                  Projet <span className="text-coral">*</span>
                  <ConfBadge score={confScore('projet')} />
                </label>
                <select value={confirmForm.projet || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, projet: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
                  <option value="">Selectionner...</option>{PROJETS.map(p => <option key={p} value={p}>{PROJECT_LABELS[p] || p}</option>)}
                </select>
              </div>
              {/* annee */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">
                  Annee <span className="text-coral">*</span>
                  <ConfBadge score={confScore('annee')} />
                </label>
                <input type="number" value={confirmForm.annee || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, annee: parseInt(e.target.value) || null }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="2024" />
              </div>
              {/* reference */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">Reference doc <ConfBadge score={confScore('reference_doc')} /></label>
                <input value={confirmForm.reference_doc || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, reference_doc: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="FAC-2024-001" />
              </div>
              {/* tiers */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">Tiers <ConfBadge score={confScore('tiers')} /></label>
                <input value={confirmForm.tiers || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, tiers: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="BATIMETAL SARL" />
              </div>
              {/* montant */}
              <div>
                <label className="text-xs font-medium text-storm flex items-center gap-2 mb-1">Montant DA <ConfBadge score={confScore('montant_da')} /></label>
                <input type="number" value={confirmForm.montant_da || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, montant_da: parseFloat(e.target.value) || null }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm font-mono focus:border-iris outline-none" placeholder="4850000" />
              </div>
              {/* mois */}
              <div>
                <label className="text-xs font-medium text-storm mb-1 block">Mois</label>
                <select value={confirmForm.mois || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, mois: parseInt(e.target.value) || null }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
                  <option value="">Non renseigne</option>{Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
                </select>
              </div>
            </div>

            {/* Resume */}
            <div className="mb-3">
              <label className="text-xs font-medium text-storm mb-1 block">Resume</label>
              <textarea value={confirmForm.resume || ''} onChange={e => setConfirmForm((f: any) => ({ ...f, resume: e.target.value }))} rows={2}
                className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none" />
            </div>

            {/* Routing info */}
            <div className="bg-[#EDE7F6] border border-iris rounded-lg p-3 mb-3 text-xs text-storm">
              Ce document sera automatiquement route vers :
              {confirmForm.doc_type && (() => {
                const routes = [];
                const dt = confirmForm.doc_type;
                if (['FACTURE_FOURNISSEUR','FACTURE_CLIENT','SITUATION_TRAVAUX','BON_COMMANDE','ACCORD_PRET','FICHE_PAIE'].includes(dt) && confirmForm.montant_da)
                  routes.push('Centre de Cout (' + confirmForm.entite + ')');
                if (['CONTRAT','AVENANT_CONTRAT','ACTE_NOTARIE','PERMIS_AUTORISATION'].includes(dt))
                  routes.push('Module Juridique');
                if (dt === 'FICHE_PAIE') routes.push('Dossier RH employe');
                if (['PV_RECEPTION','PV_CHANTIER','PLAN_TECHNIQUE'].includes(dt)) routes.push('Operations');
                return routes.length > 0
                  ? <strong> {routes.join(' + ')}</strong>
                  : <span> archivage uniquement (pas de routage automatique)</span>;
              })()}
            </div>

              </div>{/* close col-span-3 */}
            </div>{/* close grid */}

            {/* Actions */}
            <div className="flex gap-3">
              <button onClick={confirmDoc}
                disabled={!confirmForm.doc_type || !confirmForm.entite || !confirmForm.projet || !confirmForm.annee}
                className="flex-1 py-3 bg-mint text-white rounded-button font-semibold text-sm hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                Confirmer et archiver
              </button>
              <button onClick={() => { api.patch(`/dis/${confirming.id}/draft`, confirmForm); setConfirming(null); loadDocs(); }}
                className="px-6 py-3 border border-mist rounded-button text-sm text-storm hover:bg-gray-50">Brouillon</button>
              <button onClick={() => { setConfirming(null); }} className="px-6 py-3 text-sm text-storm hover:underline">Fermer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfBadge({ score }: { score: number }) {
  if (!score) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 85 ? 'bg-mint' : pct >= 65 ? 'bg-honey' : 'bg-coral';
  return <span className={`${color} text-white text-[9px] font-bold px-1.5 py-0.5 rounded`}>{pct}%</span>;
}
