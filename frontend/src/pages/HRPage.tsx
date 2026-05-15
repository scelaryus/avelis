import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";
import {
  ArrowUpTrayIcon,
  PlusIcon,
  UserGroupIcon,
  CurrencyDollarIcon,
  ClipboardDocumentListIcon,
} from "@heroicons/react/24/outline";

interface Employee {
  id: string;
  employee_number: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone?: string | null;
  professional_address?: string | null;
  activities?: string | null;
  user_id?: string | null;
  is_active: boolean;
  department?: string | null;
  position?: string | null;
  manager_name?: string | null;
  mentor_name?: string | null;
  company?: string | null;
  base_salary: number;
  status: string;
  hire_date: string | null;
  upcoming_activity_due_date?: string | null;
  social_security_number?: string | null;
}

interface PayrollProposal {
  id: string;
  period_label: string;
  status: string;
  total_gross: number;
  total_net: number;
  total_employer_charges: number;
  generated_at: string;
}

interface TaskItem {
  id: string;
  employee_id: string | null;
  employee_name: string | null;
  entreprise_id: string | null;
  task_type: string;
  title: string;
  description: string;
  required_role: string | null;
  plan_date: string;
  due_date: string | null;
  status: string;
  approval_status: string;
  employee_estimated_time: number | null;
  employee_estimated_price: number | null;
  manager_final_time: number | null;
  manager_final_price: number | null;
  proof_document_id: string | null;
  ai_score: number | null;
  ai_note: string | null;
  manager_validated: boolean;
  manager_rating: number | null;
  manager_feedback: string | null;
  salary_adjustment_amount: number;
}

interface TaskNotification {
  id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string | null;
  task?: TaskItem | null;
}

type Tab = "employees" | "tasks" | "payroll";

const ACCOUNT_ROLE_OPTIONS = [
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
  "VIEWER",
  "SUPER_ADMIN",
];

const EMP_STATUS: Record<string, { cls: string; label: string }> = {
  ACTIVE: { cls: "badge-success", label: "Actif" },
  INACTIVE: { cls: "badge-neutral", label: "Inactif" },
  ON_LEAVE: { cls: "badge-warning", label: "En congé" },
  TERMINATED: { cls: "badge-danger", label: "Résilié" },
  SUSPENDED: { cls: "badge-neutral", label: "Suspendu" },
};

export default function HRPage() {
  const [tab, setTab] = useState<Tab>("employees");
  const { user } = useAuth();

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">RH & Paie</h1>
      <p className="text-sm text-slate-500 mb-6">Gestion des employés, tâches quotidiennes & bulletins de paie</p>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {(["employees", "tasks", "payroll"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t === "employees" ? "Employés" : t === "tasks" ? "Tâches" : "Paie"}
          </button>
        ))}
      </div>

      {tab === "employees" && <EmployeesSection />}
      {tab === "tasks" && <TasksSection isManager={Boolean(user && ["admin", "hr_manager", "RH", "SUPER_ADMIN"].includes(user.role))} />}
      {tab === "payroll" && <PayrollSection />}
    </div>
  );
}

function EmployeesSection() {
  const { user } = useAuth();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountMessage, setAccountMessage] = useState("");
  const [accountError, setAccountError] = useState("");
  const [importLoading, setImportLoading] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [importError, setImportError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [accountForm, setAccountForm] = useState({
    email: "",
    password: "",
    role: "EMPLOYE",
  });
  const [form, setForm] = useState({
    employee_number: "",
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    professional_address: "Avelis Promotion immobilière",
    activities: "",
    department: "",
    position: "",
    manager_name: "",
    mentor_name: "",
    company: "Avelis Promotion immobilière",
    hire_date: "",
    upcoming_activity_due_date: "",
    base_salary: "",
    social_security_number: "",
    status: "ACTIVE",
    is_active: true,
  });

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hr/employees");
      setEmployees(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setEmployees([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const canManageAccounts = Boolean(user && ["admin", "hr_manager", "RH", "SUPER_ADMIN"].includes(user.role));

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append("file", selectedFile);
    setImportLoading(true);
    setImportMessage("");
    setImportError("");
    try {
      const { data } = await api.post("/hr/employees/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const summary = data?.summary;
      setImportMessage(`Import terminé: ${summary?.created ?? 0} créé(s), ${summary?.updated ?? 0} mis à jour, ${summary?.normalized_names ?? 0} nom(s) normalisé(s).`);
      await fetch();
    } catch (err: any) {
      setImportError(err?.response?.data?.detail ?? "Erreur lors de l'import des employés.");
    } finally {
      event.target.value = "";
      setImportLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/hr/employees", {
      ...form,
      base_salary: form.base_salary ? Number(form.base_salary) : null,
      hire_date: form.hire_date || null,
      upcoming_activity_due_date: form.upcoming_activity_due_date || null,
    });
    setShowForm(false);
    setForm({
      employee_number: "",
      first_name: "",
      last_name: "",
      email: "",
      phone: "",
      professional_address: "Avelis Promotion immobilière",
      activities: "",
      department: "",
      position: "",
      manager_name: "",
      mentor_name: "",
      company: "Avelis Promotion immobilière",
      hire_date: "",
      upcoming_activity_due_date: "",
      base_salary: "",
      social_security_number: "",
      status: "ACTIVE",
      is_active: true,
    });
    fetch();
  };

  const openAccountModal = (employee: Employee) => {
    setSelectedEmployee(employee);
    setAccountMessage("");
    setAccountError("");
    setAccountForm({
      email: employee.email ?? "",
      password: "",
      role: "EMPLOYE",
    });
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmployee) return;
    setAccountLoading(true);
    setAccountMessage("");
    setAccountError("");
    try {
      await api.post("/hr/employees/create-account", {
        employee_id: selectedEmployee.id,
        email: accountForm.email || null,
        password: accountForm.password,
        role: accountForm.role,
      });
      setAccountMessage("Compte créé et lié à l'employé.");
      setSelectedEmployee(null);
      await fetch();
    } catch (err: any) {
      setAccountError(err?.response?.data?.detail ?? "Erreur lors de la création du compte.");
    } finally {
      setAccountLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <UserGroupIcon className="h-5 w-5 text-slate-400" />
          <span className="text-lg font-semibold">{employees.length} employés</span>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {accountMessage && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{accountMessage}</div>}
      {accountError && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{accountError}</div>}
      {importMessage && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{importMessage}</div>}
      {importError && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{importError}</div>}

      <div className="card p-4 mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-800">Import employés</p>
          <p className="text-xs text-slate-500">Formats acceptés: CSV, XLSX, XLS. Les noms existants seront normalisés pendant l'import.</p>
        </div>
        <div className="flex items-center gap-3">
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleImport} />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={importLoading} className="btn-secondary text-xs">
            <ArrowUpTrayIcon className="h-4 w-4" /> {importLoading ? "Import…" : "Importer CSV / Excel"}
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 space-y-4">
          <h3 className="text-sm font-semibold text-slate-800 border-b pb-2">Identité</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Matricule *</label>
              <input value={form.employee_number} onChange={(e) => setForm({ ...form, employee_number: e.target.value })} className="input-field" required placeholder="EMP-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Prénom *</label>
              <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="input-field" required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Nom *</label>
              <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="input-field" required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">N° sécurité sociale</label>
              <input value={form.social_security_number} onChange={(e) => setForm({ ...form, social_security_number: e.target.value })} className="input-field" placeholder="N° CNAS" /></div>
          </div>

          <h3 className="text-sm font-semibold text-slate-800 border-b pb-2">Contact</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Email professionnel</label>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input-field" placeholder="nom@entreprise.com" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Téléphone</label>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input-field" placeholder="0550000000" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Adresse professionnelle</label>
              <input value={form.professional_address} onChange={(e) => setForm({ ...form, professional_address: e.target.value })} className="input-field" /></div>
          </div>

          <h3 className="text-sm font-semibold text-slate-800 border-b pb-2">Poste & Organisation</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Société</label>
              <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="input-field" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Département</label>
              <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="input-field" placeholder="Finance, RH, ADV..." /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Poste</label>
              <input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} className="input-field" placeholder="Comptable, Commercial..." /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Statut RH</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input-field">
                <option value="ACTIVE">Actif</option><option value="INACTIVE">Inactif</option>
                <option value="ON_LEAVE">En congé</option><option value="TERMINATED">Résilié</option>
              </select></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Manager</label>
              <input value={form.manager_name} onChange={(e) => setForm({ ...form, manager_name: e.target.value })} className="input-field" placeholder="Nom complet du manager" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Mentor</label>
              <input value={form.mentor_name} onChange={(e) => setForm({ ...form, mentor_name: e.target.value })} className="input-field" placeholder="Nom complet du mentor" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date d'embauche</label>
              <input type="date" value={form.hire_date} onChange={(e) => setForm({ ...form, hire_date: e.target.value })} className="input-field" /></div>
          </div>

          <h3 className="text-sm font-semibold text-slate-800 border-b pb-2">Rémunération</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Salaire de base (DA)</label>
              <input type="number" value={form.base_salary} onChange={(e) => setForm({ ...form, base_salary: e.target.value })} className="input-field" min={0} placeholder="0" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date limite activité à venir</label>
              <input type="date" value={form.upcoming_activity_due_date} onChange={(e) => setForm({ ...form, upcoming_activity_due_date: e.target.value })} className="input-field" /></div>
          </div>

          <div>
            <label className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-500">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Employé actif
            </label>
            <textarea value={form.activities} onChange={(e) => setForm({ ...form, activities: e.target.value })} className="input-field w-full" rows={2} placeholder="Activités, notes RH..." />
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" className="btn-primary text-sm">Créer l'employé</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Matricule</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Nom complet</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Société / poste</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Contact</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Manager / mentor</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Compte app</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Salaire base</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Dates</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : employees.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Aucun employé</td></tr>
            ) : (
              employees.map((emp) => {
                const s = EMP_STATUS[emp.status] ?? EMP_STATUS.ACTIVE;
                return (
                  <tr key={emp.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono">{emp.employee_number}</td>
                    <td className="px-4 py-3 font-medium">{emp.first_name} {emp.last_name}</td>
                    <td className="px-4 py-3 text-slate-600">
                      <div>{emp.company ?? "—"}</div>
                      <div className="text-xs text-slate-400">{emp.position ?? emp.department ?? "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div>{emp.email ?? "—"}</div>
                      <div className="text-xs text-slate-400">{emp.phone ?? emp.professional_address ?? "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div>{emp.manager_name ?? "—"}</div>
                      <div className="text-xs text-slate-400">Mentor: {emp.mentor_name ?? "—"}</div>
                    </td>
                    <td className="px-4 py-3">
                      {emp.user_id ? (
                        <span className="badge-success">Compte actif</span>
                      ) : canManageAccounts ? (
                        <button onClick={() => openAccountModal(emp)} className="px-2 py-1 rounded text-xs font-medium bg-teal-600 text-white hover:bg-teal-700">
                          Créer un compte
                        </button>
                      ) : (
                        <span className="text-xs text-red-400">Pas de compte</span>
                      )}
                    </td>
                    <td className="px-4 py-3">{emp.base_salary ? Number(emp.base_salary).toLocaleString("fr-FR") : "—"} DA</td>
                    <td className="px-4 py-3">
                      <div><span className={s.cls}>{s.label}</span></div>
                      <div className="mt-1 text-xs text-slate-400">{emp.is_active ? "Actif" : "Inactif"}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div>Embauche: {emp.hire_date ? new Date(emp.hire_date).toLocaleDateString("fr-FR") : "—"}</div>
                      <div className="text-xs text-slate-400">Échéance activité: {emp.upcoming_activity_due_date ? new Date(emp.upcoming_activity_due_date).toLocaleDateString("fr-FR") : "—"}</div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {selectedEmployee && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-slate-900">Créer un compte lié</h3>
              <p className="mt-1 text-sm text-slate-500">
                {selectedEmployee.first_name} {selectedEmployee.last_name} recevra les notifications des tâches via ce compte.
              </p>
            </div>

            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">Email de connexion</label>
                <input
                  value={accountForm.email}
                  onChange={(e) => setAccountForm({ ...accountForm, email: e.target.value })}
                  className="input-field"
                  placeholder="email@entreprise.com"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">Mot de passe initial</label>
                <input
                  type="password"
                  value={accountForm.password}
                  onChange={(e) => setAccountForm({ ...accountForm, password: e.target.value })}
                  className="input-field"
                  minLength={6}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">Rôle applicatif</label>
                <select
                  value={accountForm.role}
                  onChange={(e) => setAccountForm({ ...accountForm, role: e.target.value })}
                  className="input-field"
                >
                  {ACCOUNT_ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Les accès fins par module se règlent ensuite dans Administration → Utilisateurs → Permissions.
              </div>
              <div className="flex justify-end gap-3">
                <button type="button" onClick={() => setSelectedEmployee(null)} className="btn-secondary">
                  Annuler
                </button>
                <button type="submit" disabled={accountLoading} className="btn-primary">
                  {accountLoading ? "Création…" : "Créer le compte"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function TasksSection({ isManager }: { isManager: boolean }) {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [notifications, setNotifications] = useState<TaskNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [planDate, setPlanDate] = useState(new Date(Date.now() + 86400000).toISOString().slice(0, 10));
  const [rawText, setRawText] = useState("");
  const [ratingDrafts, setRatingDrafts] = useState<Record<string, { rating: number; feedback: string }>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [approveForm, setApproveForm] = useState<{ taskId: string; time: string; price: string; feedback: string } | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data: employeesData }, { data: tasksData }, { data: notifData }] = await Promise.all([
        api.get("/hr/employees"),
        api.get("/hr/tasks"),
        api.get("/hr/tasks/notifications"),
      ]);
      setEmployees(Array.isArray(employeesData) ? employeesData : []);
      setTasks(Array.isArray(tasksData) ? tasksData : []);
      setNotifications(Array.isArray(notifData) ? notifData : []);
    } catch {
      setEmployees([]);
      setTasks([]);
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handlePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setPlanning(true);
    setMessage("");
    setError("");
    try {
      const { data } = await api.post("/hr/tasks/plan", { plan_date: planDate, raw_text: rawText });
      setMessage(`${data.created} tâche(s) générée(s) et notifiées.`);
      setRawText("");
      await fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors de la génération des tâches.");
    } finally {
      setPlanning(false);
    }
  };

  const handleComplete = async (taskId: string) => {
    await api.post(`/hr/tasks/${taskId}/complete`, { status: "completed" });
    await fetchAll();
  };

  const handleRate = async (taskId: string) => {
    const draft = ratingDrafts[taskId] ?? { rating: 3, feedback: "" };
    try {
      await api.post(`/hr/tasks/${taskId}/rate`, draft);
      setMessage("Évaluation enregistrée et salaire ajusté.");
      setError("");
      await fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors de l'évaluation.");
    }
  };

  const handleReadNotification = async (notificationId: string) => {
    await api.post(`/hr/tasks/notifications/${notificationId}/read`);
    await fetchAll();
  };

  /* ── New workflow actions ── */
  const handleApproveEstimate = async (taskId: string, approved: boolean) => {
    if (!approveForm && approved) return;
    setActionLoading(taskId);
    try {
      await api.post(`/hr/tasks/${taskId}/approve`, {
        approved,
        final_time: approved && approveForm ? parseFloat(approveForm.time) || undefined : undefined,
        final_price: approved && approveForm ? parseFloat(approveForm.price) || undefined : undefined,
        feedback: approved && approveForm?.feedback ? approveForm.feedback : approved ? undefined : "Estimation rejetée par le manager",
      });
      setApproveForm(null);
      setMessage(approved ? "Estimation approuvée." : "Estimation rejetée.");
      await fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur");
    } finally {
      setActionLoading(null);
    }
  };

  const handleTriggerAI = async (taskId: string) => {
    setActionLoading(taskId);
    try {
      const { data } = await api.post(`/hr/tasks/${taskId}/ai-evaluate`);
      setMessage(`Score AI: ${data.ai_score}/100 — ${data.ai_note}`);
      await fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur évaluation AI");
    } finally {
      setActionLoading(null);
    }
  };

  const handleValidateAI = async (taskId: string, validated: boolean) => {
    setActionLoading(taskId);
    try {
      await api.post(`/hr/tasks/${taskId}/validate`, { validated });
      setMessage(validated ? "Score AI validé et bonus appliqué." : "Score AI rejeté.");
      await fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur validation");
    } finally {
      setActionLoading(null);
    }
  };

  const approvalBadge = (status: string) => {
    const colors: Record<string, string> = {
      PENDING_ESTIMATE: "badge-warning",
      ESTIMATED: "badge-info",
      APPROVED: "badge-success",
      IN_PROGRESS: "badge-info",
      PROOF_SUBMITTED: "badge-neutral",
      AI_EVALUATED: "badge-info",
      VALIDATED: "badge-success",
      REJECTED: "badge-danger",
    };
    return <span className={colors[status] || "badge-neutral"}>{status.replace(/_/g, " ")}</span>;
  };

  const isCompletedState = (task: TaskItem) => task.status === "completed" || task.status === "closed";
  const isClosedState = (task: TaskItem) => task.status === "closed";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ClipboardDocumentListIcon className="h-5 w-5 text-slate-400" />
        <span className="text-lg font-semibold">Tâches quotidiennes & notifications</span>
      </div>

      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {isManager && (
        <form onSubmit={handlePlan} className="card p-4 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Planification IA de la semaine</h3>
              <p className="text-sm text-slate-500">Décrivez les tâches à faire pour un jour donné. Le moteur les répartit selon les rôles et employés.</p>
            </div>
            <div className="w-52">
              <label className="block text-xs font-medium text-slate-500 mb-1">Jour ciblé</label>
              <input type="date" className="input-field w-full" value={planDate} onChange={(e) => setPlanDate(e.target.value)} required />
            </div>
          </div>
          <textarea
            className="input-field min-h-32 w-full"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="Ex: Vérifier les encaissements du projet Irène. Préparer la paie du personnel. Relancer les clients en retard. Mettre à jour le stock chantier."
            required
          />
          <button type="submit" disabled={planning} className="btn-primary">
            {planning ? "Génération…" : "Générer les tâches du jour"}
          </button>
        </form>
      )}

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="card p-4 xl:col-span-1">
          <h3 className="text-base font-semibold text-slate-900 mb-3">Notifications</h3>
          <div className="space-y-3 max-h-[32rem] overflow-auto pr-1">
            {loading ? (
              <div className="text-sm text-slate-400">Chargement…</div>
            ) : notifications.length === 0 ? (
              <div className="text-sm text-slate-400">Aucune notification</div>
            ) : notifications.map((notification) => (
              <div key={notification.id} className={`rounded-lg border p-3 ${notification.is_read ? "border-slate-200 bg-white" : "border-blue-200 bg-blue-50"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{notification.title}</p>
                    <p className="text-xs text-slate-500 mt-1">{notification.message}</p>
                  </div>
                  {!notification.is_read && (
                    <button onClick={() => handleReadNotification(notification.id)} className="text-xs text-teal-600 hover:text-teal-700">Lu</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card overflow-hidden xl:col-span-2">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <h3 className="text-base font-semibold text-slate-900">Menu des tâches quotidiennes</h3>
            <span className="text-xs text-slate-500">{employees.length} employé(s) actifs</span>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50">
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Jour</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Tâche</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Affectation</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Workflow</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Évaluation</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
                ) : tasks.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune tâche planifiée</td></tr>
                ) : (
                  tasks.map((task) => (
                    <tr key={task.id} className="align-top hover:bg-slate-50">
                      <td className="px-4 py-3 whitespace-nowrap">{task.plan_date}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-800">{task.title}</p>
                        <p className="text-xs text-slate-500 mt-1">{task.description}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-700">{task.employee_name ?? "Non affecté"}</p>
                        <p className="text-xs text-slate-500 mt-1">Rôle: {task.required_role ?? "—"}</p>
                      </td>
                      {/* Workflow status column */}
                      <td className="px-4 py-3 space-y-1 min-w-48">
                        {approvalBadge(task.approval_status || "PENDING_ESTIMATE")}
                        {task.employee_estimated_time && (
                          <p className="text-xs text-slate-500 mt-1">
                            Estimé: {task.employee_estimated_time}h / {task.employee_estimated_price} DA
                          </p>
                        )}
                        {task.manager_final_time && (
                          <p className="text-xs text-blue-600 mt-1">
                            Validé: {task.manager_final_time}h / {task.manager_final_price} DA
                          </p>
                        )}
                        {task.proof_document_id && (
                          <p className="text-xs text-green-600 mt-1">✓ Preuve envoyée</p>
                        )}
                        {task.ai_score !== null && (
                          <p className="text-xs text-purple-600 mt-1">
                            AI: {task.ai_score}/100
                            {task.manager_validated && " ✓ validé"}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 min-w-56">
                        {isCompletedState(task) ? (
                          isManager ? (
                            isClosedState(task) ? (
                              <div className="space-y-2">
                                <p className="text-xs font-medium text-emerald-600">Tâche clôturée</p>
                                {task.manager_rating && (
                                  <p className="text-xs text-slate-600">Note finale: {task.manager_rating}/5</p>
                                )}
                                {task.manager_feedback && (
                                  <p className="text-xs text-slate-500">Feedback: {task.manager_feedback}</p>
                                )}
                                {task.manager_rating && (
                                  <p className="text-xs text-slate-500">Ajustement salaire: {Number(task.salary_adjustment_amount).toLocaleString("fr-FR")} DA</p>
                                )}
                              </div>
                            ) : (
                              <div className="space-y-2">
                                <select
                                  className="input-field w-full"
                                  value={ratingDrafts[task.id]?.rating ?? task.manager_rating ?? 3}
                                  onChange={(e) => setRatingDrafts((prev) => ({ ...prev, [task.id]: { rating: Number(e.target.value), feedback: prev[task.id]?.feedback ?? task.manager_feedback ?? "" } }))}
                                >
                                  {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
                                </select>
                                <textarea
                                  className="input-field w-full min-h-20"
                                  placeholder="Feedback manager"
                                  value={ratingDrafts[task.id]?.feedback ?? task.manager_feedback ?? ""}
                                  onChange={(e) => setRatingDrafts((prev) => ({ ...prev, [task.id]: { rating: prev[task.id]?.rating ?? task.manager_rating ?? 3, feedback: e.target.value } }))}
                                />
                                {task.manager_rating && (
                                  <p className="text-xs text-slate-500">Ajustement salaire: {Number(task.salary_adjustment_amount).toLocaleString("fr-FR")} DA</p>
                                )}
                              </div>
                            )
                          ) : (
                            <span className="text-xs text-slate-500">En attente d'évaluation manager</span>
                          )
                        ) : (
                          <span className="text-xs text-slate-500">La tâche doit être terminée avant notation.</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <div className="flex flex-col items-end gap-2">
                          {!isCompletedState(task) && (
                            <button onClick={() => handleComplete(task.id)} className="btn-secondary text-xs px-2 py-1">Marquer fait</button>
                          )}
                          {isManager && task.status === "completed" && (
                            <button onClick={() => handleRate(task.id)} className="btn-primary text-xs px-2 py-1">Noter</button>
                          )}
                          {isManager && isClosedState(task) && (
                            <span className="badge-success">Clôturée</span>
                          )}

                          {/* Manager: approve/reject employee estimate */}
                          {isManager && task.approval_status === "ESTIMATED" && (
                            approveForm?.taskId === task.id ? (
                              <div className="space-y-1 text-left w-40">
                                <input type="number" step="0.5" placeholder="Temps (h)" className="input-field w-full text-xs"
                                  value={approveForm.time} onChange={(e) => setApproveForm({ ...approveForm, time: e.target.value })} />
                                <input type="number" step="100" placeholder="Valeur (DA)" className="input-field w-full text-xs"
                                  value={approveForm.price} onChange={(e) => setApproveForm({ ...approveForm, price: e.target.value })} />
                                <input placeholder="Feedback" className="input-field w-full text-xs"
                                  value={approveForm.feedback} onChange={(e) => setApproveForm({ ...approveForm, feedback: e.target.value })} />
                                <div className="flex gap-1">
                                  <button onClick={() => handleApproveEstimate(task.id, true)} disabled={actionLoading === task.id}
                                    className="btn-primary text-xs px-2 py-1 flex-1">✓</button>
                                  <button onClick={() => handleApproveEstimate(task.id, false)} disabled={actionLoading === task.id}
                                    className="btn-secondary text-xs px-2 py-1 flex-1 !text-red-600">✗</button>
                                  <button onClick={() => setApproveForm(null)} className="text-xs text-slate-400 px-1">×</button>
                                </div>
                              </div>
                            ) : (
                              <button onClick={() => setApproveForm({ taskId: task.id, time: String(task.employee_estimated_time ?? ""), price: String(task.employee_estimated_price ?? ""), feedback: "" })}
                                className="btn-primary text-xs px-2 py-1">Valider estimation</button>
                            )
                          )}

                          {/* Manager: trigger AI evaluation */}
                          {isManager && task.approval_status === "PROOF_SUBMITTED" && (
                            <button onClick={() => handleTriggerAI(task.id)} disabled={actionLoading === task.id}
                              className="btn-primary text-xs px-2 py-1 bg-purple-600 hover:bg-purple-700">
                              {actionLoading === task.id ? "AI…" : "Évaluer AI"}
                            </button>
                          )}

                          {/* Manager: validate AI score */}
                          {isManager && task.approval_status === "AI_EVALUATED" && !task.manager_validated && (
                            <div className="flex gap-1">
                              <button onClick={() => handleValidateAI(task.id, true)} disabled={actionLoading === task.id}
                                className="btn-primary text-xs px-2 py-1">Valider AI</button>
                              <button onClick={() => handleValidateAI(task.id, false)} disabled={actionLoading === task.id}
                                className="btn-secondary text-xs px-2 py-1 !text-red-600">Rejeter</button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function PayrollSection() {
  const [payrolls, setPayrolls] = useState<PayrollProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [periodLabel, setPeriodLabel] = useState("");

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hr/payroll");
      setPayrolls(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setPayrolls([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      await api.post("/hr/payroll/generate", { period_label: periodLabel });
      setPeriodLabel("");
      fetch();
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleGenerate} className="card p-4 mb-4 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-500 mb-1">Période</label>
          <input value={periodLabel} onChange={(e) => setPeriodLabel(e.target.value)} className="input-field" required placeholder="Janvier 2025" />
        </div>
        <button type="submit" disabled={generating} className="btn-primary">
          <CurrencyDollarIcon className="h-4 w-4" />
          {generating ? "Génération…" : "Générer la paie"}
        </button>
      </form>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Période</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Brut total</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Net total</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Charges patron</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Généré le</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : payrolls.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune paie générée</td></tr>
            ) : (
              payrolls.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{p.period_label}</td>
                  <td className="px-4 py-3"><span className="badge-info">{p.status}</span></td>
                  <td className="px-4 py-3 text-right">{Number(p.total_gross).toLocaleString("fr-FR")} DA</td>
                  <td className="px-4 py-3 text-right font-semibold">{Number(p.total_net).toLocaleString("fr-FR")} DA</td>
                  <td className="px-4 py-3 text-right">{Number(p.total_employer_charges).toLocaleString("fr-FR")} DA</td>
                  <td className="px-4 py-3 text-slate-600">{new Date(p.generated_at).toLocaleDateString("fr-FR")}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
