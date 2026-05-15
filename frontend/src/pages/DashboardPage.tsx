import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowTrendingUpIcon,
  BanknotesIcon,
  BriefcaseIcon,
  BuildingOffice2Icon,
  ExclamationTriangleIcon,
  SparklesIcon,
  UserGroupIcon,
} from "@heroicons/react/24/outline";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  AreaChart, Area,
  RadialBarChart, RadialBar,
} from "recharts";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";

/* ── Types ──────────────────────────────────────────────────────── */

interface AdminStats {
  documents: number;
  workflows_total: number;
  workflows_committed: number;
  workflows_blocked: number;
  journal_entries: number;
  users: number;
}

interface AdvDashboard {
  clients_count: number;
  active_contracts: number;
  total_receivable: number;
  overdue_amount: number;
}

interface CostCenterDashboard {
  periode: string;
  nb_projets_actifs: number;
  nb_clients: number;
  ca_mois: number;
  transit_notaire: number;
  resultat_mois: number;
}

interface SpiDashboard {
  mois: string;
  total_employees: number;
  average_spi: number;
  top_performers: Array<{ employee_id: string; employee_name: string | null; score_spi: number; department: string | null }>;
  low_performers: Array<{ employee_id: string; employee_name: string | null; score_spi: number; department: string | null }>;
  alerts: Array<{ type: string; message: string }>;
  distribution: Record<string, number>;
}

interface TacheItem {
  id: string;
  titre: string;
  statut: string;
  priorite: string;
  assignee_nom: string | null;
  score_execution: number | null;
  score_qualite: number | null;
}

interface SpiScore {
  id: string;
  employee_name: string | null;
  employee_id: string;
  department: string | null;
  score_spi: number;
  c1_execution: number;
  c2_qualite: number;
  c3_comportement: number;
  c4_metier: number;
  mois: string;
}

interface PaymentItem {
  id: string;
  amount: number;
  payment_date: string;
  client_id: string;
}

/* ── Helpers ────────────────────────────────────────────────────── */

function fmt(value: number | null | undefined) {
  if (value == null) return "0";
  if (Math.abs(value) >= 1_000_000)
    return (value / 1_000_000).toFixed(1) + "M";
  if (Math.abs(value) >= 1_000)
    return (value / 1_000).toFixed(0) + "K";
  return value.toFixed(0);
}

function fmtDA(value: number | null | undefined) {
  if (value == null) return "0 DA";
  return new Intl.NumberFormat("fr-DZ", { maximumFractionDigits: 0 }).format(value) + " DA";
}

const COLORS = ["#0d9488", "#6366f1", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];
const SPI_COLORS = { excellent: "#059669", bon: "#0d9488", moyen: "#f59e0b", faible: "#ef4444" };

/* ── Component ──────────────────────────────────────────────────── */

export default function DashboardPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [adv, setAdv] = useState<AdvDashboard | null>(null);
  const [costCenter, setCostCenter] = useState<CostCenterDashboard | null>(null);
  const [spi, setSpi] = useState<SpiDashboard | null>(null);
  const [taches, setTaches] = useState<TacheItem[]>([]);
  const [spiScores, setSpiScores] = useState<SpiScore[]>([]);
  const [payments, setPayments] = useState<PaymentItem[]>([]);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    const requests = await Promise.allSettled([
      api.get("/adv/dashboard"),
      api.get("/cost-center/dashboard"),
      api.get("/spi/dashboard"),
      api.get("/planification/taches"),
      api.get("/spi/scores"),
      api.get("/adv/payments"),
      user?.role === "admin" || user?.role === "SUPER_ADMIN" ? api.get("/admin/stats") : Promise.resolve({ data: null }),
    ]);

    const [advRes, ccRes, spiRes, tachesRes, scoresRes, paymentsRes, adminRes] = requests;
    setAdv(advRes.status === "fulfilled" ? advRes.value.data : null);
    setCostCenter(ccRes.status === "fulfilled" ? ccRes.value.data : null);
    setSpi(spiRes.status === "fulfilled" ? spiRes.value.data : null);
    setTaches(tachesRes.status === "fulfilled" ? (tachesRes.value.data ?? []) : []);
    setSpiScores(scoresRes.status === "fulfilled" ? (scoresRes.value.data ?? []) : []);
    setPayments(paymentsRes.status === "fulfilled" ? (paymentsRes.value.data ?? []) : []);
    setAdminStats(adminRes.status === "fulfilled" ? adminRes.value.data : null);
    setLoading(false);
  }, [user?.role]);

  useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  /* ── Computed chart data ── */

  const taskStatusData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of taches) {
      const label = {
        VALIDEE: "Validee", EN_COURS: "En cours", EN_REVUE: "En revue",
        ASSIGNEE: "Assignee", REJETEE: "Rejetee", ANNULEE: "Annulee",
        VERROUILLEE: "Verrouillee", OFFRE_EN_COURS: "Offre",
      }[t.statut] ?? t.statut;
      counts[label] = (counts[label] || 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [taches]);

  const taskPriorityData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of taches) {
      counts[t.priorite] = (counts[t.priorite] || 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [taches]);

  const spiDistributionData = useMemo(() => {
    const brackets = { "90-100 (Excellent)": 0, "70-89 (Bon)": 0, "50-69 (Moyen)": 0, "0-49 (Faible)": 0 };
    for (const s of spiScores) {
      const v = s.score_spi;
      if (v >= 90) brackets["90-100 (Excellent)"]++;
      else if (v >= 70) brackets["70-89 (Bon)"]++;
      else if (v >= 50) brackets["50-69 (Moyen)"]++;
      else brackets["0-49 (Faible)"]++;
    }
    return Object.entries(brackets).map(([name, value]) => ({ name, value }));
  }, [spiScores]);

  const spiComponentsData = useMemo(() => {
    // Group by employee, take latest month
    const byEmp = new Map<string, SpiScore>();
    for (const s of spiScores) {
      const key = s.employee_id ?? s.employee_name ?? s.id;
      const existing = byEmp.get(key);
      if (!existing || s.mois > existing.mois) {
        byEmp.set(key, s);
      }
    }
    return Array.from(byEmp.values())
      .sort((a, b) => b.score_spi - a.score_spi)
      .slice(0, 8)
      .map(s => ({
        name: (s.employee_name ?? "Employe").split(" ").slice(-1)[0],
        C1: Number(s.c1_execution) || 0,
        C2: Number(s.c2_qualite) || 0,
        C3: Number(s.c3_comportement) || 0,
        C4: Number(s.c4_metier) || 0,
        SPI: Number(s.score_spi) || 0,
      }));
  }, [spiScores]);

  const monthlyPayments = useMemo(() => {
    const byMonth: Record<string, number> = {};
    for (const p of payments) {
      const month = p.payment_date?.substring(0, 7) ?? "N/A";
      byMonth[month] = (byMonth[month] || 0) + Number(p.amount);
    }
    return Object.entries(byMonth)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, total]) => ({ month, total }));
  }, [payments]);

  const receivableGauge = useMemo(() => {
    const total = adv?.total_receivable ?? 0;
    const overdue = adv?.overdue_amount ?? 0;
    const pct = total > 0 ? Math.round(((total - overdue) / total) * 100) : 100;
    return [{ name: "Recouvrement", value: pct, fill: pct > 70 ? "#059669" : pct > 40 ? "#f59e0b" : "#ef4444" }];
  }, [adv]);

  /* ── KPI Cards ── */
  const kpis = [
    { label: "CA du mois", value: fmt(costCenter?.ca_mois), sub: costCenter?.periode ?? "", icon: BanknotesIcon, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Resultat", value: fmt(costCenter?.resultat_mois), sub: "ultra-reel", icon: ArrowTrendingUpIcon, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Projets actifs", value: String(costCenter?.nb_projets_actifs ?? 0), sub: `${costCenter?.nb_clients ?? 0} clients`, icon: BriefcaseIcon, color: "text-violet-600", bg: "bg-violet-50" },
    { label: "SPI moyen", value: String(Math.round(spi?.average_spi ?? 0)), sub: `${spi?.total_employees ?? 0} employes`, icon: SparklesIcon, color: "text-fuchsia-600", bg: "bg-fuchsia-50" },
    { label: "Alertes", value: String(spi?.alerts?.length ?? 0), sub: "RH actives", icon: ExclamationTriangleIcon, color: "text-amber-600", bg: "bg-amber-50" },
    { label: "Utilisateurs", value: String(adminStats?.users ?? adv?.clients_count ?? 0), sub: "plateforme", icon: UserGroupIcon, color: "text-slate-600", bg: "bg-slate-100" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Vue d'ensemble — performances, finances, operations</p>
        </div>
        <button onClick={() => void fetchDashboard()} className="btn-secondary text-xs flex items-center gap-1.5">
          <ArrowTrendingUpIcon className="h-4 w-4" /> Actualiser
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {kpis.map((k) => (
          <div key={k.label} className="card p-4">
            <div className="flex items-center gap-2">
              <div className={`rounded-lg p-2 ${k.bg}`}>
                <k.icon className={`h-4 w-4 ${k.color}`} />
              </div>
              <span className="text-xs text-slate-500">{k.label}</span>
            </div>
            <p className="mt-2 text-xl font-bold text-slate-900">{loading ? "..." : k.value}</p>
            <p className="text-xs text-slate-400">{k.sub}</p>
          </div>
        ))}
      </div>

      {/* Row 1: Revenue + Task Status */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Monthly Revenue */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Encaissements par mois</h2>
          {monthlyPayments.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={monthlyPayments} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmt(v)} />
                <Tooltip formatter={(v) => fmtDA(Number(v))} labelFormatter={(l) => `Mois: ${l}`} />
                <Bar dataKey="total" fill="#0d9488" radius={[4, 4, 0, 0]} name="Montant" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[240px] text-slate-400 text-sm">Aucun paiement enregistre</div>
          )}
        </div>

        {/* Task Status Distribution */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Taches par statut</h2>
          {taskStatusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={taskStatusData} cx="50%" cy="50%" outerRadius={85} innerRadius={45} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {taskStatusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[240px] text-slate-400 text-sm">Aucune tache</div>
          )}
        </div>
      </div>

      {/* Row 2: SPI Components + SPI Distribution */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* SPI by Employee (stacked bar) */}
        <div className="card p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">SPI par employe (C1-C4)</h2>
          {spiComponentsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={spiComponentsData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="C1" stackId="spi" fill="#0d9488" name="C1 Execution" radius={[0, 0, 0, 0]} />
                <Bar dataKey="C2" stackId="spi" fill="#6366f1" name="C2 Qualite" />
                <Bar dataKey="C3" stackId="spi" fill="#f59e0b" name="C3 Comportement" />
                <Bar dataKey="C4" stackId="spi" fill="#ec4899" name="C4 Metier" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-slate-400 text-sm">Aucun score SPI</div>
          )}
        </div>

        {/* SPI Distribution Donut */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Repartition SPI</h2>
          {spiScores.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={spiDistributionData} cx="50%" cy="50%" outerRadius={80} innerRadius={40} paddingAngle={2} dataKey="value" label={({ name, value }) => value > 0 ? `${value}` : ""}>
                  {spiDistributionData.map((_, i) => (
                    <Cell key={i} fill={[SPI_COLORS.excellent, SPI_COLORS.bon, SPI_COLORS.moyen, SPI_COLORS.faible][i]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-slate-400 text-sm">Aucun score</div>
          )}
        </div>
      </div>

      {/* Row 3: ADV + Top/Low SPI + Alerts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ADV Recouvrement Gauge + Stats */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">ADV & Tresorerie</h2>
          <div className="flex items-center gap-4">
            <div className="w-24 h-24">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={receivableGauge} startAngle={180} endAngle={0}>
                  <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "#f1f5f9" }} />
                </RadialBarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{receivableGauge[0].value}%</p>
              <p className="text-xs text-slate-500">Taux recouvrement</p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Clients</span>
              <span className="font-semibold text-slate-800">{adv?.clients_count ?? 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Contrats actifs</span>
              <span className="font-semibold text-slate-800">{adv?.active_contracts ?? 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Creances totales</span>
              <span className="font-semibold text-slate-800">{fmtDA(adv?.total_receivable)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Impayes</span>
              <span className="font-semibold text-red-600">{fmtDA(adv?.overdue_amount)}</span>
            </div>
          </div>
          <Link to="/adv" className="mt-3 block text-xs text-center text-teal-600 hover:text-teal-700 font-medium">
            Voir ADV &rarr;
          </Link>
        </div>

        {/* Top SPI Performers */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Top Performers SPI</h2>
          <div className="space-y-2">
            {(spi?.top_performers ?? []).slice(0, 6).map((p, i) => (
              <div key={p.employee_id} className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${i === 0 ? "bg-amber-500" : i === 1 ? "bg-slate-400" : i === 2 ? "bg-amber-700" : "bg-slate-300"}`}>
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{p.employee_name ?? "Employe"}</p>
                  <p className="text-xs text-slate-400">{p.department ?? ""}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-emerald-600">{Math.round(p.score_spi)}</p>
                </div>
              </div>
            ))}
            {!(spi?.top_performers?.length) && <p className="text-sm text-slate-400">Aucune donnee</p>}
          </div>
        </div>

        {/* Alerts & Low Performers */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Alertes & Sous-performance</h2>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {(spi?.alerts ?? []).slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-red-50 p-2">
                <ExclamationTriangleIcon className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                <p className="text-xs text-red-700">{a.message}</p>
              </div>
            ))}
            {!(spi?.alerts?.length) && <p className="text-xs text-emerald-600">Aucune alerte active</p>}
          </div>
          {(spi?.low_performers?.length ?? 0) > 0 && (
            <>
              <h3 className="text-xs font-semibold text-slate-500 mt-4 mb-2">A surveiller</h3>
              <div className="space-y-1.5">
                {spi!.low_performers.slice(0, 4).map((p) => (
                  <div key={p.employee_id} className="flex items-center justify-between rounded-lg bg-amber-50 px-2 py-1.5">
                    <span className="text-xs text-slate-700 truncate">{p.employee_name ?? "Employe"}</span>
                    <span className="text-xs font-bold text-red-600">{Math.round(p.score_spi)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          <Link to="/spi" className="mt-3 block text-xs text-center text-teal-600 hover:text-teal-700 font-medium">
            Voir SPI 360 &rarr;
          </Link>
        </div>
      </div>

      {/* Row 4: Task Priority + Quick Links */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Taches par priorite</h2>
          {taskPriorityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={taskPriorityData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} name="Nombre" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-slate-400 text-sm">Aucune tache</div>
          )}
        </div>

        {/* Centre de Cout Summary */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Centre de Cout</h2>
          <div className="space-y-3">
            <div className="rounded-lg bg-emerald-50 p-3">
              <p className="text-xs text-emerald-600">Chiffre d'affaires</p>
              <p className="text-lg font-bold text-slate-900">{fmtDA(costCenter?.ca_mois)}</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3">
              <p className="text-xs text-blue-600">Resultat ultra-reel</p>
              <p className="text-lg font-bold text-slate-900">{fmtDA(costCenter?.resultat_mois)}</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-3">
              <p className="text-xs text-amber-600">Transit notaire</p>
              <p className="text-lg font-bold text-slate-900">{fmtDA(costCenter?.transit_notaire)}</p>
            </div>
          </div>
          <Link to="/cost-center" className="mt-3 block text-xs text-center text-teal-600 hover:text-teal-700 font-medium">
            Voir Centre de Cout &rarr;
          </Link>
        </div>

        {/* Quick Access */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Acces rapide</h2>
          <div className="grid grid-cols-2 gap-2">
            {[
              { to: "/hr", label: "RH & Paie", icon: UserGroupIcon, color: "text-violet-600" },
              { to: "/adv", label: "ADV", icon: BanknotesIcon, color: "text-emerald-600" },
              { to: "/cost-center", label: "Centre de Cout", icon: BuildingOffice2Icon, color: "text-blue-600" },
              { to: "/spi", label: "SPI 360", icon: SparklesIcon, color: "text-fuchsia-600" },
              { to: "/planification", label: "Planification", icon: BriefcaseIcon, color: "text-amber-600" },
              { to: "/documents", label: "Documents", icon: ArrowTrendingUpIcon, color: "text-teal-600" },
            ].map((item) => (
              <Link key={item.to} to={item.to} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors">
                <item.icon className={`h-4 w-4 ${item.color}`} />
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
