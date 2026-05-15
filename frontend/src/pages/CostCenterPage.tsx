import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  ChartBarIcon,
  ArrowPathIcon,
  BuildingOffice2Icon,
  ChevronRightIcon,
  ChevronDownIcon,
  UserGroupIcon,
  CurrencyDollarIcon,
  EyeIcon,
  FolderOpenIcon,
  ArrowTrendingUpIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";

/* ── Types ── */

interface DashboardData {
  groupe: {
    encaissements: number;
    decaissements: number;
    cff_total: number;
    solde_net: number;
    solde_officiel: number;
    marge_brute_pct: number;
  };
  associes: AssocieConsolidation[];
  top_projets: TopProjet[];
  entreprises: EntrepriseRow[];
  periode: string;
}

interface AssocieConsolidation {
  associe_id: string;
  nom: string;
  qp_encaissements: number;
  qp_decaissements: number;
  qp_cff: number;
  qp_net: number;
  nb_projets: number;
}

interface TopProjet {
  code: string;
  libelle: string;
  encaissements: number;
  decaissements: number;
  solde_net: number;
  marge_brute_pct: number;
  cff_total: number;
  poids_rf2_pct: number;
}

interface EntrepriseRow {
  code: string;
  libelle: string;
  encaissements: number;
  decaissements: number;
  solde_net: number;
  cff_total: number;
  marge_brute_pct: number;
  nb_projets: number;
}

interface CCTreeNode {
  id: string;
  code: string;
  libelle: string;
  niveau: number;
  parent_id: string | null;
  entreprise_id: string | null;
  projet_id: string | null;
  associe_id: string | null;
  categorie: string | null;
  est_actif: boolean;
  chemin: string;
}

interface NodeDetail {
  node_id: string;
  code: string;
  libelle: string;
  niveau: number;
  encaissements: number;
  decaissements: number;
  cff_total: number;
  solde_net: number;
  encaissements_officiel: number;
  decaissements_officiel: number;
  solde_officiel: number;
  encaissements_rf1: number;
  encaissements_rf2: number;
  decaissements_rf1: number;
  decaissements_rf2: number;
  marge_brute_pct: number;
  impact_cff_pct: number;
  poids_rf2_pct: number;
  masse_salariale?: number;
  quote_parts?: QuotePart[];
  projets?: NodeDetail[];
}

interface QuotePart {
  associe_id: string;
  nom: string;
  pct_projet: number;
  pct_entreprise: number;
  qp_encaissements: number;
  qp_decaissements: number;
  qp_cff: number;
  qp_solde_net: number;
  qp_net_apres_cff: number;
}

/* ── Helpers ── */

function fmt(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
}

function fmtDA(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return fmt(n) + " DA";
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return n.toFixed(1) + "%";
}

function signColor(n: number): string {
  if (n > 0) return "text-emerald-600";
  if (n < 0) return "text-red-600";
  return "text-slate-500";
}

function margeColor(pct: number): string {
  if (pct >= 30) return "bg-emerald-500";
  if (pct >= 15) return "bg-amber-500";
  if (pct >= 0) return "bg-orange-500";
  return "bg-red-500";
}

const CATEGORIE_ICONS: Record<string, string> = {
  TERRAIN: "🏗️", CONSTR: "🔨", COMMERCIAL: "📢", VENTES: "💰",
  ASSOC: "👥", CFF: "📄", FISCAL: "🏛️", ADMIN: "📋",
  MASSE_SAL: "💼", LOCAUX: "🏢", ACHATS: "🛒", VEHICULES: "🚗",
  SIEGE: "🏢", DIVERS: "📦", INTER_PROJ: "🔄", STOCK: "📦",
  ASSURANCE: "🛡️",
};

type Tab = "dashboard" | "arbre" | "associes" | "entreprises";

/* ── Main Component ── */

export default function CostCenterPage() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [loading, setLoading] = useState(false);
  const [periode, setPeriode] = useState("");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tree, setTree] = useState<CCTreeNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<NodeDetail | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  /* ── Load dashboard ── */
  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const params = periode ? { periode } : {};
      const { data } = await api.get("/cc/dashboard/daf", { params });
      setDashboard(data);
    } catch (e) {
      console.error("Dashboard load error:", e);
    } finally {
      setLoading(false);
    }
  }, [periode]);

  /* ── Load tree ── */
  const loadTree = useCallback(async () => {
    try {
      const { data } = await api.get("/cc/arbre");
      setTree(data);
      // Auto-expand first 2 levels
      const expanded = new Set<string>();
      data.forEach((n: CCTreeNode) => { if (n.niveau <= 1) expanded.add(n.id); });
      setExpandedNodes(expanded);
    } catch (e) {
      console.error("Tree load error:", e);
    }
  }, []);

  /* ── Load node detail ── */
  const loadNodeDetail = async (nodeId: string) => {
    try {
      const params = periode ? { periode } : {};
      const { data } = await api.get(`/cc/node/${nodeId}`, { params });
      setSelectedNode(data);
    } catch { setSelectedNode(null); }
  };

  useEffect(() => {
    if (tab === "dashboard" || tab === "associes" || tab === "entreprises") loadDashboard();
    if (tab === "arbre") loadTree();
  }, [tab, loadDashboard, loadTree]);

  const toggleExpand = (id: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "dashboard", label: "Dashboard DAF", icon: <ChartBarIcon className="h-4 w-4" /> },
    { key: "arbre", label: "Arbre CC", icon: <FolderOpenIcon className="h-4 w-4" /> },
    { key: "associes", label: "Par Associe", icon: <UserGroupIcon className="h-4 w-4" /> },
    { key: "entreprises", label: "Par Entreprise", icon: <BuildingOffice2Icon className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Centre de Cout</h1>
          <p className="mt-1 text-sm text-slate-500">
            Vue hierarchique dynamique — {dashboard?.periode === "cumul" ? "Cumul total" : dashboard?.periode || "Toutes periodes"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="month"
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
            className="input-field text-sm"
            placeholder="Toutes periodes"
          />
          <button onClick={loadDashboard} className="btn-secondary text-sm" disabled={loading}>
            <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <ArrowPathIcon className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      )}

      {/* ═══════════ Dashboard Tab ═══════════ */}
      {tab === "dashboard" && dashboard && !loading && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <KPICard label="Encaissements" value={dashboard.groupe.encaissements} color="emerald" />
            <KPICard label="Decaissements" value={dashboard.groupe.decaissements} color="red" />
            <KPICard label="CFF Total" value={dashboard.groupe.cff_total} color="amber" />
            <KPICard label="Solde Net" value={dashboard.groupe.solde_net} color="blue" signed />
            <KPICard label="Marge Brute" value={dashboard.groupe.marge_brute_pct} color="violet" isPct />
          </div>

          {/* Double Vue: Official vs Internal */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <EyeIcon className="h-4 w-4 text-blue-500" />
                Vue Officielle (RF1 + RF3)
              </h3>
              <div className="space-y-2">
                <Row label="Encaissements" value={dashboard.groupe.solde_officiel} />
              </div>
              <p className="text-xs text-slate-400 mt-3">Comptabilite declaree uniquement</p>
            </div>
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <EyeIcon className="h-4 w-4 text-violet-500" />
                Vue Interne (RF1+RF2+RF3+RF4)
              </h3>
              <div className="space-y-2">
                <Row label="Encaissements" value={dashboard.groupe.encaissements} />
                <Row label="Decaissements" value={-dashboard.groupe.decaissements} />
                <Row label="CFF" value={-dashboard.groupe.cff_total} />
                <div className="border-t pt-2">
                  <Row label="Solde Net Reel" value={dashboard.groupe.solde_net} bold />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Realite complete incluant RF2</p>
            </div>
          </div>

          {/* Associates */}
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <UserGroupIcon className="h-4 w-4 text-indigo-500" />
              Consolidation par Associe (net apres CFF)
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {dashboard.associes.map((a) => (
                <div key={a.associe_id} className="rounded-xl border border-slate-200 p-4 hover:border-indigo-300 transition-colors">
                  <p className="text-sm font-bold text-slate-800">{a.nom}</p>
                  <p className={`text-xl font-bold mt-1 ${signColor(a.qp_net)}`}>{fmtDA(a.qp_net)}</p>
                  <div className="mt-2 space-y-1 text-xs text-slate-500">
                    <div className="flex justify-between"><span>Encaissements</span><span className="text-emerald-600">+{fmt(a.qp_encaissements)}</span></div>
                    <div className="flex justify-between"><span>Decaissements</span><span className="text-red-600">-{fmt(a.qp_decaissements)}</span></div>
                    <div className="flex justify-between"><span>CFF</span><span className="text-amber-600">-{fmt(a.qp_cff)}</span></div>
                  </div>
                  <p className="text-xs text-slate-400 mt-2">{a.nb_projets} projet(s)</p>
                </div>
              ))}
            </div>
          </div>

          {/* Top Projects */}
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <ArrowTrendingUpIcon className="h-4 w-4 text-emerald-500" />
              Top Projets par Marge
            </h3>
            <div className="space-y-3">
              {dashboard.top_projets.map((p, i) => (
                <div key={p.code} className="flex items-center gap-4 rounded-lg border border-slate-100 p-3 hover:bg-slate-50">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{p.libelle}</p>
                    <p className="text-xs text-slate-500">{p.code}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-bold ${signColor(p.solde_net)}`}>{fmtDA(p.solde_net)}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="h-1.5 w-16 rounded-full bg-slate-200 overflow-hidden">
                        <div className={`h-full rounded-full ${margeColor(p.marge_brute_pct)}`} style={{ width: `${Math.min(Math.max(p.marge_brute_pct, 0), 100)}%` }} />
                      </div>
                      <span className="text-xs text-slate-600">{fmtPct(p.marge_brute_pct)}</span>
                    </div>
                  </div>
                  {p.poids_rf2_pct > 0 && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                      RF2: {fmtPct(p.poids_rf2_pct)}
                    </span>
                  )}
                </div>
              ))}
              {dashboard.top_projets.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-4">Aucune donnee projet</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════ Arbre CC Tab ═══════════ */}
      {tab === "arbre" && !loading && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Tree panel */}
          <div className="card p-4 lg:col-span-1 max-h-[75vh] overflow-y-auto">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Hierarchie CC</h3>
            <TreeView
              nodes={tree}
              expanded={expandedNodes}
              onToggle={toggleExpand}
              onSelect={(id) => loadNodeDetail(id)}
              selectedId={selectedNode?.node_id}
            />
          </div>

          {/* Detail panel */}
          <div className="lg:col-span-2">
            {selectedNode ? (
              <NodeDetailPanel node={selectedNode} />
            ) : (
              <div className="card p-8 text-center text-slate-400">
                <FolderOpenIcon className="h-12 w-12 mx-auto mb-3 text-slate-300" />
                <p>Selectionnez un noeud dans l'arbre pour voir le detail</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════ Associes Tab ═══════════ */}
      {tab === "associes" && dashboard && !loading && (
        <div className="space-y-4">
          {dashboard.associes.map((a) => (
            <div key={a.associe_id} className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{a.nom}</h3>
                  <p className="text-sm text-slate-500">{a.nb_projets} projet(s) actif(s)</p>
                </div>
                <div className="text-right">
                  <p className={`text-2xl font-bold ${signColor(a.qp_net)}`}>{fmtDA(a.qp_net)}</p>
                  <p className="text-xs text-slate-500">Net apres CFF</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg bg-emerald-50 p-3 text-center">
                  <p className="text-xs text-emerald-600 font-medium">Quote-part Encaissements</p>
                  <p className="text-lg font-bold text-emerald-700">{fmtDA(a.qp_encaissements)}</p>
                </div>
                <div className="rounded-lg bg-red-50 p-3 text-center">
                  <p className="text-xs text-red-600 font-medium">Quote-part Decaissements</p>
                  <p className="text-lg font-bold text-red-700">{fmtDA(a.qp_decaissements)}</p>
                </div>
                <div className="rounded-lg bg-amber-50 p-3 text-center">
                  <p className="text-xs text-amber-600 font-medium">CFF Impute</p>
                  <p className="text-lg font-bold text-amber-700">{fmtDA(a.qp_cff)}</p>
                </div>
              </div>
            </div>
          ))}
          {dashboard.associes.length === 0 && (
            <div className="card p-8 text-center text-slate-400">Aucune donnee associe</div>
          )}
        </div>
      )}

      {/* ═══════════ Entreprises Tab ═══════════ */}
      {tab === "entreprises" && dashboard && !loading && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">Entreprise</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Encaissements</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Decaissements</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">CFF</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Solde Net</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Marge</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600">Projets</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.entreprises.map((e) => (
                <tr key={e.code} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{e.libelle}</p>
                    <p className="text-xs text-slate-400">{e.code}</p>
                  </td>
                  <td className="px-4 py-3 text-right text-emerald-600">{fmtDA(e.encaissements)}</td>
                  <td className="px-4 py-3 text-right text-red-600">{fmtDA(e.decaissements)}</td>
                  <td className="px-4 py-3 text-right text-amber-600">{fmtDA(e.cff_total)}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${signColor(e.solde_net)}`}>{fmtDA(e.solde_net)}</td>
                  <td className="px-4 py-3 text-right">{fmtPct(e.marge_brute_pct)}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                      {e.nb_projets}
                    </span>
                  </td>
                </tr>
              ))}
              {dashboard.entreprises.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune entreprise</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════ */

function KPICard({ label, value, color, signed, isPct }: {
  label: string; value: number; color: string; signed?: boolean; isPct?: boolean;
}) {
  const colors: Record<string, string> = {
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    red: "border-red-200 bg-red-50 text-red-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    violet: "border-violet-200 bg-violet-50 text-violet-700",
  };

  return (
    <div className={`rounded-xl border p-4 ${colors[color] || colors.blue}`}>
      <p className="text-xs font-medium opacity-80">{label}</p>
      <p className={`mt-1 text-xl font-bold ${signed ? signColor(value) : ""}`}>
        {isPct ? fmtPct(value) : fmtDA(value)}
      </p>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className={`text-sm ${bold ? "font-semibold text-slate-800" : "text-slate-600"}`}>{label}</span>
      <span className={`text-sm ${bold ? "font-bold" : "font-medium"} ${signColor(value)}`}>{fmtDA(value)}</span>
    </div>
  );
}


/* ── Tree View ── */

function TreeView({ nodes, expanded, onToggle, onSelect, selectedId }: {
  nodes: CCTreeNode[];
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  // Build nested structure
  const nodeMap = new Map<string | null, CCTreeNode[]>();
  nodes.forEach((n) => {
    const pid = n.parent_id;
    if (!nodeMap.has(pid)) nodeMap.set(pid, []);
    nodeMap.get(pid)!.push(n);
  });

  const renderNode = (node: CCTreeNode, depth: number) => {
    const children = nodeMap.get(node.id) || [];
    const hasChildren = children.length > 0;
    const isExpanded = expanded.has(node.id);
    const isSelected = node.id === selectedId;

    const icon = node.categorie ? CATEGORIE_ICONS[node.categorie] || "" : "";
    const levelColors = [
      "text-slate-900 font-bold",    // 0 - group
      "text-slate-800 font-semibold", // 1 - enterprise
      "text-indigo-700 font-medium",  // 2 - project
      "text-slate-600",               // 3 - category
      "text-slate-500 text-xs",       // 4 - subcategory
      "text-slate-400 text-xs",       // 5 - detail
    ];

    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer hover:bg-slate-100 transition-colors ${
            isSelected ? "bg-indigo-50 ring-1 ring-indigo-300" : ""
          }`}
          style={{ paddingLeft: `${depth * 16 + 4}px` }}
          onClick={() => {
            onSelect(node.id);
            if (hasChildren) onToggle(node.id);
          }}
        >
          {hasChildren ? (
            isExpanded ?
              <ChevronDownIcon className="h-3.5 w-3.5 text-slate-400 shrink-0" /> :
              <ChevronRightIcon className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          ) : (
            <span className="w-3.5 shrink-0" />
          )}
          {icon && <span className="text-xs">{icon}</span>}
          <span className={`truncate text-sm ${levelColors[Math.min(node.niveau, 5)]}`}>
            {node.libelle}
          </span>
        </div>
        {isExpanded && children.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  };

  const roots = nodeMap.get(null) || [];
  return <div className="space-y-0.5">{roots.map((r) => renderNode(r, 0))}</div>;
}


/* ── Node Detail Panel ── */

function NodeDetailPanel({ node }: { node: NodeDetail }) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{node.libelle}</h2>
            <p className="text-xs text-slate-500 font-mono">{node.code}</p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            Niveau {node.niveau}
          </span>
        </div>
      </div>

      {/* Double vue */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="card p-4">
          <h4 className="text-xs font-semibold text-blue-600 mb-3 uppercase tracking-wide">Vue Officielle</h4>
          <div className="space-y-2">
            <Row label="Encaissements (RF1)" value={node.encaissements_rf1 || node.encaissements_officiel || 0} />
            <Row label="Decaissements (RF1)" value={-(node.decaissements_rf1 || node.decaissements_officiel || 0)} />
            <div className="border-t pt-2">
              <Row label="Solde Officiel" value={node.solde_officiel || 0} bold />
            </div>
          </div>
        </div>
        <div className="card p-4">
          <h4 className="text-xs font-semibold text-violet-600 mb-3 uppercase tracking-wide">Vue Interne (verite)</h4>
          <div className="space-y-2">
            <Row label="Encaissements" value={node.encaissements} />
            <Row label="Decaissements" value={-node.decaissements} />
            <Row label="CFF" value={-node.cff_total} />
            {(node.masse_salariale ?? 0) > 0 && <Row label="Masse salariale" value={-(node.masse_salariale ?? 0)} />}
            <div className="border-t pt-2">
              <Row label="Solde Net" value={node.solde_net} bold />
            </div>
          </div>
        </div>
      </div>

      {/* Ratios */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-slate-200 p-3 text-center">
          <p className="text-xs text-slate-500">Marge Brute</p>
          <p className={`text-lg font-bold ${node.marge_brute_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
            {fmtPct(node.marge_brute_pct)}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 p-3 text-center">
          <p className="text-xs text-slate-500">Impact CFF</p>
          <p className="text-lg font-bold text-amber-600">{fmtPct(node.impact_cff_pct)}</p>
        </div>
        <div className="rounded-lg border border-slate-200 p-3 text-center">
          <p className="text-xs text-slate-500">Poids RF2</p>
          <p className="text-lg font-bold text-violet-600">{fmtPct(node.poids_rf2_pct)}</p>
        </div>
      </div>

      {/* RF Breakdown bars */}
      {(node.encaissements_rf1 > 0 || node.encaissements_rf2 > 0) && (
        <div className="card p-4">
          <h4 className="text-xs font-semibold text-slate-600 mb-3">Repartition RF Encaissements</h4>
          <div className="flex h-4 rounded-full overflow-hidden bg-slate-100">
            {node.encaissements_rf1 > 0 && (
              <div
                className="bg-blue-500 transition-all"
                style={{ width: `${(node.encaissements_rf1 / node.encaissements) * 100}%` }}
                title={`RF1: ${fmtDA(node.encaissements_rf1)}`}
              />
            )}
            {node.encaissements_rf2 > 0 && (
              <div
                className="bg-amber-400 transition-all"
                style={{ width: `${(node.encaissements_rf2 / node.encaissements) * 100}%` }}
                title={`RF2: ${fmtDA(node.encaissements_rf2)}`}
              />
            )}
          </div>
          <div className="flex justify-between mt-2 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" /> RF1: {fmtDA(node.encaissements_rf1)}</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" /> RF2: {fmtDA(node.encaissements_rf2)}</span>
          </div>
        </div>
      )}

      {/* Quote-parts table */}
      {node.quote_parts && node.quote_parts.length > 0 && (
        <div className="card p-4">
          <h4 className="text-xs font-semibold text-slate-600 mb-3">Quote-parts par Associe</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs text-slate-500">
                  <th className="pb-2 text-left">Associe</th>
                  <th className="pb-2 text-right">% Projet</th>
                  <th className="pb-2 text-right">% Entreprise</th>
                  <th className="pb-2 text-right">QP Encaiss.</th>
                  <th className="pb-2 text-right">QP Decaiss.</th>
                  <th className="pb-2 text-right">QP CFF</th>
                  <th className="pb-2 text-right font-semibold">Net apres CFF</th>
                </tr>
              </thead>
              <tbody>
                {node.quote_parts.map((qp) => (
                  <tr key={qp.associe_id} className="border-b border-slate-100">
                    <td className="py-2 font-medium text-slate-800">{qp.nom}</td>
                    <td className="py-2 text-right text-slate-600">{fmtPct(qp.pct_projet)}</td>
                    <td className="py-2 text-right text-slate-600">{fmtPct(qp.pct_entreprise)}</td>
                    <td className="py-2 text-right text-emerald-600">{fmtDA(qp.qp_encaissements)}</td>
                    <td className="py-2 text-right text-red-600">{fmtDA(qp.qp_decaissements)}</td>
                    <td className="py-2 text-right text-amber-600">{fmtDA(qp.qp_cff)}</td>
                    <td className={`py-2 text-right font-bold ${signColor(qp.qp_net_apres_cff)}`}>{fmtDA(qp.qp_net_apres_cff)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs text-amber-600">
            <ExclamationTriangleIcon className="h-3.5 w-3.5" />
            <span>CFF utilise % entreprise EMETTRICE — Charges directes utilisent % projet</span>
          </div>
        </div>
      )}

      {/* Sub-projects if enterprise node */}
      {node.projets && node.projets.length > 0 && (
        <div className="card p-4">
          <h4 className="text-xs font-semibold text-slate-600 mb-3">Projets</h4>
          <div className="space-y-2">
            {node.projets.map((p) => (
              <div key={p.code} className="flex items-center justify-between rounded-lg border border-slate-100 p-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{p.libelle}</p>
                  <p className="text-xs text-slate-400">{p.code}</p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-bold ${signColor(p.solde_net)}`}>{fmtDA(p.solde_net)}</p>
                  <p className="text-xs text-slate-500">Marge: {fmtPct(p.marge_brute_pct)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
