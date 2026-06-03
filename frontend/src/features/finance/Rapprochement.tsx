import { useEffect, useState } from 'react';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function Rapprochement() {
  const [mode, setMode] = useState<'bank' | 'journal'>('bank');
  const [statements, setStatements] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);
  // Upload state
  const [uploading, setUploading] = useState(false);
  const [bankName, setBankName] = useState('BNA');
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [uploadResult, setUploadResult] = useState<any>(null);
  // Matching
  const [matching, setMatching] = useState(false);
  const [matchResult, setMatchResult] = useState<any>(null);

  const loadStatements = () => {
    api.get('/finance/rapprochement/statements').then(r => { setStatements(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { loadStatements(); }, []);

  const loadDetail = (id: string) => {
    api.get(`/finance/rapprochement/${id}`).then(r => { setDetail(r.data.data); setSelected(id); }).catch(() => {});
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('bank_name', bankName);
      form.append('period', period);
      const res = await api.post('/finance/rapprochement/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadResult(res.data.data);
      loadStatements();
      if (res.data.data.statement_id) loadDetail(res.data.data.statement_id);
    } catch (err: any) {
      setUploadResult({ error: err.response?.data?.detail || 'Erreur' });
    } finally {
      setUploading(false);
    }
  };

  const autoMatch = async () => {
    if (!selected) return;
    setMatching(true);
    try {
      const res = await api.post(`/finance/rapprochement/${selected}/auto-match`);
      setMatchResult(res.data.data);
      loadDetail(selected);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erreur rapprochement');
    } finally {
      setMatching(false);
    }
  };

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Rapprochement Comptable</h1>
        <div className="flex gap-2">
          <button onClick={() => setMode('bank')} className={`px-4 py-2 rounded-button text-sm font-medium ${mode === 'bank' ? 'bg-iris text-white' : 'border border-mist text-storm'}`}>
            Bancaire
          </button>
          <button onClick={() => setMode('journal')} className={`px-4 py-2 rounded-button text-sm font-medium ${mode === 'journal' ? 'bg-iris text-white' : 'border border-mist text-storm'}`}>
            Ecritures ↔ Documents
          </button>
        </div>
      </div>

      {/* ═══ JOURNAL ↔ DOCUMENT MATCHING ═══ */}
      {mode === 'journal' && <JournalDocMatch />}

      {/* ═══ BANK MATCHING ═══ */}
      {mode === 'bank' && <div className="grid grid-cols-3 gap-6">
        {/* Left: Upload + Statements list */}
        <div className="space-y-4">
          {/* Upload form */}
          <div className="bg-white rounded-card border border-mist p-4 shadow-card space-y-3">
            <h3 className="font-semibold text-sm">Importer un releve bancaire</h3>
            <p className="text-xs text-storm">CSV: date,reference,label,debit,credit,balance</p>
            <div className="grid grid-cols-2 gap-2">
              <input type="text" value={bankName} onChange={e => setBankName(e.target.value)} placeholder="Banque" className="border border-mist rounded-input px-3 py-2 text-sm" />
              <input type="month" value={period} onChange={e => setPeriod(e.target.value)} className="border border-mist rounded-input px-3 py-2 text-sm" />
            </div>
            <label className="border-2 border-dashed border-mist rounded-lg p-4 text-center cursor-pointer block hover:border-iris transition text-sm">
              {uploading ? 'Import...' : 'Choisir CSV'}
              <input type="file" className="hidden" accept=".csv" onChange={handleUpload} disabled={uploading} />
            </label>
            {uploadResult && !uploadResult.error && (
              <div className="bg-[rgba(85,239,196,0.1)] rounded-lg p-2 text-xs text-mint">{uploadResult.movements} mouvements importes</div>
            )}
          </div>

          {/* Statements list */}
          <div className="space-y-2">
            {statements.map(s => (
              <div key={s.id} onClick={() => loadDetail(s.id)}
                className={`bg-white rounded-card border p-3 cursor-pointer hover:shadow-md transition ${selected === s.id ? 'border-iris' : 'border-mist'}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold">{s.bank} — {s.period}</span>
                  <Badge variant={s.status === 'RECONCILED' ? 'success' : s.status === 'RECONCILING' ? 'warning' : 'neutral'}>{s.status}</Badge>
                </div>
                <div className="text-xs text-storm">{s.movements} mouvements — {s.matched} rapproches</div>
                <div className="bg-mist rounded-full h-1.5 mt-1"><div className="bg-mint h-full rounded-full" style={{ width: `${s.movements > 0 ? (s.matched / s.movements) * 100 : 0}%` }} /></div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Statement detail */}
        <div className="col-span-2">
          {!detail ? (
            <div className="bg-white rounded-card border border-mist p-12 text-center text-storm">Selectionnez un releve ou importez-en un nouveau</div>
          ) : (
            <div className="space-y-4">
              {/* Header + auto-match */}
              <div className="bg-white rounded-card border border-mist p-4 shadow-card flex items-center justify-between">
                <div>
                  <h2 className="font-bold">{detail.bank} — {detail.period}</h2>
                  <p className="text-xs text-storm">{detail.movements_count} mouvements — {detail.matched_count} rapproches</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={autoMatch} disabled={matching}
                    className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist">
                    {matching ? 'Rapprochement...' : 'Rapprochement automatique'}
                  </button>
                </div>
              </div>
              {matchResult && (
                <div className="bg-[rgba(85,239,196,0.1)] border border-mint rounded-lg p-3 text-sm text-mint">
                  {matchResult.matched} mouvement(s) rapproche(s) automatiquement sur {matchResult.total_movements}
                </div>
              )}

              {/* Movements table */}
              <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
                <table className="w-full text-sm">
                  <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                    <th className="py-2 px-3 text-left text-storm">Date</th>
                    <th className="py-2 px-3 text-left text-storm">Libelle</th>
                    <th className="py-2 px-3 text-left text-storm">Reference</th>
                    <th className="py-2 px-3 text-right text-storm">Debit</th>
                    <th className="py-2 px-3 text-right text-storm">Credit</th>
                    <th className="py-2 px-3 text-left text-storm">Statut</th>
                    <th className="py-2 px-3 text-left text-storm">Rapproche avec</th>
                  </tr></thead>
                  <tbody>
                    {(detail.movements || []).map((m: any) => (
                      <tr key={m.id} className={`border-b border-mist ${m.reconciled ? 'bg-[rgba(85,239,196,0.03)]' : 'hover:bg-[#FAFAFA]'}`}>
                        <td className="py-2 px-3 text-xs font-mono">{m.date}</td>
                        <td className="py-2 px-3 text-xs">{m.label}</td>
                        <td className="py-2 px-3 text-xs font-mono">{m.reference || '-'}</td>
                        <td className="py-2 px-3 text-right font-mono">{parseFloat(m.debit) > 0 ? formatDA(m.debit) : ''}</td>
                        <td className="py-2 px-3 text-right font-mono">{parseFloat(m.credit) > 0 ? formatDA(m.credit) : ''}</td>
                        <td className="py-2 px-3">
                          <Badge variant={m.reconciled ? 'success' : 'error'}>
                            {m.reconciled ? `${m.match_method} ${m.match_confidence}%` : 'NON RAPPROCHE'}
                          </Badge>
                        </td>
                        <td className="py-2 px-3 text-xs">
                          {m.payment_info ? (
                            <span className="text-mint">{m.payment_info.dossier} — {m.payment_info.client} — {formatDA(m.payment_info.montant)}</span>
                          ) : m.reconciled ? (
                            <span className="text-storm">Paiement {m.matched_payment_id?.slice(0, 8)}</span>
                          ) : (
                            <span className="text-coral">A rapprocher</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Journal ↔ Document Matching Component
// ═══════════════════════════════════════════════════════════════════════════════

function JournalDocMatch() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [matching, setMatching] = useState(false);
  const [matchResult, setMatchResult] = useState<any>(null);

  const load = () => {
    setLoading(true);
    api.get(`/finance/journal-rapprochement?period=${period}`).then(r => {
      setData(r.data.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, [period]);

  const autoMatch = async () => {
    setMatching(true);
    setMatchResult(null);
    try {
      const res = await api.post(`/finance/journal-rapprochement/auto-match?period=${period}`);
      setMatchResult(res.data.data);
      load();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erreur');
    } finally {
      setMatching(false);
    }
  };

  if (loading) return <div className="h-32 bg-mist rounded-card animate-pulse" />;

  const entries = data?.entries || [];
  const matchedCount = entries.filter((e: any) => e.has_document).length;
  const unmatchedCount = entries.filter((e: any) => !e.has_document).length;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex gap-3 items-center">
          <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
            className="border border-mist rounded-input px-4 py-2 text-sm focus:border-iris outline-none" />
          <span className="text-sm text-storm">{entries.length} ecritures</span>
        </div>
        <button onClick={autoMatch} disabled={matching || unmatchedCount === 0}
          className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
          {matching ? 'Rapprochement AI...' : `Rapprocher ${unmatchedCount} ecriture(s) par AI`}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-card border border-mist p-3"><p className="text-xs text-storm">Total ecritures</p><p className="text-lg font-bold">{entries.length}</p></div>
        <div className="bg-white rounded-card border border-mint p-3"><p className="text-xs text-storm">Avec justificatif</p><p className="text-lg font-bold text-mint">{matchedCount}</p></div>
        <div className="bg-white rounded-card border border-coral p-3"><p className="text-xs text-storm">Sans justificatif</p><p className="text-lg font-bold text-coral">{unmatchedCount}</p></div>
      </div>

      {/* Progress bar */}
      <div className="bg-mist rounded-full h-2">
        <div className="bg-mint h-full rounded-full" style={{ width: `${entries.length > 0 ? (matchedCount / entries.length * 100) : 0}%` }} />
      </div>

      {/* AI match result */}
      {matchResult && (
        <div className="bg-[rgba(85,239,196,0.1)] border border-mint rounded-lg p-4 text-sm space-y-2">
          <p className="font-medium text-mint">{matchResult.matched} ecriture(s) rapprochee(s) par AI</p>
          {matchResult.match_details?.map((m: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <Badge variant="success">{m.confidence}%</Badge>
              <span className="font-mono">{m.entry}</span>
              <span className="text-storm">→</span>
              <span>{m.document}</span>
              <span className="text-storm">({m.reason})</span>
            </div>
          ))}
          {matchResult.ai_notes && <p className="text-xs text-storm">{matchResult.ai_notes}</p>}
        </div>
      )}

      {/* Entries table */}
      <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-3 text-left text-storm">N Ecriture</th>
            <th className="py-2 px-3 text-left text-storm">Date</th>
            <th className="py-2 px-3 text-left text-storm">Libelle</th>
            <th className="py-2 px-3 text-right text-storm">Debit</th>
            <th className="py-2 px-3 text-right text-storm">Credit</th>
            <th className="py-2 px-3 text-left text-storm">Justificatif</th>
          </tr></thead>
          <tbody>
            {entries.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-storm">Aucune ecriture pour cette periode</td></tr>
            ) : entries.map((e: any) => (
              <tr key={e.id} className={`border-b border-mist ${e.has_document ? 'bg-[rgba(85,239,196,0.03)]' : 'hover:bg-[#FAFAFA]'}`}>
                <td className="py-2 px-3 font-mono text-xs">{e.number}</td>
                <td className="py-2 px-3 text-xs">{e.date}</td>
                <td className="py-2 px-3">{e.label}</td>
                <td className="py-2 px-3 text-right font-mono">{parseFloat(e.total_debit) > 0 ? formatDA(e.total_debit) : ''}</td>
                <td className="py-2 px-3 text-right font-mono">{parseFloat(e.total_credit) > 0 ? formatDA(e.total_credit) : ''}</td>
                <td className="py-2 px-3">
                  {e.has_document ? (
                    <div className="flex items-center gap-1">
                      <Badge variant="success">Justifie</Badge>
                      <span className="text-xs text-storm truncate max-w-[150px]">{e.document?.filename}</span>
                    </div>
                  ) : (
                    <Badge variant="error">Manquant</Badge>
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
