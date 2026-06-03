import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

const TYPES = [
  { value: 'fournisseur', label: 'Fournisseur', desc: 'Contrat d\'achat de biens ou services' },
  { value: 'prestation', label: 'Prestation', desc: 'Contrat de prestation de services (BET, audit, conseil)' },
  { value: 'client', label: 'Client', desc: 'Contrat de vente immobiliere ou commerciale' },
  { value: 'partenariat', label: 'Partenariat', desc: 'Accord de partenariat ou joint-venture' },
  { value: 'confidentialite', label: 'Confidentialite (NDA)', desc: 'Accord de non-divulgation' },
  { value: 'cadre', label: 'Contrat cadre', desc: 'Accord general couvrant plusieurs commandes' },
];

export function ContractCreate() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<any[]>([]);
  const [form, setForm] = useState<any>({
    contract_type: 'fournisseur', title: '', partner_name: '', partner_nif: '', partner_rc: '',
    project_code: '', date_start: '', date_end: '', amount_ht: '', renewal_type: 'manuelle',
  });
  const [proofId, setProofId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [docVerifying, setDocVerifying] = useState(false);
  const [docVerdict, setDocVerdict] = useState<any>(null);
  // AI clause suggestion
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [suggestedClauses, setSuggestedClauses] = useState<any[]>([]);

  useEffect(() => {
    api.get('/foundation/projects?status=ACTIF').then(r => setProjects(r.data.data || [])).catch(() => {});
  }, []);

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  const suggestClauses = async () => {
    setAiSuggesting(true);
    try {
      const r = await api.post('/agents/drh/contrats/generate', {
        employee: { name: form.partner_name },
        contract_type: form.contract_type,
      });
      const data = r.data.data;
      if (data.clauses_principales) {
        setSuggestedClauses(
          (Array.isArray(data.clauses_principales) ? data.clauses_principales : [data.clauses_principales])
            .map((c: any, i: number) => typeof c === 'string' ? { name: `Clause ${i + 1}`, text: c, risk_level: 'low' } : c)
        );
      } else if (data.contract_summary) {
        setSuggestedClauses([{ name: 'Resume', text: data.contract_summary, risk_level: 'low' }]);
      }
    } catch { /* ignore */ }
    finally { setAiSuggesting(false); }
  };

  const submit = async () => {
    if (!form.title || !form.partner_name) { setError('Titre et partenaire obligatoires'); return; }
    setSubmitting(true);
    setError('');
    try {
      const r = await api.post('/juridique/contracts', {
        ...form,
        amount_ht: form.amount_ht ? parseFloat(form.amount_ht) : 0,
        signed_document_id: proofId || null,
      });
      nav('/juridique/contracts');
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erreur creation');
    } finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-3xl">
      <Link to="/juridique/contracts" className="text-sm text-iris hover:underline">&larr; Contrats</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouveau Contrat</h1>

      {error && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{error}</div>}

      <div className="space-y-6">
        {/* Type selection */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-3">Type de contrat</h2>
          <div className="grid grid-cols-3 gap-3">
            {TYPES.map(t => (
              <button key={t.value} onClick={() => set('contract_type', t.value)} type="button"
                className={`p-3 rounded-lg border-2 text-left transition ${form.contract_type === t.value ? 'border-iris bg-[rgba(108,92,231,0.05)]' : 'border-mist hover:border-lavender'}`}>
                <p className="text-sm font-semibold">{t.label}</p>
                <p className="text-[10px] text-storm mt-0.5">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Contract info */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <h2 className="font-semibold">Informations du contrat</h2>
          <div>
            <label className="text-xs font-medium text-storm block mb-1">Titre du contrat <span className="text-coral">*</span></label>
            <input value={form.title} onChange={e => set('title', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
              placeholder="Ex: Gros oeuvre projet principal - GACEB Abderazak" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Partenaire / Cocontractant <span className="text-coral">*</span></label>
              <input value={form.partner_name} onChange={e => set('partner_name', e.target.value)}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                placeholder="Nom complet du partenaire" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Projet lie</label>
              <select value={form.project_code} onChange={e => set('project_code', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                <option value="">Aucun projet specifique</option>
                {projects.map(p => <option key={p.code} value={p.code}>{p.code} - {p.name}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">NIF du partenaire</label>
              <input value={form.partner_nif} onChange={e => set('partner_nif', e.target.value)}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
                placeholder="001612345678901" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Registre de Commerce</label>
              <input value={form.partner_rc} onChange={e => set('partner_rc', e.target.value)}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
                placeholder="16/00-0123456B13" />
              {!form.partner_rc && form.contract_type === 'fournisseur' && (
                <p className="text-[10px] text-coral mt-1">Attention: un fournisseur sans RC declenchera une alerte ALG-RC-FRNR</p>
              )}
            </div>
          </div>
        </div>

        {/* Dates + amounts */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <h2 className="font-semibold">Dates et montants</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Date debut</label>
              <input type="date" value={form.date_start} onChange={e => set('date_start', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Date fin</label>
              <input type="date" value={form.date_end} onChange={e => set('date_end', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Renouvellement</label>
              <select value={form.renewal_type} onChange={e => set('renewal_type', e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                <option value="manuelle">Manuel</option>
                <option value="automatique">Automatique</option>
                <option value="non_renouvelable">Non renouvelable</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-storm block mb-1">Montant HT (DA)</label>
            <input type="number" value={form.amount_ht} onChange={e => set('amount_ht', e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
              placeholder="0" />
            {form.amount_ht && parseFloat(form.amount_ht) > 1000000 && !form.partner_rc && (
              <p className="text-[10px] text-coral mt-1">{"Contrat > 1M DA sans RC: declenchera ALG-DEP-1M + ALG-RC-FRNR"}</p>
            )}
          </div>
        </div>

        {/* AI clause suggestion */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Clauses (optionnel)</h2>
            <button onClick={suggestClauses} disabled={aiSuggesting || !form.contract_type}
              className="px-3 py-1.5 bg-iris text-white rounded text-xs font-medium hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
              {aiSuggesting ? 'Generation IA...' : 'Suggerer des clauses (IA)'}
            </button>
          </div>
          {suggestedClauses.length > 0 && (
            <div className="space-y-2">
              {suggestedClauses.map((c, i) => (
                <div key={i} className="bg-[rgba(108,92,231,0.04)] rounded-lg p-3 border border-lavender/30">
                  <p className="text-xs font-semibold text-iris">{c.name}</p>
                  <p className="text-sm mt-1">{c.text}</p>
                </div>
              ))}
            </div>
          )}
          {suggestedClauses.length === 0 && !aiSuggesting && (
            <p className="text-xs text-storm">Les clauses peuvent etre ajoutees apres creation via la fiche contrat.</p>
          )}
        </div>

        {/* Document upload + AI verification */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-3">Document signe (optionnel)</h2>
          <p className="text-xs text-storm mb-3">Si vous uploadez un document, l'agent IA verifie qu'il correspond au contrat declare.</p>
          <ProofUpload onUploaded={async (id) => {
            setProofId(id);
            setDocVerifying(true);
            setDocVerdict(null);
            try {
              // Get the extracted text from the uploaded document
              let docText = '';
              try {
                const docRes = await api.get(`/dis/${id}`);
                docText = docRes.data.data?.raw_text_excerpt || docRes.data.data?.resume || '';
              } catch { /* doc might not be processed yet */ }

              // Ask the AI to verify the document matches the contract info
              const r = await api.post('/agents/compliance/check', {
                verify_mode: true,
                rule_code: 'DOC_VERIFY',
                correction_data: {
                  document_text: docText,
                  partner_name: form.partner_name,
                  contract_type: form.contract_type,
                  rc_number: form.partner_rc,
                  note: `Verification document pour contrat ${form.contract_type}: ${form.title}. Partenaire: ${form.partner_name}. Montant: ${form.amount_ht || 0} DA.`,
                },
              });
              setDocVerdict(r.data.data);
            } catch {
              setDocVerdict({ verdict: 'WARNING', message: 'Verification IA indisponible. Le document sera archive sans verification.', checks: [] });
            }
            finally { setDocVerifying(false); }
          }} label="Contrat signe (PDF)" />

          {docVerifying && (
            <div className="mt-3 bg-[rgba(108,92,231,0.06)] rounded-lg p-3 flex items-center gap-2">
              <div className="animate-spin w-4 h-4 border-2 border-iris border-t-transparent rounded-full" />
              <span className="text-sm text-iris">L'agent IA analyse le document...</span>
            </div>
          )}
          {docVerdict && !docVerifying && (
            <div className={`mt-3 rounded-lg p-3 border ${
              docVerdict.verdict === 'PASS' ? 'bg-[rgba(0,184,148,0.06)] border-mint' :
              docVerdict.verdict === 'FAIL' ? 'bg-[rgba(255,107,107,0.06)] border-coral' :
              'bg-[rgba(253,203,110,0.06)] border-honey'}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-bold text-white px-2 py-0.5 rounded ${
                  docVerdict.verdict === 'PASS' ? 'bg-mint' : docVerdict.verdict === 'FAIL' ? 'bg-coral' : 'bg-honey'}`}>
                  {docVerdict.verdict}
                </span>
                <span className="text-xs text-storm">Analyse IA du document</span>
              </div>
              <p className="text-sm">{docVerdict.message}</p>
              {docVerdict.checks?.map((c: any, idx: number) => (
                <div key={idx} className="flex items-center gap-2 text-xs mt-1">
                  <span className={c.passed ? 'text-mint' : 'text-coral'}>{c.passed ? '✓' : '✗'}</span>
                  <span>{c.check}: {c.detail}</span>
                </div>
              ))}
              {docVerdict.verdict === 'FAIL' && (
                <p className="text-xs text-coral font-medium mt-2">Le document ne correspond pas au contrat. Verifiez le fichier uploade.</p>
              )}
            </div>
          )}
        </div>

        {/* Submit */}
        <button onClick={submit} disabled={!form.title || !form.partner_name || submitting || (docVerdict?.verdict === 'FAIL')}
          className="w-full py-3.5 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Creation...' : 'Creer le contrat'}
        </button>
      </div>
    </div>
  );
}
