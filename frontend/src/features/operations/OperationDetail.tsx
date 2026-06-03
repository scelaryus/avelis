import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA, formatPct } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, ReferenceLine } from 'recharts';
import api from '../../lib/api-client';

const SRC_COLORS: Record<string, string> = {
  S1_CONTRAT: '#6C5CE7', S2_RH_PAIE: '#0984E3', S4_TRESORERIE: '#00B894',
  S7_STOCK: '#E17055', S8_FLOTTE: '#FDCB6E', S9_IT: '#A29BFE',
  S10_ASSURANCE: '#74B9FF', S11_OVERHEAD: '#636E72',
};
const STAT_V: Record<string, 'success'|'warning'|'error'|'info'|'neutral'> = {
  EN_COURS: 'success', VALIDE: 'info', BROUILLON: 'neutral', SOUMIS: 'warning',
  SUSPENDU: 'error', CLOTURE: 'neutral', ARCHIVE: 'neutral',
};

export function OperationDetail() {
  const { id } = useParams();
  const [op, setOp] = useState<any>(null);
  const [budget, setBudget] = useState<any>(null);
  const [scurve, setScurve] = useState<any>(null);
  const [tab, setTab] = useState<'resume'|'budget'|'planning'|'scurve'>('resume');
  const [loading, setLoading] = useState(true);
  // Forms
  const [showAddTask, setShowAddTask] = useState(false);
  const [taskForm, setTaskForm] = useState({ code_wbs: '', title: '', date_debut: '', date_fin: '', budget: '' });
  const [showAddCost, setShowAddCost] = useState(false);
  const [costForm, setCostForm] = useState({ source_code: 'S9_IT', label: '', amount: '', period: new Date().toISOString().slice(0, 7) });
  const [templates, setTemplates] = useState<any[]>([]);
  const [showDeploy, setShowDeploy] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get(`/operations/${id}`),
      api.get(`/operations/${id}/budget`),
      api.get(`/operations/${id}/planning/s-curve`),
    ]).then(([opR, budR, scR]) => {
      setOp(opR.data.data);
      setBudget(budR.data.data);
      setScurve(scR.data.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!op) return <p className="text-storm">Operation introuvable</p>;

  const transition = async (target: string) => {
    try {
      await api.patch(`/operations/${id}/transition`, { target_status: target });
      window.location.reload();
    } catch (e: any) { alert(e.response?.data?.detail?.message || e.response?.data?.detail || 'Erreur'); }
  };

  const addTask = async () => {
    try {
      await api.post(`/operations/${id}/planning/tasks`, {
        ...taskForm, budget: taskForm.budget ? parseFloat(taskForm.budget) : 0,
      });
      setShowAddTask(false);
      setTaskForm({ code_wbs: '', title: '', date_debut: '', date_fin: '', budget: '' });
      window.location.reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const addCost = async () => {
    try {
      await api.post(`/operations/${id}/budget/manual`, {
        ...costForm, amount: parseFloat(costForm.amount || '0'),
      });
      setShowAddCost(false);
      setCostForm({ source_code: 'S9_IT', label: '', amount: '', period: new Date().toISOString().slice(0, 7) });
      window.location.reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const grantVisa = async () => {
    try {
      await api.patch(`/operations/${id}/visa-tresorier`);
      window.location.reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const deployTemplate = async (categorie: string) => {
    try {
      await api.post(`/operations/${id}/planning/deploy-template`, { categorie });
      setShowDeploy(false);
      window.location.reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const loadTemplates = async () => {
    const r = await api.get('/operations/templates/wbs');
    setTemplates(r.data.data || []);
    setShowDeploy(true);
  };

  return (
    <div>
      <Link to="/operations" className="text-sm text-iris hover:underline">&larr; Operations</Link>

      {/* Header */}
      <div className="flex items-start justify-between mt-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-storm">{op.code}</span>
            <Badge variant={STAT_V[op.status] || 'neutral'}>{op.status}</Badge>
            <Badge variant="info">{op.category}</Badge>
          </div>
          <h1 className="text-2xl font-bold">{op.title}</h1>
          <p className="text-sm text-storm">{op.date_debut} — {op.date_fin_prevue} | Contrat: {formatDA(op.montant_ht)}</p>
        </div>
        <div className="flex gap-2">
          {!op.visa_tresorier && (
            <button onClick={grantVisa} className="px-3 py-2 rounded-button text-sm font-medium bg-mint text-white hover:bg-[#00A884]">
              Accorder visa tresorier
            </button>
          )}
          {(op.transitions || []).map((t: any) => (
            <button key={t.target} onClick={() => !t.blocked && transition(t.target)}
              disabled={t.blocked}
              className={`px-3 py-2 rounded-button text-sm font-medium ${t.blocked ? 'bg-mist text-silver cursor-not-allowed' : 'bg-iris text-white hover:bg-rose-800'}`}
              title={t.blockers?.join('\n')}>
              {t.target}
              {t.blocked && t.blockers?.length > 0 && <span className="ml-1 text-[9px]">({t.blockers.length} blockers)</span>}
            </button>
          ))}
        </div>
      </div>

      {/* RM-25 Alert */}
      {scurve?.rm25_alert && (
        <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-4 mb-6">
          <p className="text-sm text-coral font-bold">RM-25 ALERTE SURPAIEMENT</p>
          <p className="text-sm">{scurve.rm25_message}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[['resume','Resume'],['budget','Budget Agrege'],['planning','Planning'],['scurve','Courbe en S']].map(([k,l]) => (
          <button key={k} onClick={() => setTab(k as any)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === k ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>{l}</button>
        ))}
      </div>

      {/* ═══ RESUME TAB ═══ */}
      {tab === 'resume' && (
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div><p className="text-xs text-storm">Montant HT</p><p className="text-lg font-bold font-mono">{formatDA(op.montant_ht)}</p></div>
              <div><p className="text-xs text-storm">Montant TTC</p><p className="text-lg font-bold font-mono">{formatDA(op.montant_ttc)}</p></div>
              <div><p className="text-xs text-storm">Visa Tresorier</p>
                {op.visa_tresorier ? <Badge variant="success">Valide</Badge> : <Badge variant="warning">En attente</Badge>}
              </div>
            </div>
            {op.notes && <p className="text-sm text-storm">{op.notes}</p>}
            <h3 className="font-semibold mt-4">Planning ({op.tasks?.length || 0} taches)</h3>
            <div className="space-y-1">
              {(op.tasks || []).map((t: any) => (
                <div key={t.id} className={`flex items-center gap-3 p-2 rounded ${t.est_critique ? 'bg-[rgba(255,107,107,0.04)]' : ''}`}>
                  <span className="font-mono text-xs w-8">{t.code_wbs}</span>
                  <span className="flex-1 text-sm">{t.title}</span>
                  <div className="w-24 bg-mist rounded-full h-2"><div className={`h-full rounded-full ${t.avancement >= 100 ? 'bg-mint' : t.avancement > 0 ? 'bg-iris' : 'bg-mist'}`} style={{ width: `${t.avancement}%` }} /></div>
                  <span className="text-xs font-mono w-10 text-right">{t.avancement}%</span>
                  {t.est_critique && <span className="text-[9px] text-coral font-bold">CRIT</span>}
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card text-center">
              <p className="text-xs text-storm">Physique</p>
              <p className={`text-3xl font-bold ${scurve?.physical_pct >= 50 ? 'text-mint' : 'text-iris'}`}>{scurve?.physical_pct}%</p>
            </div>
            <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card text-center">
              <p className="text-xs text-storm">Financier</p>
              <p className={`text-3xl font-bold ${scurve?.surpaiement_risk ? 'text-coral' : 'text-iris'}`}>{scurve?.financial_pct}%</p>
            </div>
            <div className={`bg-white rounded-card border-2 p-5 shadow-card text-center ${scurve?.surpaiement_risk ? 'border-coral' : 'border-mint'}`}>
              <p className="text-xs text-storm">Ecart</p>
              <p className={`text-3xl font-bold ${scurve?.surpaiement_risk ? 'text-coral' : 'text-mint'}`}>{scurve?.gap} pts</p>
            </div>
          </div>
        </div>
      )}

      {/* ═══ BUDGET TAB ═══ */}
      {tab === 'budget' && budget && (
        <div className="space-y-6">
          {/* Manual cost entry */}
          <div className="flex gap-2">
            <button onClick={async () => {
              try {
                await api.post(`/operations/${id}/budget/refresh`);
                window.location.reload();
              } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
            }} className="px-4 py-2 bg-mint text-white rounded-button text-sm font-medium hover:bg-[#00A884]">
              Rafraichir depuis les modules GFI
            </button>
            <button onClick={() => setShowAddCost(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">+ Saisie manuelle (IT/Assurance/Overhead)</button>
          </div>
          <p className="text-xs text-storm">Le bouton "Rafraichir" tire les donnees reelles depuis: Paie (S2), Tresorerie (S4), ADV (S5), Centre de Couts (S6), Stock/GACEB (S7), Flotte (S8), Comptabilite (S3).</p>
          {showAddCost && (
            <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card space-y-3">
              <h3 className="font-semibold">Saisie cout manuel</h3>
              <p className="text-xs text-storm">Pour les sources S9 (IT), S10 (Assurances), S11 (Overhead) uniquement. Les autres sources sont alimentees automatiquement.</p>
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="text-xs font-medium text-storm block mb-1">Source</label>
                  <select value={costForm.source_code} onChange={e => setCostForm(f => ({ ...f, source_code: e.target.value }))}
                    className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
                    <option value="S9_IT">S9 — IT/Licences</option>
                    <option value="S10_ASSURANCE">S10 — Assurances</option>
                    <option value="S11_OVERHEAD">S11 — Overhead</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-storm block mb-1">Libelle</label>
                  <input value={costForm.label} onChange={e => setCostForm(f => ({ ...f, label: e.target.value }))}
                    className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="Licence SCADA annuelle" />
                </div>
                <div>
                  <label className="text-xs font-medium text-storm block mb-1">Montant (DA)</label>
                  <input type="number" value={costForm.amount} onChange={e => setCostForm(f => ({ ...f, amount: e.target.value }))}
                    className="w-full border border-mist rounded-input px-3 py-2 text-sm font-mono focus:border-iris outline-none" placeholder="180000" />
                </div>
                <div>
                  <label className="text-xs font-medium text-storm block mb-1">Periode</label>
                  <input type="month" value={costForm.period} onChange={e => setCostForm(f => ({ ...f, period: e.target.value }))}
                    className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={addCost} disabled={!costForm.amount}
                  className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium disabled:bg-mist disabled:text-silver">Enregistrer</button>
                <button onClick={() => setShowAddCost(false)} className="px-4 py-2 border border-mist rounded-button text-sm text-storm">Annuler</button>
              </div>
            </div>
          )}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
              <p className="text-xs text-storm">Contrat seul</p><p className="text-lg font-bold font-mono">{formatDA(budget.contrat_ht)}</p>
            </div>
            <div className="bg-white rounded-card border border-iris p-4 shadow-card text-center">
              <p className="text-xs text-storm">Budget agrege</p><p className="text-lg font-bold font-mono text-iris">{formatDA(budget.total_prevu)}</p>
            </div>
            <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
              <p className="text-xs text-storm">Reel depense</p><p className="text-lg font-bold font-mono">{formatDA(budget.total_reel)}</p>
            </div>
            <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
              <p className="text-xs text-storm">Angle mort</p><p className="text-lg font-bold text-coral">{budget.blind_spot}%</p>
              <p className="text-[10px] text-storm">Couts non vus si contrat seul</p>
            </div>
          </div>

          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h3 className="font-semibold mb-4">Budget par source ({budget.sources?.length} sources)</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={budget.sources} layout="vertical">
                <XAxis type="number" tickFormatter={v => `${(v/1000000).toFixed(0)}M`} tick={{ fontSize: 11, fill: '#636E72' }} />
                <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => formatDA(v)} />
                <Bar dataKey="prevu" fill="#DFE6E9" name="Prevu" />
                <Bar dataKey="reel" name="Reel">
                  {(budget.sources || []).map((s: any, i: number) => (
                    <Cell key={i} fill={SRC_COLORS[s.code] || '#636E72'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
                <th className="py-2 px-4 text-left text-storm font-medium">Source</th>
                <th className="py-2 px-4 text-right text-storm font-medium">Prevu</th>
                <th className="py-2 px-4 text-right text-storm font-medium">Reel</th>
                <th className="py-2 px-4 text-right text-storm font-medium">Ecart</th>
                <th className="py-2 px-4 text-center text-storm font-medium">Methode</th>
              </tr></thead>
              <tbody>
                {(budget.sources || []).map((s: any) => (
                  <tr key={s.code} className="border-b border-mist">
                    <td className="py-2 px-4"><span className="w-2 h-2 rounded-full inline-block mr-2" style={{ background: SRC_COLORS[s.code] || '#636E72' }} />{s.label}</td>
                    <td className="py-2 px-4 text-right font-mono">{formatDA(s.prevu)}</td>
                    <td className="py-2 px-4 text-right font-mono font-bold">{formatDA(s.reel)}</td>
                    <td className={`py-2 px-4 text-right font-mono ${parseFloat(s.ecart_pct) > 0 ? 'text-coral' : 'text-mint'}`}>{s.ecart_pct > 0 ? '+' : ''}{s.ecart_pct}%</td>
                    <td className="py-2 px-4 text-center text-xs text-storm">{s.methode}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ PLANNING TAB ═══ */}
      {tab === 'planning' && (
        <div className="space-y-4">
        {/* Action buttons */}
        <div className="flex gap-2">
          <button onClick={() => setShowAddTask(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">+ Ajouter une tache</button>
          <button onClick={loadTemplates} className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-[rgba(108,92,231,0.05)]">Deployer un template WBS</button>
        </div>

        {/* Add task form */}
        {showAddTask && (
          <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card space-y-3">
            <h3 className="font-semibold">Nouvelle tache</h3>
            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Code WBS</label>
                <input value={taskForm.code_wbs} onChange={e => setTaskForm(f => ({ ...f, code_wbs: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="1.1" />
              </div>
              <div className="col-span-3">
                <label className="text-xs font-medium text-storm block mb-1">Titre <span className="text-coral">*</span></label>
                <input value={taskForm.title} onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="Terrassement fondations" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Debut prevu</label>
                <input type="date" value={taskForm.date_debut} onChange={e => setTaskForm(f => ({ ...f, date_debut: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" />
              </div>
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Fin prevue</label>
                <input type="date" value={taskForm.date_fin} onChange={e => setTaskForm(f => ({ ...f, date_fin: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" />
              </div>
              <div>
                <label className="text-xs font-medium text-storm block mb-1">Budget (DA)</label>
                <input type="number" value={taskForm.budget} onChange={e => setTaskForm(f => ({ ...f, budget: e.target.value }))}
                  className="w-full border border-mist rounded-input px-3 py-2 text-sm font-mono focus:border-iris outline-none" placeholder="5000000" />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={addTask} disabled={!taskForm.title}
                className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium disabled:bg-mist disabled:text-silver">Ajouter</button>
              <button onClick={() => setShowAddTask(false)} className="px-4 py-2 border border-mist rounded-button text-sm text-storm">Annuler</button>
            </div>
          </div>
        )}

        {/* Deploy template modal */}
        {showDeploy && (
          <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card">
            <h3 className="font-semibold mb-3">Deployer un template WBS</h3>
            <p className="text-xs text-storm mb-3">Cela remplace toutes les taches existantes par le template selectionne.</p>
            <div className="grid grid-cols-3 gap-3">
              {templates.map(t => (
                <button key={t.id} onClick={() => deployTemplate(t.categorie)}
                  className="p-3 rounded-lg border-2 border-mist hover:border-iris text-left transition">
                  <p className="text-sm font-semibold">{t.name}</p>
                  <p className="text-[10px] text-storm">{t.categorie} — {t.tasks_count} taches</p>
                </button>
              ))}
            </div>
            <button onClick={() => setShowDeploy(false)} className="mt-3 text-sm text-storm hover:underline">Annuler</button>
          </div>
        )}

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h3 className="font-semibold mb-4">WBS Planning ({op.tasks?.length} taches)</h3>
          <div className="space-y-2">
            {(op.tasks || []).map((t: any) => {
              const overdue = t.fin_prevu && new Date(t.fin_prevu) < new Date() && t.avancement < 100;
              return (
                <div key={t.id} className={`flex items-center gap-3 p-3 rounded-lg border ${t.est_critique ? 'border-coral bg-[rgba(255,107,107,0.03)]' : 'border-mist'}`}>
                  <span className="font-mono text-xs font-bold text-iris w-8">{t.code_wbs}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{t.title}</p>
                    <p className="text-[10px] text-storm">{t.debut || '?'} — {t.fin || '?'} | Budget: {formatDA(t.budget)}</p>
                  </div>
                  <div className="w-32">
                    <div className="bg-mist rounded-full h-3 overflow-hidden">
                      <div className={`h-full rounded-full ${t.avancement >= 100 ? 'bg-mint' : t.est_critique ? 'bg-coral' : 'bg-iris'}`} style={{ width: `${t.avancement}%` }} />
                    </div>
                  </div>
                  <span className="font-mono text-sm font-bold w-12 text-right">{t.avancement}%</span>
                  <Badge variant={t.statut === 'TERMINEE' ? 'success' : t.statut === 'EN_COURS' ? 'info' : 'neutral'}>{t.statut}</Badge>
                  {t.est_critique && <Badge variant="error">CRITIQUE</Badge>}
                  {overdue && <Badge variant="error">RETARD</Badge>}
                </div>
              );
            })}
          </div>
        </div>
        </div>
      )}

      {/* ═══ S-CURVE TAB ═══ */}
      {tab === 'scurve' && scurve && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h3 className="font-semibold mb-4">Courbe en S — Physique vs Financier</h3>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center p-4 rounded-lg bg-[rgba(0,184,148,0.06)]">
              <p className="text-xs text-storm">Physique</p><p className="text-2xl font-bold text-mint">{scurve.physical_pct}%</p>
            </div>
            <div className={`text-center p-4 rounded-lg ${scurve.surpaiement_risk ? 'bg-[rgba(255,107,107,0.06)]' : 'bg-[rgba(9,132,227,0.06)]'}`}>
              <p className="text-xs text-storm">Financier</p><p className={`text-2xl font-bold ${scurve.surpaiement_risk ? 'text-coral' : 'text-ocean'}`}>{scurve.financial_pct}%</p>
            </div>
            <div className={`text-center p-4 rounded-lg ${scurve.surpaiement_risk ? 'bg-[rgba(255,107,107,0.06)] border-2 border-coral' : 'bg-[#FAFAFA]'}`}>
              <p className="text-xs text-storm">Ecart</p>
              <p className={`text-2xl font-bold ${scurve.surpaiement_risk ? 'text-coral' : ''}`}>{scurve.gap} pts</p>
              {scurve.surpaiement_risk && <p className="text-[10px] text-coral font-bold">SURPAIEMENT</p>}
            </div>
          </div>
          {scurve.rm25_alert && (
            <div className="bg-[rgba(255,107,107,0.06)] border border-coral rounded-lg p-3 text-sm text-coral">{scurve.rm25_message}</div>
          )}
        </div>
      )}
    </div>
  );
}
