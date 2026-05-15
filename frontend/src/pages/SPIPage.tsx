import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../api/client";
import {
  ChartBarIcon,
  ArrowPathIcon,
  CheckBadgeIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentListIcon,
  LightBulbIcon,
  CurrencyDollarIcon,
  BellAlertIcon,
  UserGroupIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";

/* ──────────────── Types ──────────────── */

interface SPIMensuel {
  id: string;
  employe_id: string;
  employe_nom: string;
  mois: string;
  c1_execution: number;
  c2_qualite: number;
  c3_comportement: number;
  c4_metier: number;
  w1: number; w2: number; w3: number; w4: number;
  score_spi: number;
  fiabilite_score: number;
  est_confirme: boolean;
  prime_calculee: number;
  solde_bm_mois: number;
  taches_total: number;
  taches_validees: number;
  taches_rejetees: number;
  taches_en_retard: number;
  valide_par_manager: boolean;
}


interface PlanStrategique {
  id: string;
  reference: string;
  titre: string;
  description: string;
  objectif_smart?: string;
  statut: string;
  horizon?: string;
  proposeur_id: string;
  proposeur_nom: string;
  date_proposition?: string;
  avancement_pct: number;
  score_pertinence: number;
  faisabilite: number;
  ameliorations?: string;
  prime_versee: boolean;
  montant_prime: number;
}

interface AlerteRH {
  id: string;
  type: string;
  message: string;
  severite: string;
  employe_id: string;
  employe_nom: string;
  mois?: string;
  score_spi?: number;
  est_traitee: boolean;
  date?: string;
}

interface DashboardDirection {
  mois: string;
  effectif_total: number;
  effectif_evalue: number;
  spi_moyen: number;
  masse_salariale_totale: number;
  total_primes_spi: number;
  distribution: Record<string, number>;
  top_performers: { id: string; nom: string; spi: number; departement?: string }[];
  low_performers: { id: string; nom: string; spi: number; departement?: string }[];
  alertes: AlerteRH[];
  employees: { id: string; nom: string; departement?: string; spi: number; base: number; prime: number; statut_rh: string }[];
}

/* ──────────────── Helpers ──────────────── */

const moisCourant = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

const fmt = (n: number) => new Intl.NumberFormat("fr-DZ").format(Math.round(n));

function spiColor(score: number) {
  if (score >= 90) return "text-emerald-600";
  if (score >= 75) return "text-teal-600";
  if (score >= 60) return "text-amber-600";
  if (score >= 50) return "text-orange-500";
  return "text-red-600";
}

function spiLabel(score: number) {
  if (score >= 90) return "Excellent";
  if (score >= 75) return "Performant";
  if (score >= 60) return "Standard";
  if (score >= 50) return "Sous-perf.";
  return "Critique";
}

function statutBadge(statut: string) {
  const map: Record<string, string> = {
    ASSIGNEE: "bg-blue-100 text-blue-700",
    OFFRE_EN_COURS: "bg-purple-100 text-purple-700",
    VERROUILLEE: "bg-indigo-100 text-indigo-700",
    EN_COURS: "bg-amber-100 text-amber-700",
    EN_REVUE: "bg-cyan-100 text-cyan-700",
    VALIDEE: "bg-emerald-100 text-emerald-700",
    REJETEE: "bg-red-100 text-red-700",
    ANNULEE: "bg-gray-100 text-gray-500",
    SOUMIS: "bg-blue-100 text-blue-700",
    EN_ANALYSE: "bg-cyan-100 text-cyan-700",
    VALIDE: "bg-emerald-100 text-emerald-700",
    DECLINE: "bg-red-100 text-red-700",
    EN_EXECUTION: "bg-amber-100 text-amber-700",
    TERMINE: "bg-teal-100 text-teal-700",
  };
  return map[statut] || "bg-gray-100 text-gray-600";
}

function prioriteIcon(p: string) {
  if (p === "CRITIQUE") return "text-red-500 font-bold";
  if (p === "ELEVEE") return "text-orange-500";
  return "text-gray-500";
}

/* ──────────────── Component ──────────────── */

const MANAGER_ROLES = new Set(["admin", "hr_manager", "SUPER_ADMIN", "RH", "DIRECTION", "DAF"]);

export default function SPIPage() {
  const { user } = useAuth();
  const isManager = user ? MANAGER_ROLES.has(user.role) : false;
  const defaultTab = isManager ? "dashboard" : "taches";
  const [tab, setTab] = useState<"dashboard" | "spi" | "taches" | "plans" | "alertes">(defaultTab);
  const [mois, setMois] = useState(moisCourant());
  const [loading, setLoading] = useState(false);

  // Data states
  const [dashboard, setDashboard] = useState<DashboardDirection | null>(null);
  const [spis, setSpis] = useState<SPIMensuel[]>([]);
  const [plans, setPlans] = useState<PlanStrategique[]>([]);
  const [alertes, setAlertes] = useState<AlerteRH[]>([]);

  // Forms
  const [showPlanForm, setShowPlanForm] = useState(false);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/planification/dashboard/direction", { params: { mois } });
      setDashboard(data);
    } catch { setDashboard(null); }
    setLoading(false);
  }, [mois]);

  const loadSPIs = useCallback(async () => {
    try {
      const { data } = await api.get("/planification/spi-mensuel", { params: { mois } });
      setSpis(data);
    } catch { setSpis([]); }
  }, [mois]);

  const loadPlans = useCallback(async () => {
    try {
      const params = isManager ? {} : { mine: true };
      const { data } = await api.get("/planification/plans", { params });
      setPlans(data);
    } catch { setPlans([]); }
  }, [isManager]);

  const loadAlertes = useCallback(async () => {
    try {
      const { data } = await api.get("/planification/alertes", { params: { mois } });
      setAlertes(data);
    } catch { setAlertes([]); }
  }, [mois]);

  useEffect(() => {
    loadDashboard();
    loadSPIs();
    loadPlans();
    loadAlertes();
  }, [loadDashboard, loadSPIs, loadPlans, loadAlertes]);

  const computeSPI = async () => {
    setLoading(true);
    try {
      await api.post("/planification/spi-mensuel/compute", null, { params: { mois } });
      await loadSPIs();
      await loadDashboard();
    } catch (e: any) { alert(e?.response?.data?.detail || "Erreur calcul SPI"); }
    setLoading(false);
  };

  const allTabs = [
    { key: "dashboard", label: "Dashboard Direction", icon: ChartBarIcon, managerOnly: true },
    { key: "spi", label: "SPI Mensuel", icon: CheckBadgeIcon, managerOnly: true },
    { key: "taches", label: "Mes Tâches", icon: ClipboardDocumentListIcon, managerOnly: false },
    { key: "plans", label: "Plans Stratégiques", icon: LightBulbIcon, managerOnly: false },
    { key: "alertes", label: "Alertes RH", icon: BellAlertIcon, managerOnly: true },
  ];
  const tabs = allTabs.filter(t => !t.managerOnly || isManager);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isManager ? "SPI 360 - Performance & Paie" : "Mon Espace SPI"}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {isManager ? "Planification, KPI, Bonus/Malus, Commissions" : "Tâches, négociations et plans stratégiques"}
          </p>
        </div>
        {isManager && (
          <div className="flex items-center gap-3">
            <input
              type="month"
              value={mois}
              onChange={e => setMois(e.target.value)}
              className="input-field text-sm"
            />
            <button onClick={computeSPI} disabled={loading} className="btn-primary flex items-center gap-1.5 text-sm">
              <ArrowPathIcon className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Calculer SPI
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as typeof tab)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-teal-600 text-teal-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
            {t.key === "alertes" && alertes.length > 0 && (
              <span className="ml-1 bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5">{alertes.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Dashboard Direction */}
      {tab === "dashboard" && (
        <DashboardSection dashboard={dashboard} loading={loading} />
      )}

      {/* SPI Mensuel */}
      {tab === "spi" && (
        <SPIMensuelSection spis={spis} onConfirm={async (id) => {
          await api.put(`/planification/spi-mensuel/${id}/confirmer`);
          await loadSPIs();
          await loadAlertes();
        }} />
      )}

      {/* Taches */}
      {tab === "taches" && (
        <TachesSection isManager={isManager} />
      )}

      {/* Plans */}
      {tab === "plans" && (
        <PlansSection
          plans={plans}
          showForm={showPlanForm}
          setShowForm={setShowPlanForm}
          onReload={loadPlans}
        />
      )}

      {/* Alertes */}
      {tab === "alertes" && (
        <AlertesSection alertes={alertes} onTraiter={async (id) => {
          await api.put(`/planification/alertes/${id}/traiter`);
          await loadAlertes();
        }} />
      )}
    </div>
  );
}

/* ── Dashboard Direction ────────────────────────────────────────── */

function DashboardSection({ dashboard, loading }: { dashboard: DashboardDirection | null; loading: boolean }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Chargement...</div>;
  if (!dashboard) return <div className="text-center py-12 text-gray-400">Aucune donnee pour ce mois</div>;

  const d = dashboard;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="card p-4">
          <p className="text-xs text-gray-500 uppercase">Effectif evalue</p>
          <p className="text-2xl font-bold text-gray-900">{d.effectif_evalue}/{d.effectif_total}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-500 uppercase">SPI Moyen</p>
          <p className={`text-2xl font-bold ${spiColor(d.spi_moyen)}`}>{d.spi_moyen}/100</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-500 uppercase">Masse salariale</p>
          <p className="text-2xl font-bold text-gray-900">{fmt(d.masse_salariale_totale)} DA</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-500 uppercase">Total primes SPI</p>
          <p className="text-2xl font-bold text-teal-600">{fmt(d.total_primes_spi)} DA</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-500 uppercase">Alertes</p>
          <p className="text-2xl font-bold text-red-600">{d.alertes.length}</p>
        </div>
      </div>

      {/* Distribution + Top/Low */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Distribution SPI</h3>
          <div className="space-y-2">
            {[
              { key: "excellent", label: "90-100 Excellent", color: "bg-emerald-500" },
              { key: "performant", label: "75-89 Performant", color: "bg-teal-500" },
              { key: "standard", label: "60-74 Standard", color: "bg-amber-500" },
              { key: "sous_perf", label: "50-59 Sous-perf", color: "bg-orange-500" },
              { key: "critique", label: "0-49 Critique", color: "bg-red-500" },
            ].map(b => {
              const count = d.distribution[b.key] || 0;
              const pct = d.effectif_evalue > 0 ? (count / d.effectif_evalue) * 100 : 0;
              return (
                <div key={b.key} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-32">{b.label}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-4">
                    <div className={`${b.color} rounded-full h-4`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs font-medium w-6 text-right">{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top performers */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Performers</h3>
          <div className="space-y-2">
            {d.top_performers.map((p, i) => (
              <div key={p.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-teal-600 w-5">#{i + 1}</span>
                  <span className="text-sm">{p.nom}</span>
                </div>
                <span className={`text-sm font-bold ${spiColor(p.spi)}`}>{p.spi}</span>
              </div>
            ))}
            {d.top_performers.length === 0 && <p className="text-xs text-gray-400">Aucun</p>}
          </div>
        </div>

        {/* Low performers */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Sous-performance</h3>
          <div className="space-y-2">
            {d.low_performers.map(p => (
              <div key={p.id} className="flex items-center justify-between">
                <span className="text-sm">{p.nom}</span>
                <span className={`text-sm font-bold ${spiColor(p.spi)}`}>{p.spi}</span>
              </div>
            ))}
            {d.low_performers.length === 0 && <p className="text-xs text-gray-400">Aucun</p>}
          </div>
        </div>
      </div>

      {/* All employees table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">Tous les employes — {d.mois}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-2 text-xs text-gray-500">Employe</th>
                <th className="text-left px-4 py-2 text-xs text-gray-500">Departement</th>
                <th className="text-right px-4 py-2 text-xs text-gray-500">SPI</th>
                <th className="text-right px-4 py-2 text-xs text-gray-500">Base</th>
                <th className="text-right px-4 py-2 text-xs text-gray-500">Prime SPI</th>
                <th className="text-center px-4 py-2 text-xs text-gray-500">Statut RH</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {d.employees.map(e => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{e.nom}</td>
                  <td className="px-4 py-2 text-gray-600">{e.departement || "—"}</td>
                  <td className={`px-4 py-2 text-right font-bold ${spiColor(e.spi)}`}>
                    {e.spi} <span className="text-xs font-normal">{spiLabel(e.spi)}</span>
                  </td>
                  <td className="px-4 py-2 text-right">{fmt(e.base)}</td>
                  <td className="px-4 py-2 text-right text-teal-600">{fmt(e.prime)}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      e.statut_rh === "ACTIF" ? "bg-emerald-100 text-emerald-700" :
                      e.statut_rh === "SURVEILLANCE" ? "bg-amber-100 text-amber-700" :
                      e.statut_rh === "AVERTISSEMENT" ? "bg-orange-100 text-orange-700" :
                      "bg-red-100 text-red-700"
                    }`}>{e.statut_rh}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ── SPI Mensuel Section ────────────────────────────────────────── */

function SPIMensuelSection({ spis, onConfirm }: { spis: SPIMensuel[]; onConfirm: (id: string) => void }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">{spis.length} scores SPI mensuels</p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {spis.map(s => (
          <div key={s.id} className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900">{s.employe_nom}</p>
                <p className="text-xs text-gray-500">{s.mois}</p>
              </div>
              <div className="text-right">
                <p className={`text-2xl font-bold ${spiColor(s.score_spi)}`}>{s.score_spi}</p>
                <p className={`text-xs ${spiColor(s.score_spi)}`}>{spiLabel(s.score_spi)}</p>
              </div>
            </div>

            {/* 4 components bar */}
            <div className="space-y-1">
              {[
                { label: "C1 Execution", score: s.c1_execution, w: s.w1, color: "bg-blue-500" },
                { label: "C2 Qualite", score: s.c2_qualite, w: s.w2, color: "bg-purple-500" },
                { label: "C3 Comportement", score: s.c3_comportement, w: s.w3, color: "bg-teal-500" },
                { label: "C4 Metier", score: s.c4_metier, w: s.w4, color: "bg-amber-500" },
              ].map(c => (
                <div key={c.label} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28">{c.label} ({c.w}%)</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div className={`${c.color} rounded-full h-2`} style={{ width: `${c.score}%` }} />
                  </div>
                  <span className="text-xs font-medium w-8 text-right">{c.score}</span>
                </div>
              ))}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-gray-50 rounded p-1.5">
                <p className="text-gray-500">Taches</p>
                <p className="font-semibold">{s.taches_validees}/{s.taches_total}</p>
              </div>
              <div className="bg-gray-50 rounded p-1.5">
                <p className="text-gray-500">Prime</p>
                <p className="font-semibold text-teal-600">{fmt(s.prime_calculee)}</p>
              </div>
              <div className="bg-gray-50 rounded p-1.5">
                <p className="text-gray-500">Solde B/M</p>
                <p className={`font-semibold ${s.solde_bm_mois >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {s.solde_bm_mois >= 0 ? "+" : ""}{fmt(s.solde_bm_mois)}
                </p>
              </div>
            </div>

            {/* Fiability + confirm */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-100">
              <div className="flex items-center gap-2">
                <span className={`text-xs ${s.fiabilite_score >= 70 ? "text-emerald-600" : "text-orange-500"}`}>
                  Fiabilite: {s.fiabilite_score}%
                </span>
                {s.est_confirme && <CheckBadgeIcon className="w-4 h-4 text-emerald-500" />}
              </div>
              {!s.est_confirme && (
                <button
                  onClick={() => onConfirm(s.id)}
                  className="text-xs btn-primary px-3 py-1"
                >
                  Confirmer
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {spis.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          Aucun SPI calcule pour ce mois. Cliquez "Calculer SPI" pour generer.
        </div>
      )}
    </div>
  );
}

/* ── Taches Section ─────────────────────────────────────────────── */

interface HRTask {
  id: string;
  title: string;
  description: string;
  status: string;
  task_type: string;
  employee_name: string | null;
  plan_date: string | null;
  due_date: string | null;
  approval_status: string | null;
  employee_estimated_time: number | null;
  employee_estimated_price: number | null;
  manager_final_time: number | null;
  manager_final_price: number | null;
  ai_score: number | null;
  manager_validated: boolean;
  manager_rating: number | null;
  manager_feedback: string | null;
}

function TachesSection({ isManager }: { isManager: boolean }) {
  const [tasks, setTasks] = useState<HRTask[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = isManager ? {} : { mine: true };
    api.get("/hr/tasks", { params })
      .then(({ data }) => setTasks(data || []))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, [isManager]);

  const approvalLabel = (s: string | null) => {
    if (!s) return null;
    const map: Record<string, { cls: string; label: string }> = {
      PENDING_ESTIMATE: { cls: "bg-slate-100 text-slate-700", label: "En attente" },
      ESTIMATED: { cls: "bg-blue-100 text-blue-700", label: "Estimée" },
      APPROVED: { cls: "bg-green-100 text-green-700", label: "Approuvée" },
      REJECTED: { cls: "bg-red-100 text-red-700", label: "Rejetée" },
      PROOF_SUBMITTED: { cls: "bg-violet-100 text-violet-700", label: "Preuve soumise" },
      VALIDATED: { cls: "bg-emerald-100 text-emerald-700", label: "Validée" },
    };
    const m = map[s] || { cls: "bg-gray-100 text-gray-700", label: s };
    return <span className={`text-xs px-2 py-0.5 rounded-full ${m.cls}`}>{m.label}</span>;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{tasks.length} tâches</p>
        <span className="text-xs text-slate-400">Les tâches sont créées depuis RH & Paie</span>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-2 text-xs text-gray-500">Titre</th>
                <th className="text-left px-4 py-2 text-xs text-gray-500">Employé</th>
                <th className="text-center px-4 py-2 text-xs text-gray-500">Type</th>
                <th className="text-center px-4 py-2 text-xs text-gray-500">Échéance</th>
                <th className="text-center px-4 py-2 text-xs text-gray-500">Statut</th>
                <th className="text-center px-4 py-2 text-xs text-gray-500">Approbation</th>
                <th className="text-right px-4 py-2 text-xs text-gray-500">Estimation</th>
                <th className="text-right px-4 py-2 text-xs text-gray-500">Score IA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Chargement…</td></tr>
              ) : tasks.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Aucune tâche assignée</td></tr>
              ) : tasks.map(t => {
                const overdue = t.due_date && new Date(t.due_date) < new Date() && t.status !== "completed";
                return (
                <tr key={t.id} className={`hover:bg-gray-50 ${overdue ? "bg-red-50" : ""}`}>
                  <td className="px-4 py-2 font-medium">{t.title}</td>
                  <td className="px-4 py-2 text-gray-600">{t.employee_name || "—"}</td>
                  <td className="px-4 py-2 text-center text-xs text-gray-500">{t.task_type || "—"}</td>
                  <td className="px-4 py-2 text-center text-xs">
                    {t.due_date ? new Date(t.due_date).toLocaleDateString("fr-FR") : "—"}
                    {overdue && <span className="block text-red-500 text-xs">En retard</span>}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statutBadge(t.status)}`}>{t.status}</span>
                  </td>
                  <td className="px-4 py-2 text-center">{approvalLabel(t.approval_status)}</td>
                  <td className="px-4 py-2 text-right text-xs">
                    {t.manager_final_time != null ? (
                      <span>{t.manager_final_time}h / {fmt(t.manager_final_price || 0)} DA</span>
                    ) : t.employee_estimated_time != null ? (
                      <span className="text-blue-600">{t.employee_estimated_time}h / {fmt(t.employee_estimated_price || 0)} DA</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {t.ai_score != null ? (
                      <span className={`text-sm font-bold ${spiColor(t.ai_score)}`}>{t.ai_score}</span>
                    ) : "—"}
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ── Plans Section ──────────────────────────────────────────────── */

function PlansSection({ plans, showForm, setShowForm, onReload }: {
  plans: PlanStrategique[];
  showForm: boolean;
  setShowForm: (v: boolean) => void;
  onReload: () => void;
}) {
  const [form, setForm] = useState({ titre: "", description: "", horizon: "MOIS_3", objectif_mesurable: "" });

  const createPlan = async () => {
    try {
      await api.post("/planification/plans", form);
      setShowForm(false);
      setForm({ titre: "", description: "", horizon: "MOIS_3", objectif_mesurable: "" });
      onReload();
    } catch (e: any) { alert(e?.response?.data?.detail || "Erreur"); }
  };

  const validerPlan = async (planId: string, decision: string) => {
    try {
      const justification = decision === "DECLINE" ? prompt("Justification du refus:") : undefined;
      if (decision === "DECLINE" && !justification) return;
      await api.put(`/planification/plans/${planId}/valider`, { decision, justification });
      onReload();
    } catch (e: any) { alert(e?.response?.data?.detail || "Erreur"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{plans.length} plans strategiques</p>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1 text-sm">
          <LightBulbIcon className="w-4 h-4" /> Proposer un plan
        </button>
      </div>

      {showForm && (
        <div className="card p-4 space-y-3 border-2 border-teal-200">
          <h3 className="text-sm font-semibold text-gray-700">Proposer un plan strategique</h3>
          <input className="input-field w-full" placeholder="Titre du plan" value={form.titre}
            onChange={e => setForm({ ...form, titre: e.target.value })} />
          <textarea className="input-field w-full" rows={3} placeholder="Description detaillee (min 50 caracteres)"
            value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <input className="input-field" placeholder="Objectif mesurable" value={form.objectif_mesurable}
              onChange={e => setForm({ ...form, objectif_mesurable: e.target.value })} />
            <select className="input-field" value={form.horizon}
              onChange={e => setForm({ ...form, horizon: e.target.value })}>
              <option value="MOIS_1">1 mois</option>
              <option value="MOIS_3">3 mois</option>
              <option value="MOIS_6">6 mois</option>
              <option value="MOIS_12">12 mois</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={createPlan} className="btn-primary text-sm">Soumettre</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {plans.map(p => (
          <div key={p.id} className="card p-4 space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-gray-400 font-mono">{p.reference}</p>
                <p className="font-semibold text-gray-900">{p.titre}</p>
                <p className="text-xs text-gray-500 mt-1">par {p.proposeur_nom} — {p.date_proposition?.slice(0, 10)}</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${statutBadge(p.statut)}`}>{p.statut}</span>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2">{p.description}</p>
            {p.objectif_smart && (
              <div className="rounded-lg bg-teal-50 border border-teal-200 p-3">
                <p className="text-xs font-semibold text-teal-800 mb-1">Objectif SMART (IA)</p>
                <p className="text-sm text-teal-700">{p.objectif_smart}</p>
              </div>
            )}
            {(p.score_pertinence > 0 || p.faisabilite > 0) && (
              <div className="flex gap-4 text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Pertinence IA:</span>
                  <span className={`font-bold ${p.score_pertinence >= 70 ? "text-green-600" : p.score_pertinence >= 40 ? "text-amber-600" : "text-red-600"}`}>{p.score_pertinence}/100</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Faisabilité:</span>
                  <span className={`font-bold ${p.faisabilite >= 70 ? "text-green-600" : p.faisabilite >= 40 ? "text-amber-600" : "text-red-600"}`}>{p.faisabilite}/100</span>
                </div>
              </div>
            )}
            {p.ameliorations && (
              <div className="rounded-lg bg-violet-50 border border-violet-200 p-3">
                <p className="text-xs font-semibold text-violet-800 mb-1">Suggestions IA</p>
                <p className="text-xs text-violet-700">{p.ameliorations}</p>
              </div>
            )}
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Horizon: {p.horizon?.replace("MOIS_", "") || "?"} mois</span>
              {p.prime_versee && (
                <span className="text-teal-600 font-semibold">Prime: {fmt(p.montant_prime)} DA</span>
              )}
            </div>
            {p.statut === "SOUMIS" && (
              <div className="flex gap-2 pt-2 border-t border-gray-100">
                <button onClick={() => validerPlan(p.id, "VALIDE")} className="text-xs btn-primary px-3 py-1">Valider</button>
                <button onClick={() => validerPlan(p.id, "DECLINE")} className="text-xs text-red-600 hover:text-red-800">Decliner</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {plans.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          Aucun plan strategique. Tout le monde peut en proposer un!
        </div>
      )}
    </div>
  );
}

/* ── Alertes Section ────────────────────────────────────────────── */

function AlertesSection({ alertes, onTraiter }: { alertes: AlerteRH[]; onTraiter: (id: string) => void }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">{alertes.length} alertes non traitees</p>

      {alertes.map(a => (
        <div key={a.id} className={`card p-4 border-l-4 ${
          a.severite === "CRITICAL" ? "border-l-red-500 bg-red-50" :
          a.severite === "WARNING" ? "border-l-orange-500 bg-orange-50" :
          "border-l-blue-500 bg-blue-50"
        }`}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  a.type === "RUPTURE_SPI" ? "bg-red-200 text-red-800" :
                  a.type === "AVERTISSEMENT" ? "bg-orange-200 text-orange-800" :
                  a.type === "SURVEILLANCE" ? "bg-amber-200 text-amber-800" :
                  a.type === "PROTECTION" ? "bg-emerald-200 text-emerald-800" :
                  "bg-gray-200 text-gray-800"
                }`}>{a.type}</span>
                <span className="text-xs text-gray-500">{a.employe_nom} — {a.mois}</span>
              </div>
              <p className="text-sm text-gray-800">{a.message}</p>
              {a.score_spi != null && (
                <p className={`text-xs mt-1 font-medium ${spiColor(a.score_spi)}`}>SPI: {a.score_spi}/100</p>
              )}
            </div>
            {!a.est_traitee && (
              <button onClick={() => onTraiter(a.id)} className="text-xs btn-secondary px-3 py-1 shrink-0">
                Traiter
              </button>
            )}
          </div>
        </div>
      ))}

      {alertes.length === 0 && (
        <div className="text-center py-12 text-gray-400">Aucune alerte en attente</div>
      )}
    </div>
  );
}
