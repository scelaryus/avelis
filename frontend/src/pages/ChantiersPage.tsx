import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../api/client";

type Tab = "dashboard" | "taches" | "sous-traitants" | "situations" | "rapports";

const TAB_LABELS: Record<Tab, string> = {
  dashboard: "Tableau de bord",
  taches: "Planning & Avancement",
  "sous-traitants": "Sous-traitants",
  situations: "Situations de Travaux",
  rapports: "Rapports Expert",
};

interface Projet { id: string; code: string; nom: string; taux_avancement: number; }
interface Tache {
  id: string; projet_id: string; code: string; libelle: string; categorie: string | null;
  avancement_pct: number; statut: string;
  date_debut_prevue: string | null; date_fin_prevue: string | null;
  budget_prevu: number; cout_reel: number; notes: string | null;
}
interface ST {
  id: string; raison_sociale: string; specialite: string | null;
  score_qualite: number; score_delais: number; score_securite: number; score_global: number;
  nb_evaluations: number; est_agree: boolean;
}
interface Situation {
  id: string; projet_id: string; sous_traitant_id: string; numero: string; periode: string | null;
  montant_ht: number; montant_ttc: number; montant_net: number;
  avancement_cumule_pct: number; statut: string; realite_financiere: string;
  journal_entry_id: string | null;
}
interface DashStats {
  taches_total: number; avancement_moyen: number;
  budget_prevu_total: number; cout_reel_total: number; ecart_budget: number;
  situations_validees: number; montant_situations_ttc: number;
}

const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(Math.round(n)) + " DA";

const STATUT_COLORS: Record<string, string> = {
  A_FAIRE: "bg-slate-100 text-slate-600",
  EN_COURS: "bg-blue-100 text-blue-700",
  TERMINE: "bg-emerald-100 text-emerald-700",
  BLOQUE: "bg-red-100 text-red-700",
  BROUILLON: "bg-slate-100 text-slate-600",
  SOUMISE: "bg-amber-100 text-amber-700",
  VALIDEE: "bg-emerald-100 text-emerald-700",
  REJETEE: "bg-red-100 text-red-700",
  PAYEE: "bg-teal-100 text-teal-700",
};

export default function ChantiersPage() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [projets, setProjets] = useState<Projet[]>([]);
  const [selectedProjet, setSelectedProjet] = useState("");

  useEffect(() => {
    api.get("/accounting/projets").then(({ data }) => {
      const items = Array.isArray(data) ? data : [];
      setProjets(items);
      if (items.length > 0 && !selectedProjet) setSelectedProjet(items[0].id);
    }).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Projets & Chantiers</h1>
      <p className="text-sm text-slate-500 mb-4">Avancement, sous-traitants, situations de travaux</p>

      <div className="flex items-center gap-4 mb-4">
        <select className="input-field text-sm w-auto min-w-[220px]" value={selectedProjet} onChange={(e) => setSelectedProjet(e.target.value)}>
          <option value="">Tous les projets</option>
          {projets.map((p) => <option key={p.id} value={p.id}>{p.code} &mdash; {p.nom}</option>)}
        </select>
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab projetId={selectedProjet} />}
      {tab === "taches" && <TachesTab projetId={selectedProjet} />}
      {tab === "sous-traitants" && <STTab />}
      {tab === "situations" && <SituationsTab projetId={selectedProjet} />}
      {tab === "rapports" && <RapportsTab projetId={selectedProjet} />}
    </div>
  );
}

/* ── Dashboard ── */
function DashboardTab({ projetId }: { projetId: string }) {
  const [stats, setStats] = useState<DashStats | null>(null);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [situations, setSituations] = useState<Situation[]>([]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (projetId) params.projet_id = projetId;
    api.get("/chantier/dashboard", { params }).then(({ data }) => setStats(data)).catch(() => {});
    api.get("/chantier/taches", { params }).then(({ data }) => setTaches(data || [])).catch(() => {});
    api.get("/chantier/situations", { params }).then(({ data }) => setSituations(data || [])).catch(() => {});
  }, [projetId]);

  if (!stats) return <p className="text-slate-400">Chargement...</p>;

  const budgetPct = stats.budget_prevu_total > 0 ? Math.round((stats.cout_reel_total / stats.budget_prevu_total) * 100) : 0;
  const overBudget = stats.ecart_budget < 0;
  const tachesEnCours = taches.filter(t => t.statut === "EN_COURS").length;
  const tachesTerminees = taches.filter(t => t.statut === "TERMINE").length;
  const tachesBloquees = taches.filter(t => t.statut === "BLOQUE").length;
  const sitEnAttente = situations.filter(s => s.statut === "BROUILLON" || s.statut === "SOUMISE").length;

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-slate-500">Avancement global</p>
          <p className="text-2xl font-bold text-teal-700 mt-1">{stats.avancement_moyen}%</p>
          <div className="w-full bg-slate-200 rounded-full h-2 mt-2">
            <div className="bg-teal-500 h-2 rounded-full" style={{ width: `${Math.min(stats.avancement_moyen, 100)}%` }} />
          </div>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500">Tâches</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.taches_total}</p>
          <div className="flex gap-2 mt-2 text-xs">
            <span className="text-blue-600">{tachesEnCours} en cours</span>
            <span className="text-emerald-600">{tachesTerminees} terminées</span>
            {tachesBloquees > 0 && <span className="text-red-600">{tachesBloquees} bloquées</span>}
          </div>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500">Budget consommé</p>
          <p className={`text-2xl font-bold mt-1 ${overBudget ? "text-red-600" : "text-blue-700"}`}>{budgetPct}%</p>
          <div className="w-full bg-slate-200 rounded-full h-2 mt-2">
            <div className={`h-2 rounded-full ${overBudget ? "bg-red-500" : "bg-blue-500"}`} style={{ width: `${Math.min(budgetPct, 100)}%` }} />
          </div>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500">Situations en attente</p>
          <p className="text-2xl font-bold text-amber-600 mt-1">{sitEnAttente}</p>
          <p className="text-xs text-slate-400 mt-2">{stats.situations_validees} validées</p>
        </div>
      </div>

      {/* Budget comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Budget vs Coût réel</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Budget prévu</span>
              <span className="text-sm font-mono font-medium text-blue-700">{fmt(stats.budget_prevu_total)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Coût réel</span>
              <span className="text-sm font-mono font-medium text-amber-700">{fmt(stats.cout_reel_total)}</span>
            </div>
            <div className="border-t pt-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">Écart</span>
              <span className={`text-sm font-mono font-bold ${overBudget ? "text-red-600" : "text-emerald-600"}`}>
                {overBudget ? "" : "+"}{fmt(stats.ecart_budget)}
              </span>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Sous-traitance</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Situations validées</span>
              <span className="text-sm font-bold text-indigo-700">{stats.situations_validees}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Montant TTC engagé</span>
              <span className="text-sm font-mono font-medium text-slate-800">{fmt(stats.montant_situations_ttc)}</span>
            </div>
            {sitEnAttente > 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 p-2 text-xs text-amber-700">
                {sitEnAttente} situation(s) en attente de validation
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent blocked/overdue tasks */}
      {tachesBloquees > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-red-700 mb-3">Tâches bloquées</h3>
          <div className="space-y-2">
            {taches.filter(t => t.statut === "BLOQUE").slice(0, 5).map(t => (
              <div key={t.id} className="flex items-center justify-between rounded-lg bg-red-50 px-3 py-2">
                <div>
                  <span className="font-mono text-xs text-red-400">{t.code}</span>
                  <span className="ml-2 text-sm text-red-800">{t.libelle}</span>
                </div>
                <span className="text-xs text-red-500">{t.notes || "Aucune note"}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Taches ── */
function TachesTab({ projetId }: { projetId: string }) {
  const [taches, setTaches] = useState<Tache[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [editPct, setEditPct] = useState("");
  const [showAiPlan, setShowAiPlan] = useState(false);
  const [aiDesc, setAiDesc] = useState("");
  const [aiBudget, setAiBudget] = useState("");
  const [aiDateDebut, setAiDateDebut] = useState("");
  const [aiDateFin, setAiDateFin] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPlan, setAiPlan] = useState<any>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (projetId) params.projet_id = projetId;
    api.get("/chantier/taches", { params }).then(({ data }) => setTaches(data || [])).catch(() => setTaches([])).finally(() => setLoading(false));
  }, [projetId]);
  useEffect(() => { load(); }, [load]);

  const updateAvancement = async (id: string) => {
    await api.put(`/chantier/taches/${id}`, { avancement_pct: parseFloat(editPct) });
    setEditing(null);
    load();
  };

  const generateAiPlan = async () => {
    setAiLoading(true); setAiPlan(null);
    try {
      const { data } = await api.post("/chantier/taches/ai-plan", {
        description: aiDesc, budget: aiBudget ? Number(aiBudget) : null,
        date_debut: aiDateDebut || null, date_fin: aiDateFin || null, projet_id: projetId || null,
      });
      setAiPlan(data);
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur IA"); }
    finally { setAiLoading(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{taches.length} tâches</span>
        <button onClick={() => setShowAiPlan(!showAiPlan)} className="btn-primary text-xs">Planifier avec l'IA</button>
      </div>

      {showAiPlan && (
        <div className="card p-4 space-y-3 bg-gradient-to-r from-violet-50 to-indigo-50 border-violet-200">
          <h3 className="text-sm font-semibold text-violet-900">Agent IA de planification</h3>
          <p className="text-xs text-violet-600">Décrivez la tâche ou le lot de travaux. L'IA crée un plan détaillé avec sous-tâches.</p>
          <textarea className="input-field w-full" rows={3} placeholder="Ex: Réaliser le gros œuvre du bloc B, 5 étages, fondations déjà terminées..."
            value={aiDesc} onChange={e => setAiDesc(e.target.value)} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-violet-700 mb-1">Budget (DA)</label>
              <input type="number" className="input-field" value={aiBudget} onChange={e => setAiBudget(e.target.value)} placeholder="Optionnel" /></div>
            <div><label className="block text-xs font-medium text-violet-700 mb-1">Date début</label>
              <input type="date" className="input-field" value={aiDateDebut} onChange={e => setAiDateDebut(e.target.value)} /></div>
            <div><label className="block text-xs font-medium text-violet-700 mb-1">Date fin souhaitée</label>
              <input type="date" className="input-field" value={aiDateFin} onChange={e => setAiDateFin(e.target.value)} /></div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => { setShowAiPlan(false); setAiPlan(null); }} className="btn-secondary text-sm">Fermer</button>
            <button onClick={generateAiPlan} disabled={aiLoading || !aiDesc.trim()} className="btn-primary text-sm">
              {aiLoading ? "Analyse IA..." : "Générer le plan"}
            </button>
          </div>

          {aiPlan && (
            <div className="mt-4 space-y-3">
              <h4 className="font-semibold text-slate-900">{aiPlan.plan_title}</h4>
              {aiPlan.missing_info?.length > 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                  <p className="text-xs font-semibold text-amber-800 mb-1">Informations manquantes :</p>
                  <ul className="text-xs text-amber-700 list-disc pl-4">
                    {aiPlan.missing_info.map((info: string, i: number) => <li key={i}>{info}</li>)}
                  </ul>
                </div>
              )}
              {aiPlan.tasks?.length > 0 && (
                <div className="card overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50"><tr>
                      <th className="px-3 py-2 text-left">Code</th>
                      <th className="px-3 py-2 text-left">Tâche</th>
                      <th className="px-3 py-2 text-left">Catégorie</th>
                      <th className="px-3 py-2 text-right">Durée (j)</th>
                      <th className="px-3 py-2 text-right">Budget estimé</th>
                      <th className="px-3 py-2 text-left">Priorité</th>
                    </tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {aiPlan.tasks.map((t: any, i: number) => (
                        <tr key={i} className="hover:bg-slate-50">
                          <td className="px-3 py-1.5 font-mono">{t.code}</td>
                          <td className="px-3 py-1.5">{t.libelle}</td>
                          <td className="px-3 py-1.5 text-slate-500">{t.categorie}</td>
                          <td className="px-3 py-1.5 text-right">{t.duree_jours ?? "—"}</td>
                          <td className="px-3 py-1.5 text-right font-mono">{t.budget_estime ? `${Number(t.budget_estime).toLocaleString("fr-FR")} DA` : "—"}</td>
                          <td className="px-3 py-1.5">{t.priorite}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {aiPlan.recommandations && (
                <div className="rounded-lg bg-teal-50 border border-teal-200 p-3">
                  <p className="text-xs font-semibold text-teal-800 mb-1">Recommandations IA</p>
                  <p className="text-xs text-teal-700">{aiPlan.recommandations}</p>
                </div>
              )}
              {aiPlan.budget_total_estime && (
                <p className="text-xs text-slate-600">Budget total estimé : <strong>{Number(aiPlan.budget_total_estime).toLocaleString("fr-FR")} DA</strong> — Durée : <strong>{aiPlan.duree_totale_jours} jours</strong></p>
              )}
            </div>
          )}
        </div>
      )}

      <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">Code</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Libell&eacute;</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Cat&eacute;gorie</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Avancement</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Statut</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Budget</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Co&ucirc;t r&eacute;el</th>
            <th className="px-3 py-3 w-32"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {loading ? (
            <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement&hellip;</td></tr>
          ) : taches.length === 0 ? (
            <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Aucune t&acirc;che</td></tr>
          ) : taches.map((t) => (
            <tr key={t.id} className="hover:bg-slate-50">
              <td className="px-3 py-2 font-mono text-xs">{t.code}</td>
              <td className="px-3 py-2">{t.libelle}</td>
              <td className="px-3 py-2 text-xs text-slate-500">{t.categorie || "\u2014"}</td>
              <td className="px-3 py-2 text-right">
                {editing === t.id ? (
                  <div className="flex items-center justify-end gap-1">
                    <input type="number" min="0" max="100" className="input-field w-16 text-xs py-1" value={editPct} onChange={(e) => setEditPct(e.target.value)} />
                    <button onClick={() => updateAvancement(t.id)} className="text-xs text-teal-600 font-medium">OK</button>
                  </div>
                ) : (
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-16 h-2 rounded-full bg-slate-200 overflow-hidden">
                      <div className="h-full bg-teal-500 rounded-full" style={{ width: `${t.avancement_pct}%` }} />
                    </div>
                    <span className="text-xs font-medium w-10 text-right">{t.avancement_pct}%</span>
                  </div>
                )}
              </td>
              <td className="px-3 py-2">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_COLORS[t.statut] || "bg-slate-100"}`}>{t.statut}</span>
              </td>
              <td className="px-3 py-2 text-right text-xs font-mono">{fmt(t.budget_prevu)}</td>
              <td className="px-3 py-2 text-right text-xs font-mono">{fmt(t.cout_reel)}</td>
              <td className="px-3 py-2">
                <button onClick={() => { setEditing(t.id); setEditPct(String(t.avancement_pct)); }}
                  className="px-2 py-0.5 rounded text-[10px] bg-teal-100 text-teal-700 hover:bg-teal-200">
                  Mettre à jour %
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  );
}

/* ── Sous-traitants ── */
function STTab() {
  const [items, setItems] = useState<ST[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [form, setForm] = useState({ raison_sociale: "", specialite: "", nif: "", telephone: "", email: "" });

  const load = useCallback(() => {
    setLoading(true);
    api.get("/chantier/sous-traitants").then(({ data }) => setItems(data || [])).catch(() => setItems([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proofFile) { alert("Un justificatif (RC, NIF, agrément, CACOBATPH) est obligatoire."); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", proofFile);
      const body = JSON.stringify(form);
      fd.append("body", new Blob([body], { type: "application/json" }));
      await api.post("/chantier/sous-traitants", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      setShowForm(false); setProofFile(null);
      setForm({ raison_sociale: "", specialite: "", nif: "", telephone: "", email: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  const evaluate = async (id: string) => {
    const q = prompt("Score qualité (0-100) :");
    const d = prompt("Score délais (0-100) :");
    const s = prompt("Score sécurité (0-100) :");
    if (!q || !d || !s) return;
    try {
      await api.post(`/chantier/sous-traitants/${id}/evaluer`, {
        score_qualite: parseFloat(q), score_delais: parseFloat(d), score_securite: parseFloat(s),
      });
      load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} sous-traitants</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">+ Nouveau sous-traitant</button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Raison sociale *</label>
              <input className="input-field" value={form.raison_sociale} onChange={e => setForm({ ...form, raison_sociale: e.target.value })} required placeholder="Nom de l'entreprise" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Spécialité</label>
              <input className="input-field" value={form.specialite} onChange={e => setForm({ ...form, specialite: e.target.value })} placeholder="Gros œuvre, électricité..." /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">NIF</label>
              <input className="input-field" value={form.nif} onChange={e => setForm({ ...form, nif: e.target.value })} placeholder="Numéro d'identification fiscale" /></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Téléphone</label>
              <input className="input-field" value={form.telephone} onChange={e => setForm({ ...form, telephone: e.target.value })} placeholder="0X XX XX XX XX" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Email</label>
              <input type="email" className="input-field" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="contact@st.dz" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Justificatif (RC, NIF, agrément) *</label>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" onChange={e => setProofFile(e.target.files?.[0] ?? null)} required />
              <p className="text-xs text-slate-400 mt-1">L'IA vérifie le document avant validation</p></div>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Vérification IA..." : "Enregistrer"}</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-3 py-3 text-left font-medium text-slate-600">Raison sociale</th>
              <th className="px-3 py-3 text-left font-medium text-slate-600">Spécialité</th>
              <th className="px-3 py-3 text-right font-medium text-slate-600">Qualité</th>
              <th className="px-3 py-3 text-right font-medium text-slate-600">Délais</th>
              <th className="px-3 py-3 text-right font-medium text-slate-600">Sécurité</th>
              <th className="px-3 py-3 text-right font-medium text-slate-600">Score global</th>
              <th className="px-3 py-3 text-right font-medium text-slate-600">Éval.</th>
              <th className="px-3 py-3 w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Aucun sous-traitant</td></tr>
            ) : items.map((s) => (
              <tr key={s.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-medium">{s.raison_sociale}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{s.specialite || "—"}</td>
                <td className="px-3 py-2 text-right">{s.score_qualite}/100</td>
                <td className="px-3 py-2 text-right">{s.score_delais}/100</td>
                <td className="px-3 py-2 text-right">{s.score_securite}/100</td>
                <td className="px-3 py-2 text-right font-bold text-teal-700">{s.score_global}/100</td>
                <td className="px-3 py-2 text-right text-xs text-slate-400">{s.nb_evaluations}x</td>
                <td className="px-3 py-2">
                  <button onClick={() => evaluate(s.id)} className="px-2 py-0.5 rounded text-[10px] bg-indigo-100 text-indigo-700 hover:bg-indigo-200">Évaluer</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Situations de travaux ── */
function SituationsTab({ projetId }: { projetId: string }) {
  const { user } = useAuth();
  const [items, setItems] = useState<Situation[]>([]);
  const [sts, setSts] = useState<ST[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [form, setForm] = useState({ numero: "", periode: "", sous_traitant_id: "", montant_ht: 0, avancement_cumule_pct: 0, avancement_periode_pct: 0, realite_financiere: "RF1", notes: "" });

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (projetId) params.projet_id = projetId;
    api.get("/chantier/situations", { params }).then(({ data }) => setItems(data || [])).catch(() => setItems([])).finally(() => setLoading(false));
  }, [projetId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/chantier/sous-traitants").then(({ data }) => setSts(data || [])).catch(() => {}); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proofFile) { alert("Le document de situation (PDF signé) est obligatoire."); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", proofFile);
      const body = JSON.stringify({ ...form, montant_ht: Number(form.montant_ht), avancement_cumule_pct: Number(form.avancement_cumule_pct), avancement_periode_pct: Number(form.avancement_periode_pct), projet_id: projetId, entreprise_id: "default" });
      fd.append("body", new Blob([body], { type: "application/json" }));
      await api.post("/chantier/situations", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      setShowForm(false); setProofFile(null);
      setForm({ numero: "", periode: "", sous_traitant_id: "", montant_ht: 0, avancement_cumule_pct: 0, avancement_periode_pct: 0, realite_financiere: "RF1", notes: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  const valider = async (id: string, createdBy: string) => {
    if (createdBy === user?.id) { alert("Le créateur ne peut pas valider sa propre situation."); return; }
    try { await api.post(`/chantier/situations/${id}/valider`); load(); } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
  };
  const rejeter = async (id: string) => {
    const motif = prompt("Motif du rejet :"); if (!motif) return;
    await api.post(`/chantier/situations/${id}/rejeter`, null, { params: { motif } }); load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} situations</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">+ Nouvelle situation</button>
      </div>
      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">N° situation *</label>
              <input className="input-field" value={form.numero} onChange={e => setForm({ ...form, numero: e.target.value })} required placeholder="SIT-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Période</label>
              <input className="input-field" value={form.periode} onChange={e => setForm({ ...form, periode: e.target.value })} placeholder="Mars 2026" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Sous-traitant *</label>
              <select className="input-field" value={form.sous_traitant_id} onChange={e => setForm({ ...form, sous_traitant_id: e.target.value })} required>
                <option value="">Sélectionner...</option>
                {sts.map(st => <option key={st.id} value={st.id}>{st.raison_sociale}</option>)}
              </select></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant HT (DA) *</label>
              <input type="number" step="0.01" className="input-field" value={form.montant_ht || ""} onChange={e => setForm({ ...form, montant_ht: +e.target.value })} required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Avancement cumulé %</label>
              <input type="number" min={0} max={100} className="input-field" value={form.avancement_cumule_pct || ""} onChange={e => setForm({ ...form, avancement_cumule_pct: +e.target.value })} /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Avancement période %</label>
              <input type="number" min={0} max={100} className="input-field" value={form.avancement_periode_pct || ""} onChange={e => setForm({ ...form, avancement_periode_pct: +e.target.value })} /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">RF</label>
              <select className="input-field" value={form.realite_financiere} onChange={e => setForm({ ...form, realite_financiere: e.target.value })}>
                <option value="RF1">RF1</option><option value="RF2">RF2</option>
              </select></div>
          </div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Document situation signé (PDF) *</label>
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" onChange={e => setProofFile(e.target.files?.[0] ?? null)} required />
            <p className="text-xs text-slate-400 mt-1">L'IA vérifie la cohérence du document avec le montant déclaré</p></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Notes / justification *</label>
            <textarea className="input-field w-full" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} required placeholder="Travaux réalisés, observations..." /></div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Vérification IA..." : "Soumettre"}</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">N°</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Période</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">HT</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">TTC</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Net</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Avancement</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Statut</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">RF</th>
            <th className="px-3 py-3 w-32"></th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-400">Chargement...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-400">Aucune situation</td></tr>
            ) : items.map((s: any) => (
              <tr key={s.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{s.numero}</td>
                <td className="px-3 py-2 text-xs">{s.periode || "—"}</td>
                <td className="px-3 py-2 text-right text-xs font-mono">{fmt(s.montant_ht)}</td>
                <td className="px-3 py-2 text-right text-xs font-mono">{fmt(s.montant_ttc)}</td>
                <td className="px-3 py-2 text-right text-xs font-mono font-medium">{fmt(s.montant_net)}</td>
                <td className="px-3 py-2 text-right text-xs">{s.avancement_cumule_pct}%</td>
                <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_COLORS[s.statut] || "bg-slate-100"}`}>{s.statut}</span></td>
                <td className="px-3 py-2 text-xs">{s.realite_financiere}</td>
                <td className="px-3 py-2">
                  {(s.statut === "BROUILLON" || s.statut === "SOUMISE") && (
                    <div className="flex gap-1">
                      <button onClick={() => valider(s.id, s.created_by)} className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-700">Valider</button>
                      <button onClick={() => rejeter(s.id)} className="px-1.5 py-0.5 rounded text-[10px] bg-red-100 text-red-700">Rejeter</button>
                    </div>
                  )}
                  {s.journal_entry_id && <span className="text-[10px] text-teal-600">JE liée</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Rapports expert ── */
function RapportsTab({ projetId }: { projetId: string }) {
  const { user } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [form, setForm] = useState({ numero: "", date_visite: new Date().toISOString().slice(0, 10), avancement_constate_pct: 0, palier_vsp: "", observations: "" });

  const load = useCallback(() => {
    const params: Record<string, string> = {};
    if (projetId) params.projet_id = projetId;
    api.get("/chantier/rapports-expert", { params }).then(({ data }) => setItems(data || [])).catch(() => setItems([]));
  }, [projetId]);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proofFile) { alert("Le rapport d'expert signé (PDF) est obligatoire."); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", proofFile);
      const body = JSON.stringify({ ...form, avancement_constate_pct: Number(form.avancement_constate_pct), palier_vsp: form.palier_vsp ? Number(form.palier_vsp) : null, projet_id: projetId });
      fd.append("body", new Blob([body], { type: "application/json" }));
      await api.post("/chantier/rapports-expert", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      setShowForm(false); setProofFile(null);
      setForm({ numero: "", date_visite: new Date().toISOString().slice(0, 10), avancement_constate_pct: 0, palier_vsp: "", observations: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  const valider = async (id: string, createdBy: string) => {
    if (createdBy === user?.id) { alert("Le créateur ne peut pas valider son propre rapport."); return; }
    try { await api.post(`/chantier/rapports-expert/${id}/valider`); load(); } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} rapports</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">+ Nouveau rapport</button>
      </div>
      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">N° rapport *</label>
              <input className="input-field" value={form.numero} onChange={e => setForm({ ...form, numero: e.target.value })} required placeholder="RE-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date visite *</label>
              <input type="date" className="input-field" value={form.date_visite} onChange={e => setForm({ ...form, date_visite: e.target.value })} required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Avancement constaté % *</label>
              <input type="number" min={0} max={100} className="input-field" value={form.avancement_constate_pct || ""} onChange={e => setForm({ ...form, avancement_constate_pct: +e.target.value })} required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Palier VSP</label>
              <input type="number" className="input-field" value={form.palier_vsp} onChange={e => setForm({ ...form, palier_vsp: e.target.value })} placeholder="1, 2, 3..." /></div>
          </div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Rapport d'expert signé (PDF) *</label>
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" onChange={e => setProofFile(e.target.files?.[0] ?? null)} required />
            <p className="text-xs text-slate-400 mt-1">L'IA vérifie le document avant soumission</p></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Observations / justification *</label>
            <textarea className="input-field w-full" rows={2} value={form.observations} onChange={e => setForm({ ...form, observations: e.target.value })} required placeholder="État des travaux constatés, réserves..." /></div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Vérification IA..." : "Soumettre"}</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">N°</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Date visite</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Avancement</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Palier VSP</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Validé</th>
            <th className="px-3 py-3 w-24"></th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {items.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucun rapport</td></tr>
            ) : items.map((r: any) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{r.numero}</td>
                <td className="px-3 py-2 text-xs">{r.date_visite}</td>
                <td className="px-3 py-2 text-right font-medium">{r.avancement_constate_pct}%</td>
                <td className="px-3 py-2 text-right">{r.palier_vsp ?? "—"}</td>
                <td className="px-3 py-2">{r.est_valide ? <span className="text-emerald-600 font-medium">Oui</span> : <span className="text-slate-400">Non</span>}</td>
                <td className="px-3 py-2">
                  {!r.est_valide && (
                    <button onClick={() => valider(r.id, r.created_by)} className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-700">Valider</button>
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
