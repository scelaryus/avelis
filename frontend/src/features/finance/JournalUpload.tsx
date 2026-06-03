import { useEffect, useState } from 'react';
import { formatDA, rfLabel } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function JournalUpload() {
  const [tab, setTab] = useState<'entries' | 'import'>('entries');
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [detail, setDetail] = useState<any>(null);

  // Import flow: upload → AI → review → confirm
  const [importStep, setImportStep] = useState<'upload' | 'analyzing' | 'review' | 'done'>('upload');
  const [journalCode, setJournalCode] = useState('OD');
  const [entityCode, setEntityCode] = useState('');
  const [aiData, setAiData] = useState<any>(null);
  const [aiEntries, setAiEntries] = useState<any[]>([]);
  const [importError, setImportError] = useState('');
  const [importResult, setImportResult] = useState<any>(null);

  const loadEntries = () => {
    setLoading(true);
    api.get(`/finance/journal/entries?period=${period}`).then(r => {
      setEntries(r.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };
  useEffect(() => { loadEntries(); }, [period]);

  // Upload file → AI reads it
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportStep('analyzing');
    setImportError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/finance/journal/read-document', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      const d = res.data.data;
      setAiData(d);
      if (d.error) setImportError(d.error);
      setAiEntries((d.entries || []).map((e: any, i: number) => ({ ...e, _idx: i, _include: true })));
      if (d.journal_type) setJournalCode(d.journal_type);
      setImportStep('review');
    } catch (err: any) {
      setImportError(err.response?.data?.detail || 'Erreur analyse');
      setImportStep('upload');
    }
  };

  const updateEntry = (idx: number, field: string, value: any) => {
    setAiEntries(prev => prev.map(e => e._idx === idx ? { ...e, [field]: value } : e));
  };

  const toggleEntry = (idx: number) => {
    setAiEntries(prev => prev.map(e => e._idx === idx ? { ...e, _include: !e._include } : e));
  };

  const confirmImport = async () => {
    const selected = aiEntries.filter(e => e._include);
    if (selected.length === 0) return;
    try {
      const res = await api.post('/finance/journal/import-ai', {
        journal_code: journalCode,
        entity_code: entityCode,
        entries: selected.map(e => ({
          date: e.date, account: e.account, debit: parseFloat(e.debit) || 0,
          credit: parseFloat(e.credit) || 0, label: e.label, tiers: e.tiers, reference: e.reference,
        })),
      });
      setImportResult(res.data.data);
      setImportStep('done');
      loadEntries();
    } catch (err: any) {
      setImportError(err.response?.data?.detail || 'Erreur import');
    }
  };

  const totalDebit = aiEntries.filter(e => e._include).reduce((s, e) => s + (parseFloat(e.debit) || 0), 0);
  const totalCredit = aiEntries.filter(e => e._include).reduce((s, e) => s + (parseFloat(e.credit) || 0), 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Journal Comptable</h1>
        <div className="flex gap-2">
          <button onClick={() => setTab('entries')} className={`px-4 py-2 rounded-button text-sm font-medium ${tab === 'entries' ? 'bg-iris text-white' : 'border border-mist text-storm'}`}>Ecritures</button>
          <button onClick={() => { setTab('import'); setImportStep('upload'); setAiData(null); setAiEntries([]); setImportResult(null); setImportError(''); }}
            className={`px-4 py-2 rounded-button text-sm font-medium ${tab === 'import' ? 'bg-iris text-white' : 'border border-mist text-storm'}`}>Importer (AI)</button>
        </div>
      </div>

      {/* ═══ ENTRIES TAB ═══ */}
      {tab === 'entries' && (
        <div>
          <div className="flex gap-3 mb-4">
            <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
              className="border border-mist rounded-input px-4 py-2 text-sm focus:border-iris outline-none" />
            <span className="self-center text-sm text-storm">{entries.length} ecritures</span>
          </div>
          {loading ? <div className="h-32 bg-mist rounded-card animate-pulse" /> : (
            <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                  <th className="py-2 px-3 text-left text-storm">N Piece</th>
                  <th className="py-2 px-3 text-left text-storm">Date</th>
                  <th className="py-2 px-3 text-left text-storm">Journal</th>
                  <th className="py-2 px-3 text-left text-storm">Entite</th>
                  <th className="py-2 px-3 text-left text-storm">Libelle</th>
                  <th className="py-2 px-3 text-right text-storm">Debit</th>
                  <th className="py-2 px-3 text-right text-storm">Credit</th>
                  <th className="py-2 px-3 text-left text-storm">Justif.</th>
                </tr></thead>
                <tbody>
                  {entries.length === 0 ? <tr><td colSpan={8} className="py-6 text-center text-storm">Aucune ecriture pour cette periode</td></tr> :
                    entries.map((e: any) => (
                      <tr key={e.id} className="border-b border-mist hover:bg-[#FAFAFA] cursor-pointer" onClick={() => setDetail(e)}>
                        <td className="py-2 px-3 font-mono text-xs text-iris font-bold">{e.number}</td>
                        <td className="py-2 px-3 text-xs">{e.date}</td>
                        <td className="py-2 px-3"><Badge variant="neutral">{e.journal}</Badge></td>
                        <td className="py-2 px-3 text-xs">{e.entity}</td>
                        <td className="py-2 px-3">{e.label}</td>
                        <td className="py-2 px-3 text-right font-mono font-bold">{formatDA(e.total_debit)}</td>
                        <td className="py-2 px-3 text-right font-mono font-bold">{formatDA(e.total_credit)}</td>
                        <td className="py-2 px-3">
                          {e.has_justificatif ? <Badge variant="success">Oui</Badge> : <Badge variant="warning">Non</Badge>}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══ IMPORT TAB ═══ */}
      {tab === 'import' && (
        <div>
          {importError && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{importError}</div>}

          {/* Step 1: Upload */}
          {importStep === 'upload' && (
            <div className="max-w-xl space-y-4">
              <div className="bg-white rounded-card border border-mist p-6 shadow-card space-y-4">
                <p className="text-sm text-storm">Uploadez un fichier comptable — l'IA extrait les ecritures quel que soit le format.</p>
                <p className="text-xs text-storm">Formats acceptes: CSV, Excel-like, PDF, image de journal, scan de balance — colonnes en francais ou arabe, noms variables.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-storm block mb-1">Code journal</label>
                    <select value={journalCode} onChange={e => setJournalCode(e.target.value)} className="w-full border border-mist rounded-input px-3 py-2 text-sm">
                      <option value="HA">HA — Achats</option>
                      <option value="VT">VT — Ventes</option>
                      <option value="BQ">BQ — Banque</option>
                      <option value="CA">CA — Caisse</option>
                      <option value="OD">OD — Operations diverses</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-storm block mb-1">Entite</label>
                    <input type="text" value={entityCode} onChange={e => setEntityCode(e.target.value)}
                      className="w-full border border-mist rounded-input px-3 py-2 text-sm" placeholder="ETS-DK, SARL-DP..." />
                  </div>
                </div>
                <label className="border-2 border-dashed border-iris rounded-lg p-8 text-center cursor-pointer block hover:bg-[rgba(108,92,231,0.03)] transition">
                  <div className="text-4xl mb-2">&#128196;</div>
                  <p className="text-sm font-medium">Choisir un fichier</p>
                  <p className="text-xs text-storm mt-1">CSV, PDF, image (JPG/PNG) — francais ou arabe</p>
                  <input type="file" className="hidden" accept=".csv,.txt,.tsv,.pdf,.jpg,.jpeg,.png,.webp,.xlsx" onChange={handleUpload} />
                </label>
              </div>
            </div>
          )}

          {/* Step 2: Analyzing */}
          {importStep === 'analyzing' && (
            <div className="bg-white rounded-card border border-mist p-12 text-center">
              <div className="w-12 h-12 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-sm font-medium">Analyse du document comptable...</p>
              <p className="text-xs text-storm mt-1">L'IA identifie les comptes, montants, dates et tiers</p>
            </div>
          )}

          {/* Step 3: Review */}
          {importStep === 'review' && (
            <div className="space-y-4">
              {/* AI summary */}
              {aiData && (
                <div className={`flex items-center gap-3 p-3 rounded-lg text-sm ${
                  (aiData.confidence || 0) >= 80 ? 'bg-[rgba(85,239,196,0.1)] border border-mint' :
                  (aiData.confidence || 0) >= 50 ? 'bg-[#FFF8E1] border border-honey' :
                  'bg-[rgba(255,107,107,0.08)] border border-coral'
                }`}>
                  <Badge variant={(aiData.confidence || 0) >= 80 ? 'success' : 'warning'}>{aiData.confidence || 0}%</Badge>
                  <span>{aiData.total_entries} ligne(s) extraites — {aiData.balanced ? 'Equilibre OK' : 'DESEQUILIBRE'}</span>
                  {aiData.journal_type && <Badge variant="neutral">{aiData.journal_type}</Badge>}
                </div>
              )}
              {aiData?.notes && <p className="text-xs text-storm bg-[#FAFAFA] rounded-lg p-2">{aiData.notes}</p>}

              {/* Balance check */}
              <div className={`flex items-center justify-between p-3 rounded-lg text-sm ${balanced ? 'bg-[rgba(85,239,196,0.05)] border border-mint' : 'bg-[rgba(255,107,107,0.08)] border border-coral'}`}>
                <span>Total Debit: <span className="font-mono font-bold">{formatDA(totalDebit)}</span></span>
                <span>Total Credit: <span className="font-mono font-bold">{formatDA(totalCredit)}</span></span>
                <Badge variant={balanced ? 'success' : 'error'}>{balanced ? 'Equilibre' : `Ecart: ${formatDA(Math.abs(totalDebit - totalCredit))}`}</Badge>
              </div>

              {/* Entries table */}
              <div className="bg-white rounded-card border border-mist shadow-card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                    <th className="py-2 px-2 w-8"></th>
                    <th className="py-2 px-2 text-left text-storm">Date</th>
                    <th className="py-2 px-2 text-left text-storm">Compte</th>
                    <th className="py-2 px-2 text-right text-storm">Debit</th>
                    <th className="py-2 px-2 text-right text-storm">Credit</th>
                    <th className="py-2 px-2 text-left text-storm">Libelle</th>
                    <th className="py-2 px-2 text-left text-storm">Tiers</th>
                    <th className="py-2 px-2 text-left text-storm">Ref</th>
                  </tr></thead>
                  <tbody>
                    {aiEntries.map(e => (
                      <tr key={e._idx} className={`border-b border-mist ${e._include ? '' : 'opacity-40'}`}>
                        <td className="py-1.5 px-2"><input type="checkbox" checked={e._include} onChange={() => toggleEntry(e._idx)} /></td>
                        <td className="py-1.5 px-2"><input type="text" value={e.date || ''} onChange={ev => updateEntry(e._idx, 'date', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-24 font-mono" /></td>
                        <td className="py-1.5 px-2"><input type="text" value={e.account || ''} onChange={ev => updateEntry(e._idx, 'account', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-14 font-mono" /></td>
                        <td className="py-1.5 px-2"><input type="number" value={e.debit || ''} onChange={ev => updateEntry(e._idx, 'debit', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-24 font-mono text-right" /></td>
                        <td className="py-1.5 px-2"><input type="number" value={e.credit || ''} onChange={ev => updateEntry(e._idx, 'credit', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-24 font-mono text-right" /></td>
                        <td className="py-1.5 px-2"><input type="text" value={e.label || ''} onChange={ev => updateEntry(e._idx, 'label', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-40" /></td>
                        <td className="py-1.5 px-2"><input type="text" value={e.tiers || ''} onChange={ev => updateEntry(e._idx, 'tiers', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-28" /></td>
                        <td className="py-1.5 px-2"><input type="text" value={e.reference || ''} onChange={ev => updateEntry(e._idx, 'reference', ev.target.value)} className="border border-mist rounded px-1 py-0.5 text-xs w-20 font-mono" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex gap-3">
                <button onClick={() => { setImportStep('upload'); setAiEntries([]); }}
                  className="px-6 py-3 border border-mist rounded-button text-sm text-storm">Recommencer</button>
                <button onClick={confirmImport} disabled={aiEntries.filter(e => e._include).length === 0}
                  className="flex-1 py-3 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist">
                  Importer {aiEntries.filter(e => e._include).length} ligne(s) dans {journalCode}
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Done */}
          {importStep === 'done' && importResult && (
            <div className="bg-white rounded-card border border-mint p-8 text-center space-y-3">
              <div className="text-5xl">&#10003;</div>
              <h2 className="text-xl font-bold">{importResult.entries_created} ecriture(s) importee(s)</h2>
              <p className="text-sm text-storm">Journal {importResult.journal} — Entite {importResult.entity}</p>
              {importResult.errors?.length > 0 && (
                <div className="text-xs text-coral">{importResult.errors.join('; ')}</div>
              )}
              <div className="flex gap-3 justify-center">
                <button onClick={() => { setTab('entries'); loadEntries(); }} className="px-4 py-2 bg-iris text-white rounded-button text-sm">Voir les ecritures</button>
                <button onClick={() => { setImportStep('upload'); setAiEntries([]); setImportResult(null); }}
                  className="px-4 py-2 border border-iris text-iris rounded-button text-sm">Importer un autre</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Entry detail modal */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setDetail(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[600px] shadow-xl max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-1">{detail.number}</h3>
            <div className="grid grid-cols-2 gap-3 text-sm mb-4">
              <div><span className="text-storm">Date:</span> <span className="font-medium">{detail.date}</span></div>
              <div><span className="text-storm">Journal:</span> <span className="font-medium">{detail.journal} — {detail.journal_label}</span></div>
              <div><span className="text-storm">Entite:</span> <span className="font-medium">{detail.entity}</span></div>
              <div><span className="text-storm">Exercice:</span> <span className="font-medium">{detail.exercice}</span></div>
              <div className="col-span-2"><span className="text-storm">Libelle:</span> <span className="font-medium">{detail.label}</span></div>
              <div><span className="text-storm">Justificatif:</span> {detail.has_justificatif ? <Badge variant="success">Lie</Badge> : <Badge variant="warning">Aucun</Badge>}</div>
              <div><span className="text-storm">Source:</span> <span className="text-xs font-mono">{detail.source_type || '-'}</span></div>
            </div>
            <table className="w-full text-sm mb-4">
              <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                <th className="py-2 px-3 text-left">Compte</th>
                <th className="py-2 px-3 text-left">Intitule compte</th>
                <th className="py-2 px-3 text-left">Libelle</th>
                <th className="py-2 px-3 text-right">Debit</th>
                <th className="py-2 px-3 text-right">Credit</th>
                <th className="py-2 px-3 text-left">Tiers</th>
              </tr></thead>
              <tbody>
                {(detail.lines || []).map((l: any, i: number) => (
                  <tr key={i} className="border-b border-mist">
                    <td className="py-2 px-3 font-mono font-bold">{l.account}</td>
                    <td className="py-2 px-3 text-xs text-storm">{l.account_label}</td>
                    <td className="py-2 px-3">{l.label}</td>
                    <td className="py-2 px-3 text-right font-mono">{parseFloat(l.debit) > 0 ? formatDA(l.debit) : ''}</td>
                    <td className="py-2 px-3 text-right font-mono">{parseFloat(l.credit) > 0 ? formatDA(l.credit) : ''}</td>
                    <td className="py-2 px-3 text-xs">{l.tiers || ''}</td>
                  </tr>
                ))}
                <tr className="bg-[#FAFAFA] font-bold">
                  <td colSpan={3} className="py-2 px-3 text-right">Totaux</td>
                  <td className="py-2 px-3 text-right font-mono">{formatDA(detail.total_debit)}</td>
                  <td className="py-2 px-3 text-right font-mono">{formatDA(detail.total_credit)}</td>
                  <td></td>
                </tr>
              </tbody>
            </table>
            <button onClick={() => setDetail(null)} className="w-full py-2 border border-mist rounded-button text-sm text-storm">Fermer</button>
          </div>
        </div>
      )}
    </div>
  );
}
