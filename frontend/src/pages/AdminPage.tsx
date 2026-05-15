import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  UsersIcon,
  ShieldCheckIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  ChartBarSquareIcon,
} from "@heroicons/react/24/outline";

/* ── Types ──────────────────────────────────────── */
interface TenantInfo {
  id: string;
  name: string;
  is_active: boolean;
}
interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  employee_id?: string | null;
}
interface ModuleInfo {
  code: string;
  label: string;
}
interface UserPermissionItem {
  module: string;
  can_read: boolean;
  can_write: boolean;
}
interface UserDetail extends UserInfo {
  tenant_id: string;
  employee_name?: string | null;
  permissions: UserPermissionItem[];
  created_at?: string | null;
}
interface AuditEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}
interface SystemStats {
  total_tenants: number;
  total_users: number;
  total_documents: number;
  total_workflows: number;
  committed_workflows: number;
}
interface Policies {
  VAT_RATES_ALLOWED: string;
  ROUNDING_TOLERANCE: number;
  CONFIDENCE_GATE_THRESHOLD: number;
  MAX_UPLOAD_SIZE_MB: number;
  ALLOWED_EXTENSIONS: string;
  MAX_RESOLUTION_ATTEMPTS: number;
}

type Tab = "stats" | "users" | "tenants" | "policies" | "audit";

const ROLE_OPTIONS = [
  "VIEWER",
  "EMPLOYE",
  "RH",
  "DAF",
  "ADV",
  "BIM",
  "DIRECTION",
  "COMMERCIAL",
  "MARKETING",
  "JURIDIQUE",
  "NOTAIRE",
  "SUPER_ADMIN",
];

const ROLE_ALIASES: Record<string, string> = {
  admin: "SUPER_ADMIN",
  accountant: "DAF",
  hr_manager: "RH",
  sales: "COMMERCIAL",
  employee: "EMPLOYE",
  viewer: "VIEWER",
};

function normalizeRole(role: string): string {
  return ROLE_ALIASES[role] ?? role;
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("stats");

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Administration</h1>
      <p className="text-sm text-slate-500 mb-6">Utilisateurs, politiques & audit</p>

      <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {(["stats", "users", "tenants", "policies", "audit"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === t ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {{
              stats: "Statistiques",
              users: "Utilisateurs",
              tenants: "Tenants",
              policies: "Politiques",
              audit: "Journal d'audit",
            }[t]}
          </button>
        ))}
      </div>

      {tab === "stats" && <StatsSection />}
      {tab === "users" && <UsersSection />}
      {tab === "tenants" && <TenantsSection />}
      {tab === "policies" && <PoliciesSection />}
      {tab === "audit" && <AuditSection />}
    </div>
  );
}

/* ── Stats ─────────────── */
function StatsSection() {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api
      .get("/admin/stats")
      .then(({ data }) => setStats(data ?? null))
      .catch(() => setStats(null));
  }, []);

  if (!stats) return <p className="text-slate-400">Chargement…</p>;

  const cards = [
    { label: "Tenants", value: stats.total_tenants, icon: ShieldCheckIcon, color: "text-indigo-600 bg-indigo-50" },
    { label: "Utilisateurs", value: stats.total_users, icon: UsersIcon, color: "text-teal-600 bg-teal-50" },
    { label: "Documents", value: stats.total_documents, icon: ClipboardDocumentListIcon, color: "text-amber-600 bg-amber-50" },
    { label: "Workflows", value: stats.total_workflows, icon: ChartBarSquareIcon, color: "text-green-600 bg-green-50" },
    { label: "Engagés", value: stats.committed_workflows, icon: ChartBarSquareIcon, color: "text-emerald-600 bg-emerald-50" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="card p-5">
          <div className="flex items-center gap-3">
            <div className={`rounded-lg p-2 ${c.color}`}>
              <c.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className="text-xl font-bold text-slate-900">{c.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Users ──────────────── */
function UsersSection() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null);
  const [permissionDrafts, setPermissionDrafts] = useState<Record<string, UserPermissionItem>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [savingPermissions, setSavingPermissions] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/users");
      const items = Array.isArray(data) ? data : (data?.items ?? []);
      setUsers(items.map((item: UserInfo) => ({ ...item, role: normalizeRole(item.role) })));
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  useEffect(() => {
    api.get("/admin/modules")
      .then(({ data }) => setModules(Array.isArray(data) ? data : []))
      .catch(() => setModules([]));
  }, []);

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.put(`/admin/users/${userId}/role`, { role: newRole });
      setMessage("Rôle mis à jour.");
      setError("");
      fetch();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors du changement de rôle.");
    }
  };

  const handleToggleActive = async (userId: string) => {
    try {
      await api.put(`/admin/users/${userId}/toggle-active`);
      setMessage("Statut utilisateur mis à jour.");
      setError("");
      fetch();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors du changement de statut.");
    }
  };

  const openPermissions = async (userId: string) => {
    setDetailLoading(true);
    setMessage("");
    setError("");
    try {
      const { data } = await api.get(`/admin/users/${userId}`);
      setSelectedUser({ ...data, role: normalizeRole(data.role) });
      const draftMap: Record<string, UserPermissionItem> = {};
      const existingMap = new Map<string, UserPermissionItem>((data.permissions ?? []).map((item: UserPermissionItem) => [item.module, item]));
      modules.forEach((module) => {
        draftMap[module.code] = existingMap.get(module.code) ?? { module: module.code, can_read: false, can_write: false };
      });
      setPermissionDrafts(draftMap);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Impossible de charger les permissions.");
    } finally {
      setDetailLoading(false);
    }
  };

  const savePermissions = async () => {
    if (!selectedUser) return;
    setSavingPermissions(true);
    try {
      await api.put(`/admin/users/${selectedUser.id}/permissions`, {
        permissions: Object.values(permissionDrafts),
      });
      setMessage("Permissions enregistrées.");
      setError("");
      setSelectedUser(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors de l'enregistrement des permissions.");
    } finally {
      setSavingPermissions(false);
    }
  };

  return (
    <div>
      {message && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      <h2 className="text-lg font-semibold mb-4">{users.length} utilisateurs</h2>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Nom</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Email</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Rôle</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{u.full_name}</td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className="input-field w-36 text-xs py-1"
                    >
                      {ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? <span className="badge-success">Actif</span> : <span className="badge-danger">Inactif</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openPermissions(u.id)}
                        className="btn-secondary text-xs px-3 py-1"
                      >
                        Permissions
                      </button>
                      <button
                        onClick={() => handleToggleActive(u.id)}
                        className={`text-xs px-3 py-1 rounded ${u.is_active ? "btn-danger" : "btn-primary"}`}
                      >
                        {u.is_active ? "Désactiver" : "Activer"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div className="w-full max-w-4xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Permissions utilisateur</h3>
                <p className="mt-1 text-sm text-slate-500">
                  {selectedUser.full_name} · {selectedUser.email}
                  {selectedUser.employee_name ? ` · Employé lié: ${selectedUser.employee_name}` : " · Aucun employé lié"}
                </p>
              </div>
              <button onClick={() => setSelectedUser(null)} className="text-sm text-slate-500 hover:text-slate-700">Fermer</button>
            </div>

            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Cette grille devient la matrice d'accès complète de l'utilisateur. Chaque module peut être ouvert en lecture et/ou écriture indépendamment.
            </div>

            {detailLoading ? (
              <div className="py-10 text-center text-sm text-slate-400">Chargement…</div>
            ) : (
              <div className="max-h-[28rem] overflow-auto rounded-xl border border-slate-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-slate-50">
                      <th className="px-4 py-3 text-left font-medium text-slate-600">Module</th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">Lecture</th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">Modification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {modules.map((module) => {
                      const current = permissionDrafts[module.code] ?? { module: module.code, can_read: false, can_write: false };
                      return (
                        <tr key={module.code} className="hover:bg-slate-50">
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-800">{module.label}</div>
                            <div className="text-xs text-slate-500">{module.code}</div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <input
                              type="checkbox"
                              checked={current.can_read}
                              onChange={(e) => setPermissionDrafts((prev) => ({
                                ...prev,
                                [module.code]: { ...current, can_read: e.target.checked },
                              }))}
                            />
                          </td>
                          <td className="px-4 py-3 text-center">
                            <input
                              type="checkbox"
                              checked={current.can_write}
                              onChange={(e) => setPermissionDrafts((prev) => ({
                                ...prev,
                                [module.code]: {
                                  ...current,
                                  can_read: e.target.checked ? true : current.can_read,
                                  can_write: e.target.checked,
                                },
                              }))}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setSelectedUser(null)} className="btn-secondary">Annuler</button>
              <button onClick={savePermissions} disabled={savingPermissions || detailLoading} className="btn-primary">
                {savingPermissions ? "Enregistrement…" : "Enregistrer les permissions"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Tenants ───────────── */
function TenantsSection() {
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get("/admin/tenants")
      .then(({ data }) => setTenants(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setTenants([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">{tenants.length} tenants</h2>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">ID</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Nom</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : (
              tenants.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{t.id}</td>
                  <td className="px-4 py-3 font-medium">{t.name}</td>
                  <td className="px-4 py-3">
                    {t.is_active ? <span className="badge-success">Actif</span> : <span className="badge-danger">Inactif</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Policies ──────────── */
function PoliciesSection() {
  const [policies, setPolicies] = useState<Policies | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Policies | null>(null);

  useEffect(() => {
    api
      .get("/admin/policies")
      .then(({ data }) => {
        setPolicies(data);
        setForm(data);
      })
      .catch(() => {
        setPolicies(null);
        setForm(null);
      });
  }, []);

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    try {
      const { data } = await api.put("/admin/policies", form);
      setPolicies(data);
      setForm(data);
    } finally {
      setSaving(false);
    }
  };

  if (!form) return <p className="text-slate-400">Chargement…</p>;

  return (
    <div className="max-w-2xl">
      <div className="card p-6 space-y-5">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Cog6ToothIcon className="h-5 w-5 text-slate-400" />
          Politiques système
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Taux TVA autorisés</label>
            <input value={form.VAT_RATES_ALLOWED} onChange={(e) => setForm({ ...form, VAT_RATES_ALLOWED: e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tolérance arrondi</label>
            <input type="number" step="0.001" value={form.ROUNDING_TOLERANCE} onChange={(e) => setForm({ ...form, ROUNDING_TOLERANCE: +e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Seuil confiance (%)</label>
            <input type="number" step="0.01" value={form.CONFIDENCE_GATE_THRESHOLD} onChange={(e) => setForm({ ...form, CONFIDENCE_GATE_THRESHOLD: +e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Taille max upload (MB)</label>
            <input type="number" value={form.MAX_UPLOAD_SIZE_MB} onChange={(e) => setForm({ ...form, MAX_UPLOAD_SIZE_MB: +e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Extensions autorisées</label>
            <input value={form.ALLOWED_EXTENSIONS} onChange={(e) => setForm({ ...form, ALLOWED_EXTENSIONS: e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tentatives résolution max</label>
            <input type="number" value={form.MAX_RESOLUTION_ATTEMPTS} onChange={(e) => setForm({ ...form, MAX_RESOLUTION_ATTEMPTS: +e.target.value })} className="input-field" />
          </div>
        </div>

        <div className="flex justify-end">
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Audit Log ─────────── */
function AuditSection() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get("/admin/audit-log")
      .then(({ data }) => setLogs(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Journal d'audit</h2>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Action</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Entité</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">ID Entité</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Utilisateur</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Aucune entrée</td></tr>
            ) : (
              logs.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-xs">{new Date(l.created_at).toLocaleString("fr-FR")}</td>
                  <td className="px-4 py-3">
                    <span className="badge-info">{l.action}</span>
                  </td>
                  <td className="px-4 py-3 font-medium">{l.entity_type}</td>
                  <td className="px-4 py-3 font-mono text-xs">{l.entity_id ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{l.user_id ?? "system"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
