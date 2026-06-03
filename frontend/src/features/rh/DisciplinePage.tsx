import { useState, useEffect } from 'react';
import { Badge } from '../../components/ui/Badge';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

const SEV_V: Record<string, 'error'|'warning'|'info'> = { GRAVE: 'error', MOYENNE: 'warning', MINEURE: 'info' };
const SANC_V: Record<string, 'error'|'warning'|'info'|'success'|'neutral'> = {
  LICENCIEMENT: 'error', MISE_A_PIED: 'error', BLAME: 'warning', AVERTISSEMENT: 'info', CLASSEE_SANS_SUITE: 'success',
};
const STATUS_LABELS: Record<string, string> = {
  PV_CONSTAT: 'PV Constat', EN_ATTENTE_DECISION: 'En attente decision', CLOTURE: 'Cloture',
};
const SANCTIONS = [
  { value: 'AVERTISSEMENT', label: 'Avertissement (ecrit)', desc: 'Premier niveau — notification formelle' },
  { value: 'BLAME', label: 'Blame', desc: 'Deuxieme niveau — inscrit au dossier' },
  { value: 'MISE_A_PIED', label: 'Mise a pied', desc: 'Suspension temporaire sans salaire' },
  { value: 'LICENCIEMENT', label: 'Licenciement', desc: 'Rupture du contrat pour faute' },
  { value: 'CLASSEE_SANS_SUITE', label: 'Classee sans suite', desc: 'Aucune sanction — dossier ferme' },
];

export function DisciplinePage() {
  const [cases, setCases] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmployee, setSelectedEmployee] = useState<string | null>(null);
  const [employeeHistory, setEmployeeHistory] = useState<any>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  // Detail modal
  const [detailCase, setDetailCase] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // Decision form
  const [decidingSanction, setDecidingSanction] = useState('');
  const [decidingDuration, setDecidingDuration] = useState('');
  const [decidingComment, setDecidingComment] = useState('');
  const [deciding, setDeciding] = useState(false);
  // New case form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ employee_id: '', description: '', severity: 'MOYENNE', infraction_date: new Date().toISOString().slice(0, 10), infraction_location: '', witnesses: '' });
  const [proofIds, setProofIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<any>(null);

  const reload = () => {
    setLoading(true);
    Promise.all([
      api.get('/agents/drh/discipline/cases'),
      api.get('/drh/employees'),
    ]).then(([cR, eR]) => {
      setCases(cR.data.data || []);
      setEmployees(eR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const loadHistory = async (empId: string) => {
    setHistoryLoading(true); setSelectedEmployee(empId);
    try { const r = await api.get(`/agents/drh/discipline/employee/${empId}/history`); setEmployeeHistory(r.data.data); }
    catch { setEmployeeHistory(null); }
    finally { setHistoryLoading(false); }
  };

  const openDetail = async (caseId: string) => {
    setDetailLoading(true);
    try { const r = await api.get(`/agents/drh/discipline/cases/${caseId}`); setDetailCase(r.data.data); setDecidingSanction(r.data.data.ai_sanction_suggested || ''); }
    catch { alert('Erreur chargement'); }
    finally { setDetailLoading(false); }
  };

  const submitDecision = async () => {
    if (!detailCase || !decidingSanction) return;
    setDeciding(true);
    try {
      await api.patch(`/agents/drh/discipline/cases/${detailCase.id}/decide`, {
        sanction: decidingSanction, duration_days: decidingDuration ? parseInt(decidingDuration) : null,
        comment: decidingComment, validated_by_drh: true,
      });
      setDetailCase(null); setDecidingSanction(''); setDecidingComment(''); setDecidingDuration('');
      reload();
      if (selectedEmployee) loadHistory(selectedEmployee);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setDeciding(false); }
  };

  const submitCase = async () => {
    setSubmitting(true); setSubmitResult(null);
    try {
      const r = await api.post('/agents/drh/discipline/cases', {
        ...form, witnesses: form.witnesses ? form.witnesses.split(',').map(w => w.trim()) : [],
        evidence_document_ids: proofIds.length > 0 ? proofIds : ['proof-placeholder'],
      });
      setSubmitResult(r.data.data); setShowForm(false);
      setForm({ employee_id: '', description: '', severity: 'MOYENNE', infraction_date: new Date().toISOString().slice(0, 10), infraction_location: '', witnesses: '' });
      setProofIds([]); reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setSubmitting(false); }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  const byEmployee: Record<string, any[]> = {};
  cases.forEach(c => { (byEmployee[c.employee_id] = byEmployee[c.employee_id] || []).push(c); });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Dossiers Disciplinaires</h1>
          <p className="text-sm text-storm">{cases.length} infractions — {Object.keys(byEmployee).length} employes concernes</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-coral text-white rounded-button text-sm font-semibold hover:bg-[#E55555]">+ Signaler une infraction</button>
      </div>

      {/* AI result */}
      {submitResult && (
        <div className="bg-[rgba(108,92,231,0.06)] border border-iris rounded-card p-4 mb-6">
          <span className="text-xs font-bold text-white bg-iris px-2 py-0.5 rounded">AGENT IA</span>
          <span className="ml-2 text-sm">Gravite: <Badge variant={SEV_V[submitResult.ai_severity] || 'neutral'}>{submitResult.ai_severity}</Badge></span>
          <span className="ml-2 text-sm">Sanction: <Badge variant={SANC_V[submitResult.ai_sanction_suggested] || 'neutral'}>{submitResult.ai_sanction_suggested?.replace(/_/g, ' ')}</Badge></span>
          {submitResult.ai_justification && <p className="text-xs text-storm mt-1">{submitResult.ai_justification}</p>}
          <button onClick={() => setSubmitResult(null)} className="text-xs text-iris ml-4 hover:underline">Fermer</button>
        </div>
      )}

      {/* New case form */}
      {showForm && (
        <div className="bg-white rounded-card border-2 border-coral p-6 shadow-card mb-6 space-y-4">
          <h2 className="font-semibold">Signalement — PV de constat (F-DIS-001)</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Employe <span className="text-coral">*</span></label>
              <select value={form.employee_id} onChange={e => setForm(f => ({ ...f, employee_id: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                <option value="">Selectionner</option>
                {employees.map((e: any) => <option key={e.id} value={e.id}>{e.name} — {e.matricule}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Date</label>
                <input type="date" value={form.infraction_date} onChange={e => setForm(f => ({ ...f, infraction_date: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
              </div>
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Gravite</label>
                <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                  <option value="MINEURE">Mineure</option><option value="MOYENNE">Moyenne</option><option value="GRAVE">Grave</option>
                </select>
              </div>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-storm block mb-1">Description <span className="text-coral">*</span> (min 50 car.)</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={3}
              className="w-full border border-mist rounded-input px-4 py-3 text-sm focus:border-iris outline-none resize-none"
              placeholder="Decrivez les faits: date, heure, circonstances, temoins..." />
            <p className="text-xs text-storm mt-1">{form.description.length}/50</p>
          </div>
          <ProofUpload onUploaded={id => setProofIds(prev => [...prev, id])} label="Preuves (PV, photos)" />
          <div className="flex gap-3">
            <button onClick={submitCase} disabled={!form.employee_id || form.description.length < 50 || submitting}
              className="px-6 py-2.5 bg-coral text-white rounded-button text-sm font-semibold disabled:bg-mist disabled:text-silver">
              {submitting ? 'Evaluation IA...' : 'Enregistrer'}
            </button>
            <button onClick={() => setShowForm(false)} className="px-6 py-2.5 border border-mist rounded-button text-sm text-storm">Annuler</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-5 gap-6">
        {/* Left: employees */}
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
          <h2 className="font-semibold mb-3">Employes</h2>
          <div className="space-y-1 max-h-[600px] overflow-y-auto">
            {employees.map((emp: any) => {
              const ec = byEmployee[emp.id] || [];
              return (
                <div key={emp.id} onClick={() => loadHistory(emp.id)}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition ${selectedEmployee === emp.id ? 'bg-[rgba(108,92,231,0.06)] border border-iris' : 'hover:bg-[#FAFAFA] border border-transparent'}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold ${ec.length === 0 ? 'bg-mint' : ec.length <= 1 ? 'bg-honey' : 'bg-coral'}`}>{ec.length}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{emp.name}</p>
                    <p className="text-[10px] text-storm">{emp.matricule}</p>
                  </div>
                  {ec.length === 0 && <Badge variant="success">Clean</Badge>}
                  {ec.length >= 3 && <Badge variant="error">Recidive</Badge>}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: history */}
        <div className="col-span-3">
          {historyLoading ? <div className="h-40 bg-mist rounded-card animate-pulse" /> :
           employeeHistory ? (
            <div className="space-y-4">
              {/* Summary */}
              <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-bold">{employeeHistory.employee.name}</h2>
                  <Badge variant={employeeHistory.summary.risk_level === 'CRITIQUE' ? 'error' : employeeHistory.summary.risk_level === 'ALERTE' ? 'warning' : 'success'}>
                    {employeeHistory.summary.risk_level}
                  </Badge>
                </div>
                <div className="grid grid-cols-5 gap-2 text-center text-xs">
                  <div className="p-2 rounded bg-[#FAFAFA]"><p className="text-storm">Total</p><p className="text-lg font-bold">{employeeHistory.summary.total}</p></div>
                  <div className="p-2 rounded bg-[rgba(9,132,227,0.06)]"><p className="text-storm">Avert.</p><p className="text-lg font-bold text-ocean">{employeeHistory.summary.avertissements}</p></div>
                  <div className="p-2 rounded bg-[rgba(253,203,110,0.06)]"><p className="text-storm">Blames</p><p className="text-lg font-bold text-[#E17055]">{employeeHistory.summary.blames}</p></div>
                  <div className="p-2 rounded bg-[rgba(255,107,107,0.06)]"><p className="text-storm">M. a pied</p><p className="text-lg font-bold text-coral">{employeeHistory.summary.mises_a_pied}</p></div>
                  <div className="p-2 rounded bg-[rgba(0,184,148,0.06)]"><p className="text-storm">Classees</p><p className="text-lg font-bold text-mint">{employeeHistory.summary.classees}</p></div>
                </div>
              </div>

              {/* Cases — clickable */}
              {employeeHistory.cases.length === 0 ? (
                <div className="bg-white rounded-card border border-mint p-8 shadow-card text-center">
                  <p className="text-mint font-semibold">Dossier vierge</p>
                </div>
              ) : employeeHistory.cases.map((c: any) => (
                <div key={c.id} onClick={() => openDetail(c.id)}
                  className={`bg-white rounded-card border-l-4 p-4 shadow-card cursor-pointer hover:shadow-card-hover transition ${
                    c.sanction_applied === 'MISE_A_PIED' || c.sanction_applied === 'LICENCIEMENT' ? 'border-l-coral' :
                    c.sanction_applied === 'BLAME' ? 'border-l-[#E17055]' :
                    c.sanction_applied === 'AVERTISSEMENT' ? 'border-l-ocean' : 'border-l-mint'} border border-[#E0E0E0]`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-storm">{c.infraction_date}</span>
                      <Badge variant={SEV_V[c.severity_declared] || 'neutral'}>{c.severity_declared}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {c.sanction_applied ? (
                        <Badge variant={SANC_V[c.sanction_applied] || 'neutral'}>{c.sanction_applied.replace(/_/g, ' ')}{c.sanction_duration_days ? ` (${c.sanction_duration_days}j)` : ''}</Badge>
                      ) : (
                        <Badge variant="warning">EN ATTENTE DECISION</Badge>
                      )}
                      <span className="text-xs text-iris font-medium">Voir detail &rarr;</span>
                    </div>
                  </div>
                  <p className="text-sm">{c.description}</p>
                  <p className="text-[10px] text-storm mt-1">Signale par: {c.reported_by} | Statut: {c.status}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-card border border-mist p-12 shadow-card text-center text-storm">
              Selectionnez un employe
            </div>
          )}
        </div>
      </div>

      {/* ═══ DETAIL MODAL ═══ */}
      {detailCase && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[4px]" onClick={() => setDetailCase(null)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-[800px] max-h-[90vh] overflow-y-auto p-8">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold">Dossier Disciplinaire</h2>
                <p className="text-sm text-storm">{detailCase.employee?.name} — {detailCase.employee?.matricule}</p>
                <p className="text-xs text-storm">Infractions totales: {detailCase.employee_total_infractions}</p>
              </div>
              <button onClick={() => setDetailCase(null)} className="text-storm hover:text-charcoal text-xl">&times;</button>
            </div>

            {/* Infraction details */}
            <div className="bg-[#FAFAFA] rounded-lg p-4 mb-4">
              <h3 className="text-sm font-semibold mb-2">Infraction</h3>
              <div className="grid grid-cols-3 gap-3 mb-2 text-xs">
                <div><span className="text-storm">Date:</span> <strong>{detailCase.infraction_date}</strong></div>
                <div><span className="text-storm">Heure:</span> <strong>{detailCase.infraction_time || '—'}</strong></div>
                <div><span className="text-storm">Lieu:</span> <strong>{detailCase.infraction_location || '—'}</strong></div>
              </div>
              <p className="text-sm mb-2">{detailCase.description}</p>
              <div className="flex gap-2">
                <Badge variant={SEV_V[detailCase.severity_declared] || 'neutral'}>Gravite: {detailCase.severity_declared}</Badge>
                <span className="text-xs text-storm">Signale par: {detailCase.reported_by}</span>
              </div>
              {detailCase.witnesses?.length > 0 && (
                <p className="text-xs text-storm mt-2">Temoins: {detailCase.witnesses.join(', ')}</p>
              )}
            </div>

            {/* Evidence — clickable with preview */}
            {detailCase.evidence_document_ids?.length > 0 && (
              <div className="bg-[#FAFAFA] rounded-lg p-4 mb-4">
                <h3 className="text-sm font-semibold mb-2">Pieces justificatives ({detailCase.evidence_document_ids.length})</h3>
                <div className="space-y-2">
                  {detailCase.evidence_document_ids.map((docId: string, i: number) => (
                    <div key={i} className="flex items-center gap-3 bg-white border border-mist rounded-lg p-3 hover:border-iris transition">
                      <div className="w-10 h-10 rounded-lg bg-[rgba(225,112,85,0.1)] flex items-center justify-center text-lg flex-shrink-0">
                        {docId.endsWith('.pdf') ? '📄' : docId.endsWith('.jpg') || docId.endsWith('.png') ? '🖼️' : '📎'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">Preuve #{i + 1}</p>
                        <p className="text-xs font-mono text-storm truncate">{docId}</p>
                      </div>
                      <a href={`/api/v1/dis/${docId}`} target="_blank" rel="noopener"
                        className="px-3 py-1.5 bg-iris text-white text-xs rounded-button font-medium hover:bg-rose-800">
                        Voir
                      </a>
                      <a href={`/api/v1/dis/${docId}/preview`} target="_blank" rel="noopener"
                        className="px-3 py-1.5 border border-mist text-xs rounded-button text-storm hover:bg-gray-50">
                        Telecharger
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {(!detailCase.evidence_document_ids || detailCase.evidence_document_ids.length === 0) && (
              <div className="bg-[rgba(255,107,107,0.06)] rounded-lg p-4 mb-4 text-center">
                <p className="text-sm text-coral font-medium">Aucune piece justificative jointe</p>
                <p className="text-xs text-storm">Les preuves doivent etre ajoutees au dossier</p>
              </div>
            )}

            {/* AI evaluation — FULL text, no truncation */}
            <div className="bg-[rgba(108,92,231,0.06)] rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-white bg-iris px-2 py-0.5 rounded">EVALUATION IA</span>
                {detailCase.ai_evaluated_at && <span className="text-[10px] text-storm">{detailCase.ai_evaluated_at?.slice(0, 19)}</span>}
              </div>
              <div className="flex gap-4 mb-3">
                <div><span className="text-xs text-storm">Gravite confirmee:</span> <Badge variant={SEV_V[detailCase.ai_severity] || 'neutral'}>{detailCase.ai_severity}</Badge></div>
                <div><span className="text-xs text-storm">Sanction recommandee:</span> <Badge variant={SANC_V[detailCase.ai_sanction_suggested] || 'neutral'}>{detailCase.ai_sanction_suggested?.replace(/_/g, ' ')}</Badge></div>
              </div>
              {detailCase.ai_justification && (
                <div className="bg-white rounded-lg p-3 border border-mist">
                  <p className="text-xs font-semibold text-storm mb-1">Analyse et justification:</p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{detailCase.ai_justification}</p>
                </div>
              )}
              {detailCase.circonstances_aggravantes?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-coral">Circonstances aggravantes:</p>
                  <ul className="text-xs text-storm">{detailCase.circonstances_aggravantes.map((c: string, i: number) => <li key={i}>- {c}</li>)}</ul>
                </div>
              )}
              {detailCase.circonstances_attenuantes?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-mint">Circonstances attenuantes:</p>
                  <ul className="text-xs text-storm">{detailCase.circonstances_attenuantes.map((c: string, i: number) => <li key={i}>- {c}</li>)}</ul>
                </div>
              )}
              {detailCase.recommandation_complementaire && (
                <p className="text-xs text-iris mt-2 font-medium">Recommandation: {detailCase.recommandation_complementaire}</p>
              )}
            </div>

            {/* Workflow timeline */}
            {(detailCase.convocation_date || detailCase.audition_date) && (
              <div className="bg-[#FAFAFA] rounded-lg p-4 mb-4">
                <h3 className="text-sm font-semibold mb-2">Procedure</h3>
                {detailCase.convocation_date && <p className="text-xs">Convocation: {detailCase.convocation_date}</p>}
                {detailCase.audition_date && <p className="text-xs">Audition: {detailCase.audition_date}</p>}
                {detailCase.audition_pv && <p className="text-xs mt-1">PV: {detailCase.audition_pv}</p>}
              </div>
            )}

            {/* Current decision or decision form */}
            {detailCase.status === 'CLOTURE' ? (
              <div className={`rounded-lg p-4 mb-4 border-2 ${SANC_V[detailCase.sanction_applied] === 'error' ? 'border-coral bg-[rgba(255,107,107,0.04)]' : SANC_V[detailCase.sanction_applied] === 'success' ? 'border-mint bg-[rgba(0,184,148,0.04)]' : 'border-honey bg-[rgba(253,203,110,0.04)]'}`}>
                <h3 className="text-sm font-semibold mb-2">Decision finale</h3>
                <Badge variant={SANC_V[detailCase.sanction_applied] || 'neutral'}>
                  {detailCase.sanction_applied?.replace(/_/g, ' ')}{detailCase.sanction_duration_days ? ` — ${detailCase.sanction_duration_days} jours` : ''}
                </Badge>
                {detailCase.sanction_comment && <p className="text-sm mt-2">{detailCase.sanction_comment}</p>}
                <p className="text-xs text-storm mt-2">Decide par: {detailCase.sanction_decided_by} le {detailCase.sanction_decided_at?.slice(0, 10)}</p>
              </div>
            ) : (
              <div className="border-2 border-iris rounded-lg p-4 mb-4">
                <h3 className="text-sm font-semibold mb-3">Prendre une decision</h3>
                <div className="space-y-2 mb-3">
                  {SANCTIONS.map(s => (
                    <label key={s.value} className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition ${
                      decidingSanction === s.value ? 'border-iris bg-[rgba(108,92,231,0.04)]' : 'border-mist hover:border-lavender'}`}>
                      <input type="radio" name="sanction" value={s.value} checked={decidingSanction === s.value}
                        onChange={() => setDecidingSanction(s.value)} className="accent-iris" />
                      <div>
                        <p className="text-sm font-medium">{s.label}</p>
                        <p className="text-[10px] text-storm">{s.desc}</p>
                      </div>
                      <Badge variant={SANC_V[s.value] || 'neutral'}>{s.value.replace(/_/g, ' ')}</Badge>
                    </label>
                  ))}
                </div>
                {decidingSanction === 'MISE_A_PIED' && (
                  <div className="mb-3">
                    <label className="text-xs font-medium text-storm block mb-1">Duree de la mise a pied (jours)</label>
                    <input type="number" value={decidingDuration} onChange={e => setDecidingDuration(e.target.value)}
                      className="w-32 border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="3" />
                  </div>
                )}
                <div className="mb-3">
                  <label className="text-xs font-medium text-storm block mb-1">Commentaire du decideur</label>
                  <textarea value={decidingComment} onChange={e => setDecidingComment(e.target.value)} rows={2}
                    className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none"
                    placeholder="Justification de la decision..." />
                </div>
                <button onClick={submitDecision} disabled={!decidingSanction || deciding}
                  className="w-full py-3 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
                  {deciding ? 'Enregistrement...' : 'Valider la decision et cloturer'}
                </button>
              </div>
            )}

            {/* Validations */}
            {(detailCase.validated_by_drh || detailCase.validated_by_dg || detailCase.validated_by_pdg) && (
              <div className="text-xs text-storm space-y-0.5">
                {detailCase.validated_by_drh && <p>DRH: {detailCase.validated_by_drh}</p>}
                {detailCase.validated_by_dg && <p>DG: {detailCase.validated_by_dg}</p>}
                {detailCase.validated_by_pdg && <p>PDG: {detailCase.validated_by_pdg}</p>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
