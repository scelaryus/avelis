import { useEffect, useState, useRef } from 'react';
import { Badge } from '../../components/ui/Badge';
import { formatDate } from '../../lib/format';
import api from '../../lib/api-client';

export function DocumentSearch() {
  const [docs, setDocs] = useState<any[]>([]);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const search = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (typeFilter) params.set('doc_type', typeFilter);
    api.get(`/ged/documents?${params}`).then(r => { setDocs(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { search(); }, []);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadMsg('');
    const form = new FormData();
    form.append('file', files[0]);
    try {
      const res = await api.post('/ged/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadMsg(`Uploade: ${res.data.data?.filename || files[0].name}`);
      search(); // Refresh
    } catch (e: any) {
      setUploadMsg(e.response?.data?.detail || 'Erreur upload');
    } finally {
      setUploading(false);
    }
  };

  const TYPE_ICON: Record<string, string> = {
    facture: '📄', contrat: '📋', pv: '📝', bulletin_paie: '💰',
    acte_notarie: '⚖️', declaration_fiscale: '🏛️', cin: '🪪', statuts: '📜',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Documents GED</h1>
          <p className="text-sm text-storm">{docs.length} documents indexes</p>
        </div>
        <div>
          <input ref={fileRef} type="file" className="hidden" onChange={e => upload(e.target.files)} />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800 disabled:bg-mist">
            {uploading ? 'Upload...' : '+ Uploader un document'}
          </button>
        </div>
      </div>

      {uploadMsg && (
        <div className={`rounded-lg p-3 mb-4 text-sm ${uploadMsg.startsWith('Erreur') || uploadMsg.startsWith('Document duplique') ? 'bg-[rgba(255,107,107,0.08)] text-coral' : 'bg-[rgba(85,239,196,0.08)] text-mint'}`}>
          {uploadMsg}
        </div>
      )}

      <div className="flex gap-3 mb-6">
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="Rechercher (nom, entite, projet)..."
          className="flex-1 border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
          <option value="">Tous types</option>
          {['facture', 'contrat', 'pv', 'bulletin_paie', 'acte_notarie', 'declaration_fiscale', 'cin', 'statuts'].map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={search} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">Rechercher</button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-20 bg-mist rounded-card animate-pulse" />)}</div>
      ) : docs.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <p className="text-3xl mb-2">📂</p>
          <p className="text-storm">Aucun document trouve</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {docs.map(d => (
            <div key={d.id} className="bg-white rounded-card border border-mist p-4 shadow-card hover:shadow-card-hover hover:border-iris transition cursor-pointer">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{TYPE_ICON[d.doc_type] || '📄'}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{d.filename}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {d.doc_type && <Badge variant="info">{d.doc_type}</Badge>}
                    {d.entity && <span className="text-xs text-storm">{d.entity}</span>}
                    {d.project && <span className="text-xs text-iris">{d.project}</span>}
                  </div>
                  <div className="flex items-center justify-between mt-2 text-xs text-storm">
                    <span>{(d.size / 1000).toFixed(0)} Ko</span>
                    <span>{d.date}</span>
                    <Badge variant={d.pipeline_status === 'INDEXED' ? 'success' : 'warning'}>{d.pipeline_status}</Badge>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
