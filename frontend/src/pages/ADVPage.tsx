import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";
import {
  PlusIcon,
  BanknotesIcon,
  ChartBarIcon,
  CubeIcon,
  ArrowPathIcon,
  ArrowUpTrayIcon,
  TableCellsIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";

/* ── Types ─────────────────────────────────────────── */
interface Client {
  id: string;
  code: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  ice: string | null;
  address: string | null;
  city: string | null;
  phone: string | null;
  email: string | null;
  entreprise_id: string | null;
  projet_id: string | null;
}
interface Contract {
  id: string;
  client_id: string;
  contract_number: string;
  total_amount: number;
  status: string;
  start_date: string | null;
  end_date: string | null;
  entreprise_id: string | null;
  projet_id: string | null;
  notes?: string | null;
}
interface Receivable {
  id: string;
  client_id: string;
  invoice_ref: string;
  amount: number;
  amount_paid: number;
  due_date: string;
  status: string;
  last_payment_date: string | null;
}
interface Payment {
  id: string;
  client_id: string;
  amount: number;
  payment_ref: string;
  payment_method: string | null;
  bank_ref: string | null;
  payment_date: string;
  entreprise_id: string | null;
  projet_id: string | null;
}
interface DashboardStats {
  clients_count: number;
  active_contracts: number;
  total_receivable: number;
  overdue_amount: number;
  total_paid: number;
}

interface EDDProject {
  id: string;
  code: string;
  name: string;
  status: string;
}

interface EDDValidation {
  id?: string;
  stage: string;
  status: string;
  ts: string;
}

interface EDDProjectDetails {
  project: {
    code: string;
    name: string;
    status: string;
  };
  validations: EDDValidation[];
}

interface EDDUnit {
  id: string;
  code: string;
  typology: string | null;
  area_sh: number;
  area_su: number;
  exposure: string | null;
  view_class: string | null;
  price_base: number;
  price_total: number;
  edd_state: string;
}

interface EddImportResult {
  status: string;
  filename: string;
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  warnings: { row: number; unit_code?: string; message: string }[];
  ai_mapping: Record<string, string | null>;
  ai_notes: string | null;
  detected_headers: string[];
  mapped_fields: string[];
}

type Tab = "dashboard" | "clients" | "contracts" | "receivables" | "payments" | "edd";

const ADV_TAB_ORDER: Tab[] = ["dashboard", "edd", "clients", "contracts", "receivables", "payments"];
const ADV_TAB_LABELS: Record<Tab, string> = {
  dashboard: "Tableau de bord",
  edd: "Stock EDD",
  clients: "Clients",
  contracts: "Contrats",
  receivables: "Créances",
  payments: "Paiements",
};

const CONTRACT_STATUS: Record<string, { cls: string; label: string }> = {
  DRAFT: { cls: "badge-neutral", label: "Brouillon" },
  ACTIVE: { cls: "badge-success", label: "Actif" },
  COMPLETED: { cls: "badge-info", label: "Terminé" },
  CANCELLED: { cls: "badge-danger", label: "Annulé" },
};

export default function ADVPage() {
  const [tab, setTab] = useState<Tab>("dashboard");

  const filterParams = {};
  const selectedEntreprise = "";
  const selectedProjet = "";

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Administration des Ventes</h1>
      <p className="text-sm text-slate-500 mb-4">Flux conseillé : stock EDD, client, contrat, créance, puis encaissement</p>

      <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {ADV_TAB_ORDER.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === t ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {ADV_TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardSection filters={filterParams} />}
      {tab === "clients" && <ClientsSection filters={filterParams} selectedEntreprise={selectedEntreprise} selectedProjet={selectedProjet} />}
      {tab === "contracts" && <ContractsSection filters={filterParams} selectedEntreprise={selectedEntreprise} selectedProjet={selectedProjet} />}
      {tab === "receivables" && <ReceivablesSection filters={filterParams} />}
      {tab === "payments" && <PaymentsSection filters={filterParams} selectedEntreprise={selectedEntreprise} selectedProjet={selectedProjet} />}
      {tab === "edd" && <EDDSection />}
    </div>
  );
}

function EDDSection() {
  const [projects, setProjects] = useState<EDDProject[]>([]);
  const [selectedProjectCode, setSelectedProjectCode] = useState("");
  const [details, setDetails] = useState<EDDProjectDetails | null>(null);
  const [units, setUnits] = useState<EDDUnit[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [createProjectForm, setCreateProjectForm] = useState({
    code: "",
    name: "",
    lat: "",
    lon: "",
    north_angle: "",
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState("");
  const [showCreateUnit, setShowCreateUnit] = useState(false);
  const [createUnitLoading, setCreateUnitLoading] = useState(false);
  const [createUnitError, setCreateUnitError] = useState("");
  const [createUnitForm, setCreateUnitForm] = useState({
    block_code: "",
    level_code: "",
    code: "",
    typology: "",
    area_sh: "",
    area_su: "",
    price_total: "",
  });

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/bim/projects");
      const items = Array.isArray(data) ? data : [];
      setProjects(items);
      if (!selectedProjectCode && items.length > 0) {
        setSelectedProjectCode(items[0].code);
      }
    } catch (err: any) {
      setProjects([]);
      setError(err?.response?.data?.detail ?? "Erreur lors du chargement des projets EDD.");
    } finally {
      setLoading(false);
    }
  }, [selectedProjectCode]);

  const loadProjectData = useCallback(async (projectCode: string) => {
    if (!projectCode) {
      setDetails(null);
      setUnits([]);
      return;
    }
    setLoading(true);
    try {
      const [{ data: detailsData }, { data: unitsData }] = await Promise.all([
        api.get(`/bim/edd/${projectCode}`),
        api.get(`/bim/edd/${projectCode}/units`, { params: { per_page: 200 } }),
      ]);
      setDetails(detailsData ?? null);
      setUnits(Array.isArray(unitsData?.units) ? unitsData.units : []);
      setError("");
    } catch (err: any) {
      setDetails(null);
      setUnits([]);
      setError(err?.response?.data?.detail ?? "Erreur lors du chargement des données EDD.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProjectCode) {
      loadProjectData(selectedProjectCode);
    }
  }, [selectedProjectCode, loadProjectData]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError("");
    setMessage("");
    try {
      const payload = {
        code: createProjectForm.code.trim(),
        name: createProjectForm.name.trim(),
        lat: createProjectForm.lat ? Number(createProjectForm.lat) : undefined,
        lon: createProjectForm.lon ? Number(createProjectForm.lon) : undefined,
        north_angle: createProjectForm.north_angle
          ? Number(createProjectForm.north_angle)
          : undefined,
      };
      const { data } = await api.post("/bim/projects", payload);
      const newCode = data?.code || payload.code;
      setShowCreateProject(false);
      setCreateProjectForm({ code: "", name: "", lat: "", lon: "", north_angle: "" });
      await loadProjects();
      setSelectedProjectCode(newCode);
      await loadProjectData(newCode);
      setMessage("Projet EDD créé avec succès.");
    } catch (err: any) {
      setCreateError(
        err?.response?.data?.detail ?? "Erreur lors de la création du projet EDD."
      );
    } finally {
      setCreateLoading(false);
    }
  };

  const runAction = async (action: "generate" | "publish" | "rollback") => {
    if (!selectedProjectCode) return;
    setActionLoading(action);
    setMessage("");
    setError("");
    try {
      if (action === "generate") {
        const { data } = await api.post("/bim/edd/generate", { project_code: selectedProjectCode });
        const totalUnits = data?.summary?.total_units ?? 0;
        const totalSh = data?.summary?.total_sh?.toLocaleString("fr-FR") ?? "0";
        setMessage(`EDD généré : ${totalUnits} lots, ${totalSh} m² SH`);
        // Auto-open PDF in new tab
        try {
          const pdfRes = await api.get(`/bim/edd/${selectedProjectCode}/pdf`, { responseType: "blob" });
          const url = URL.createObjectURL(pdfRes.data);
          window.open(url, "_blank");
        } catch { /* PDF download optional */ }
      } else if (action === "publish") {
        const { data } = await api.post("/bim/edd/publish", { project_code: selectedProjectCode });
        setMessage(data?.status || "EDD publié.");
      } else {
        const { data } = await api.post("/bim/edd/rollback", { project_code: selectedProjectCode, reason: rollbackReason });
        setMessage(data?.status || "EDD réouvert.");
      }
      await loadProjectData(selectedProjectCode);
      await loadProjects();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Action EDD impossible.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateUnit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProjectCode) return;
    setCreateUnitLoading(true);
    setCreateUnitError("");
    setMessage("");
    try {
      const payload = {
        block_code: createUnitForm.block_code.trim(),
        level_code: createUnitForm.level_code.trim(),
        code: createUnitForm.code.trim(),
        typology: createUnitForm.typology.trim() || undefined,
        area_sh: createUnitForm.area_sh ? Number(createUnitForm.area_sh) : undefined,
        area_su: createUnitForm.area_su ? Number(createUnitForm.area_su) : undefined,
        price_total: createUnitForm.price_total ? Number(createUnitForm.price_total) : undefined,
      };
      await api.post(`/bim/edd/${selectedProjectCode}/units`, payload);
      setShowCreateUnit(false);
      setCreateUnitForm({
        block_code: "",
        level_code: "",
        code: "",
        typology: "",
        area_sh: "",
        area_su: "",
        price_total: "",
      });
      await loadProjectData(selectedProjectCode);
      setMessage("Unité EDD créée avec succès.");
    } catch (err: any) {
      setCreateUnitError(
        err?.response?.data?.detail ?? "Erreur lors de la création de l'unité EDD."
      );
    } finally {
      setCreateUnitLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <CubeIcon className="h-5 w-5 text-slate-400" />
        <span className="text-lg font-semibold">EDD intégré à l'ADV</span>
      </div>

      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {createError && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{createError}</div>}

      <div className="card p-4 flex flex-wrap items-end gap-4">
        <div className="min-w-72 flex-1">
          <label className="block text-xs font-medium text-slate-500 mb-1">Projet EDD</label>
          <select className="input-field w-full" value={selectedProjectCode} onChange={(e) => setSelectedProjectCode(e.target.value)}>
            <option value="">Sélectionner un projet</option>
            {projects.map((project) => (
              <option key={project.id} value={project.code}>{project.code} — {project.name}</option>
            ))}
          </select>
        </div>
        <button
          onClick={() => setShowCreateProject(!showCreateProject)}
          className="btn-secondary text-sm"
          type="button"
        >
          <PlusIcon className="h-4 w-4" /> Nouveau projet EDD
        </button>
        <button
          onClick={() => setShowImport(!showImport)}
          className="btn-secondary text-sm"
          type="button"
        >
          <ArrowUpTrayIcon className="h-4 w-4" /> Import Excel
        </button>
        <button onClick={() => loadProjectData(selectedProjectCode)} disabled={!selectedProjectCode || loading} className="btn-secondary text-sm">
          <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Rafraîchir
        </button>
        <button onClick={() => runAction("generate")} disabled={!selectedProjectCode || actionLoading !== null} className="btn-primary text-sm">
          Générer EDD
        </button>
        <button
          onClick={async () => {
            try {
              const res = await api.get(`/bim/edd/${selectedProjectCode}/pdf`, { responseType: "blob" });
              const url = URL.createObjectURL(res.data);
              window.open(url, "_blank");
            } catch (err: any) {
              setError(err?.response?.data?.detail ?? "Erreur lors du téléchargement du PDF.");
            }
          }}
          disabled={!selectedProjectCode}
          className="btn-secondary text-sm"
        >
          Télécharger PDF
        </button>
        <button onClick={() => runAction("publish")} disabled={!selectedProjectCode || actionLoading !== null} className="btn-primary text-sm">
          Publier
        </button>
      </div>

      {showCreateProject && (
        <form onSubmit={handleCreateProject} className="card p-4 mt-4 grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Code projet</label>
            <input
              className="input-field"
              value={createProjectForm.code}
              onChange={(e) => setCreateProjectForm({ ...createProjectForm, code: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Nom</label>
            <input
              className="input-field"
              value={createProjectForm.name}
              onChange={(e) => setCreateProjectForm({ ...createProjectForm, name: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Latitude (optionnel)</label>
            <input
              className="input-field"
              type="number"
              step="0.000001"
              value={createProjectForm.lat}
              onChange={(e) => setCreateProjectForm({ ...createProjectForm, lat: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Longitude (optionnel)</label>
            <input
              className="input-field"
              type="number"
              step="0.000001"
              value={createProjectForm.lon}
              onChange={(e) => setCreateProjectForm({ ...createProjectForm, lon: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Angle nord (°)</label>
            <input
              className="input-field"
              type="number"
              step="0.1"
              value={createProjectForm.north_angle}
              onChange={(e) => setCreateProjectForm({ ...createProjectForm, north_angle: e.target.value })}
            />
          </div>
          <button type="submit" disabled={createLoading} className="btn-primary text-xs md:col-span-5 w-full md:w-auto">
            {createLoading ? "Création…" : "Créer le projet"}
          </button>
        </form>
      )}

      {showImport && (
        <ImportEddSection onImported={async () => {
          await loadProjects();
          if (selectedProjectCode) await loadProjectData(selectedProjectCode);
          setMessage("Import Excel terminé avec succès.");
        }} />
      )}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <div className="card p-4 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Projet & validations</h3>
              <p className="text-sm text-slate-500">Statut EDD et historique des validations</p>
            </div>
          </div>

          {!selectedProjectCode ? (
            <p className="text-sm text-slate-400">Choisissez un projet EDD.</p>
          ) : loading && !details ? (
            <p className="text-sm text-slate-400">Chargement…</p>
          ) : !details ? (
            <p className="text-sm text-slate-400">Aucune donnée EDD disponible.</p>
          ) : (
            <>
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Projet</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{details.project.code} — {details.project.name}</p>
                <p className="mt-2 text-sm text-slate-600">Statut: <span className="font-medium">{details.project.status}</span></p>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-slate-800 mb-2">Historique des validations</h4>
                <div className="space-y-2">
                  {details.validations.length === 0 ? (
                    <p className="text-sm text-slate-400">Aucune validation enregistrée.</p>
                  ) : (
                    details.validations.map((validation, index) => (
                      <div key={`${validation.stage}-${validation.ts}-${index}`} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                        <div className="flex items-center justify-between gap-4">
                          <span className="font-medium text-slate-800">{validation.stage}</span>
                          <span className="text-xs text-slate-500">{new Date(validation.ts).toLocaleString("fr-FR")}</span>
                        </div>
                        <p className="mt-1 text-slate-600">Statut: {validation.status}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="card p-4 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Réouverture EDD</h3>
            <p className="text-sm text-slate-500">Rollback vers une nouvelle version si nécessaire</p>
          </div>
          <textarea
            className="input-field min-h-28 w-full"
            placeholder="Raison de la réouverture"
            value={rollbackReason}
            onChange={(e) => setRollbackReason(e.target.value)}
          />
          <button onClick={() => runAction("rollback")} disabled={!selectedProjectCode || actionLoading !== null} className="btn-secondary text-sm">
            Réouvrir / rollback
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Unités EDD</h3>
            <span className="text-xs text-slate-500">{units.length} unité(s)</span>
          </div>
          <div className="flex items-center gap-2">
            {createUnitError && (
              <span className="text-xs text-red-600">{createUnitError}</span>
            )}
            <button
              type="button"
              onClick={() => setShowCreateUnit(!showCreateUnit)}
              disabled={!selectedProjectCode}
              className="btn-secondary text-xs"
            >
              <PlusIcon className="h-4 w-4" /> Ajouter une unité
            </button>
          </div>
        </div>
        {showCreateUnit && selectedProjectCode && (
          <form
            onSubmit={handleCreateUnit}
            className="px-4 py-3 border-b border-slate-200 bg-white grid grid-cols-1 md:grid-cols-6 gap-3 items-end"
          >
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Bloc</label>
              <input
                className="input-field"
                value={createUnitForm.block_code}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, block_code: e.target.value })}
                placeholder="BLKA"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Niveau</label>
              <input
                className="input-field"
                value={createUnitForm.level_code}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, level_code: e.target.value })}
                placeholder="L03"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Code unité</label>
              <input
                className="input-field"
                value={createUnitForm.code}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, code: e.target.value })}
                placeholder="PROJ1-BLKA-STA-L03-UNIT-AAA"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Typologie</label>
              <input
                className="input-field"
                value={createUnitForm.typology}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, typology: e.target.value })}
                placeholder="F3"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">SH (m²)</label>
              <input
                className="input-field"
                type="number"
                step="0.01"
                value={createUnitForm.area_sh}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, area_sh: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Prix total</label>
              <input
                className="input-field"
                type="number"
                step="1000"
                value={createUnitForm.price_total}
                onChange={(e) => setCreateUnitForm({ ...createUnitForm, price_total: e.target.value })}
              />
            </div>
            <div className="md:col-span-6 flex justify-end">
              <button
                type="submit"
                disabled={createUnitLoading}
                className="btn-primary text-xs"
              >
                {createUnitLoading ? "Création…" : "Créer l'unité"}
              </button>
            </div>
          </form>
        )}
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">Code</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Typologie</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">SH</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">SU</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Exposition</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Prix total</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">État EDD</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && units.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
              ) : units.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune unité EDD</td></tr>
              ) : (
                units.map((unit) => (
                  <tr key={unit.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono">{unit.code}</td>
                    <td className="px-4 py-3">{unit.typology ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{unit.area_sh.toLocaleString("fr-FR")}</td>
                    <td className="px-4 py-3 text-right">{unit.area_su.toLocaleString("fr-FR")}</td>
                    <td className="px-4 py-3">{unit.exposure ?? "—"}</td>
                    <td className="px-4 py-3 text-right font-semibold">{unit.price_total.toLocaleString("fr-FR")} DA</td>
                    <td className="px-4 py-3">{unit.edd_state}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ── Import EDD Excel ────────── */
function ImportEddSection({ onImported }: { onImported: () => void }) {
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<EddImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projectCode, setProjectCode] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImport = async (file: File) => {
    setImporting(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    if (projectCode.trim()) {
      formData.append("project_code", projectCode.trim());
    }

    try {
      const res = await api.post("/bim/edd/import-excel", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setResult(res.data);
      onImported();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "object" && detail?.message) {
        setError(detail.message);
        if (detail.ai_mapping) setResult(detail as EddImportResult);
      } else {
        setError(typeof detail === "string" ? detail : "Erreur lors de l'import");
      }
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100">
          <TableCellsIcon className="h-5 w-5 text-emerald-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Import EDD depuis Excel</h2>
          <p className="text-xs text-slate-500">
            L'agent IA comprend automatiquement les formats de colonnes (FR, EN, abrégés)
          </p>
        </div>
      </div>

      <div className="card p-4">
        <label className="block text-xs font-medium text-slate-500 mb-1">
          Code Projet (optionnel — si non présent dans le fichier)
        </label>
        <input
          value={projectCode}
          onChange={(e) => setProjectCode(e.target.value)}
          className="input-field max-w-xs"
          placeholder="Ex: PROJ01, RESIDENCE-ORAN..."
        />
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => { e.preventDefault(); setDragActive(false); const f = e.dataTransfer.files?.[0]; if (f) handleImport(f); }}
        onClick={() => fileInputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragActive
            ? "border-emerald-500 bg-emerald-50"
            : "border-slate-300 bg-white hover:border-emerald-400 hover:bg-slate-50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); e.target.value = ""; }}
        />
        {importing ? (
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent" />
            <p className="text-lg font-medium text-emerald-700">Analyse IA en cours...</p>
            <p className="text-sm text-slate-500">L'agent IA détecte les colonnes et importe les lots</p>
          </div>
        ) : (
          <>
            <ArrowUpTrayIcon className="mx-auto h-12 w-12 text-slate-300 mb-3" />
            <p className="text-lg font-medium text-slate-700">Glissez votre fichier Excel EDD ici</p>
            <p className="mt-1 text-sm text-slate-500">ou cliquez pour sélectionner — .xlsx uniquement</p>
          </>
        )}
      </div>

      <div className="card p-4 bg-gradient-to-r from-violet-50 to-indigo-50 border-violet-200">
        <div className="flex items-start gap-3">
          <SparklesIcon className="h-5 w-5 text-violet-600 mt-0.5 shrink-0" />
          <div>
            <h3 className="text-sm font-semibold text-violet-900">Agent IA de mapping</h3>
            <p className="text-xs text-violet-700 mt-1">
              L'agent IA analyse les en-têtes de votre fichier Excel et les mappe automatiquement vers les champs EDD.
            </p>
            <ul className="mt-2 text-xs text-violet-600 space-y-0.5">
              <li>- Colonnes en français : "N Lot", "Surface Hab.", "Etage", "Bloc", "Type", "Prix Total"</li>
              <li>- Abréviations : "SH", "SU", "PU", "PT", "Typ", "Niv", "Bat"</li>
              <li>- Colonnes en anglais : "Unit Code", "Floor", "Area", "Price"</li>
              <li>- Formats mixtes et personnalisés</li>
            </ul>
          </div>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-red-50 border-red-200">
          <div className="flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-red-900">Erreur d'import</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {result && result.status === "success" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{result.total_rows}</p>
              <p className="text-xs text-slate-500">Lignes lues</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-2xl font-bold text-green-600">{result.created}</p>
              <p className="text-xs text-slate-500">Lots créés</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{result.updated}</p>
              <p className="text-xs text-slate-500">Lots mis à jour</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{result.skipped}</p>
              <p className="text-xs text-slate-500">Ignorés</p>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="border-b px-4 py-3 flex items-center gap-2">
              <SparklesIcon className="h-4 w-4 text-violet-500" />
              <h3 className="font-semibold text-slate-900 text-sm">Mapping IA détecté</h3>
              {result.ai_notes && (
                <span className="text-xs text-slate-400 ml-auto">{result.ai_notes}</span>
              )}
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(result.ai_mapping).map(([header, field]) => (
                  <div
                    key={header}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
                      field ? "bg-green-50 border border-green-200" : "bg-slate-50 border border-slate-200"
                    }`}
                  >
                    <span className="font-medium text-slate-700 truncate">{header}</span>
                    <span className="text-slate-400">&rarr;</span>
                    <span className={field ? "font-mono text-green-700" : "text-slate-400"}>
                      {field || "ignoré"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="card overflow-hidden">
              <div className="border-b px-4 py-3 flex items-center gap-2">
                <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />
                <h3 className="font-semibold text-slate-900 text-sm">
                  {result.warnings.length} avertissement(s)
                </h3>
              </div>
              <div className="max-h-48 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Ligne</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Lot</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.warnings.map((w, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-2 font-mono">{w.row}</td>
                        <td className="px-4 py-2 font-mono">{w.unit_code || "—"}</td>
                        <td className="px-4 py-2 text-slate-600">{w.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/* ── Dashboard ────────── */
function DashboardSection({ filters }: { filters: Record<string, string> }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api
      .get("/adv/dashboard", { params: filters })
      .then(({ data }) => setStats(data ?? null))
      .catch(() => setStats(null));
  }, [JSON.stringify(filters)]);

  if (!stats) return <p className="text-slate-400">Chargement…</p>;

  const cards = [
    { label: "Clients", value: Number(stats.clients_count ?? 0), icon: ChartBarIcon, color: "text-teal-600 bg-teal-50" },
    { label: "Contrats actifs", value: Number(stats.active_contracts ?? 0), icon: ChartBarIcon, color: "text-green-600 bg-green-50" },
    { label: "Créances totales", value: `${Number(stats.total_receivable ?? 0).toLocaleString("fr-FR")} DA`, icon: BanknotesIcon, color: "text-amber-600 bg-amber-50" },
    { label: "Total encaissé", value: `${Number(stats.total_paid ?? 0).toLocaleString("fr-FR")} DA`, icon: BanknotesIcon, color: "text-green-600 bg-green-50" },
    { label: "Montant en retard", value: `${Number(stats.overdue_amount ?? 0).toLocaleString("fr-FR")} DA`, icon: BanknotesIcon, color: "text-red-600 bg-red-50" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="card p-5">
          <div className="flex items-center gap-3">
            <div className={`rounded-lg p-2 ${c.color}`}>
              <c.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className="text-lg font-bold text-slate-900">{c.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Clients ─────────── */
function ClientsSection({ filters, selectedEntreprise, selectedProjet }: { filters: Record<string, string>; selectedEntreprise: string; selectedProjet: string }) {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", legal_name: "", tax_id: "", ice: "",
    address: "", city: "", phone: "", email: "",
  });

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/adv/clients", { params: filters });
      setClients(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setClients([]);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/adv/clients", {
      ...form,
      entreprise_id: selectedEntreprise || undefined,
      projet_id: selectedProjet || undefined,
    });
    setShowForm(false);
    setForm({ name: "", legal_name: "", tax_id: "", ice: "", address: "", city: "", phone: "", email: "" });
    fetchClients();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-lg font-semibold">{clients.length} clients</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Nom complet *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" placeholder="Nom et prénom" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Raison sociale</label>
              <input value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} className="input-field" placeholder="Dénomination légale" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">NIF</label>
              <input value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} className="input-field" placeholder="Numéro d'identification fiscale" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">ICE / RC</label>
              <input value={form.ice} onChange={(e) => setForm({ ...form, ice: e.target.value })} className="input-field" placeholder="Registre de commerce" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Téléphone</label>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input-field" placeholder="0X XX XX XX XX" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input-field" placeholder="contact@exemple.dz" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Adresse</label>
              <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="input-field" placeholder="Rue, numéro..." />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Ville</label>
              <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className="input-field" placeholder="Alger, Oran..." />
            </div>
          </div>
          <div className="flex justify-end">
            <button type="submit" className="btn-primary text-sm">Créer le client</button>
          </div>
          <p className="text-xs text-slate-400">Le code client est généré automatiquement (CLI-XXXX)</p>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Code</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Nom</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Raison sociale</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">NIF</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">ICE / RC</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Téléphone</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Ville</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : clients.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucun client</td></tr>
            ) : (
              clients.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{c.code}</td>
                  <td className="px-4 py-3 font-medium">{c.name}</td>
                  <td className="px-4 py-3 text-slate-600">{c.legal_name ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.tax_id ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.ice ?? "—"}</td>
                  <td className="px-4 py-3 text-sm">{c.phone ?? "—"}</td>
                  <td className="px-4 py-3 text-sm">{c.city ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Contracts ────────── */
function ContractsSection({ filters, selectedEntreprise, selectedProjet }: { filters: Record<string, string>; selectedEntreprise: string; selectedProjet: string }) {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [form, setForm] = useState({
    client_id: "",
    contract_number: "",
    title: "",
    total_amount: 0,
    start_date: "",
    end_date: "",
    edd_unit_code: "",
  });

  const fetchContracts = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/adv/contracts", { params: filters });
      setContracts(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setContracts([]);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => { fetchContracts(); }, [fetchContracts]);

  useEffect(() => {
    api.get("/adv/clients", { params: filters })
      .then(({ data }) => setClients(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setClients([]));
  }, [JSON.stringify(filters)]);

  const clientLabels = new Map(clients.map((client) => [client.id, `${client.code} - ${client.name}`]));

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proofFile) {
      setFormError("Un justificatif (contrat sign\u00e9, promesse de vente) est obligatoire.");
      return;
    }
    setSubmitting(true);
    setFormError("");
    try {
      const notes = form.edd_unit_code ? `EDD_UNIT:${form.edd_unit_code.trim()}` : undefined;
      const fd = new FormData();
      fd.append("file", proofFile);
      // Send contract fields as JSON body param (FastAPI accepts body + file together)
      const body = JSON.stringify({
        client_id: form.client_id,
        contract_number: form.contract_number,
        title: form.title || undefined,
        total_amount: Number(form.total_amount),
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        notes,
        entreprise_id: selectedEntreprise || undefined,
        projet_id: selectedProjet || undefined,
      });
      fd.append("body", new Blob([body], { type: "application/json" }));
      await api.post("/adv/contracts", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      setShowForm(false);
      setProofFile(null);
      setForm({ client_id: "", contract_number: "", title: "", total_amount: 0, start_date: "", end_date: "", edd_unit_code: "" });
      fetchContracts();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail ?? "Erreur lors de la cr\u00e9ation du contrat.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-lg font-semibold">{contracts.length} contrats</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 space-y-4">
          {formError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-start gap-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
              {formError}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Client *</label>
              <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} className="input-field" required>
                <option value="">Sélectionner un client</option>
                {clients.map((client) => <option key={client.id} value={client.id}>{client.code} - {client.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">N° Contrat *</label>
              <input value={form.contract_number} onChange={(e) => setForm({ ...form, contract_number: e.target.value })} className="input-field" placeholder="CTR-001" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Intitulé</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input-field" placeholder="Vente lot F3..." />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Montant (DA) *</label>
              <input type="number" step="0.01" value={form.total_amount || ""} onChange={(e) => setForm({ ...form, total_amount: +e.target.value })} className="input-field" required min={0} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Début</label>
              <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input-field" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Unité EDD (code)</label>
              <input value={form.edd_unit_code} onChange={(e) => setForm({ ...form, edd_unit_code: e.target.value })} className="input-field" placeholder="Ex: AUREA-BLKA-L01-001" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Justificatif (contrat signé, promesse de vente) *
            </label>
            <div className={`flex items-center gap-3 rounded-lg border-2 border-dashed p-4 transition-colors ${
              proofFile ? "border-emerald-400 bg-emerald-50" : "border-slate-300 bg-white"
            }`}>
              <input
                type="file"
                accept="image/*,.pdf"
                className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-teal-600 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-teal-700 file:cursor-pointer"
                onChange={(e) => setProofFile(e.target.files?.[0] ?? null)}
                required
              />
              {proofFile && (
                <span className="text-xs text-emerald-700 font-medium">{proofFile.name}</span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">L'IA vérifie le document avant d'accepter le contrat (image ou PDF)</p>
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => { setShowForm(false); setFormError(""); setProofFile(null); }} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">
              {submitting ? "Vérification IA..." : "Créer le contrat"}
            </button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Client</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">N° Contrat</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Unité EDD</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Début</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Fin</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : contracts.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucun contrat</td></tr>
            ) : (
              contracts.map((c) => {
                const s = CONTRACT_STATUS[c.status] ?? CONTRACT_STATUS.DRAFT;
                  const eddUnit =
                    c.notes && c.notes.includes("EDD_UNIT:")
                      ? c.notes.split("EDD_UNIT:")[1].split(/\s|;/)[0]
                      : "";
                return (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">{clientLabels.get(c.client_id) ?? c.client_id}</td>
                    <td className="px-4 py-3 font-mono">{c.contract_number}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">
                        {eddUnit || "—"}
                      </td>
                    <td className="px-4 py-3"><span className={s.cls}>{s.label}</span></td>
                    <td className="px-4 py-3 text-right font-semibold">{Number(c.total_amount).toLocaleString("fr-FR")} DA</td>
                    <td className="px-4 py-3">{c.start_date ? new Date(c.start_date).toLocaleDateString("fr-FR") : "—"}</td>
                    <td className="px-4 py-3">{c.end_date ? new Date(c.end_date).toLocaleDateString("fr-FR") : "—"}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Receivables ──────── */
function ReceivablesSection({ filters }: { filters: Record<string, string> }) {
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReceivables = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/adv/receivables", { params: filters });
      setReceivables(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setReceivables([]);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => { fetchReceivables(); }, [fetchReceivables]);

  useEffect(() => {
    api.get("/adv/clients", { params: filters })
      .then(({ data }) => setClients(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setClients([]));
  }, [JSON.stringify(filters)]);

  const clientLabels = new Map(clients.map((client) => [client.id, `${client.code} - ${client.name}`]));

  const totalAmount = receivables.reduce((s, r) => s + Number(r.amount), 0);
  const totalPaid = receivables.reduce((s, r) => s + Number(r.amount_paid), 0);
  const totalRemaining = totalAmount - totalPaid;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-lg font-semibold">{receivables.length} créances</span>
        <span className="text-xs text-slate-400">Créées automatiquement depuis les contrats. Mises à jour par les paiements.</span>
      </div>

      {receivables.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="card p-3 text-center">
            <p className="text-lg font-bold text-slate-900">{totalAmount.toLocaleString("fr-FR")} DA</p>
            <p className="text-xs text-slate-500">Montant total</p>
          </div>
          <div className="card p-3 text-center">
            <p className="text-lg font-bold text-green-600">{totalPaid.toLocaleString("fr-FR")} DA</p>
            <p className="text-xs text-slate-500">Total payé</p>
          </div>
          <div className="card p-3 text-center">
            <p className={`text-lg font-bold ${totalRemaining > 0 ? "text-amber-600" : "text-emerald-600"}`}>{totalRemaining.toLocaleString("fr-FR")} DA</p>
            <p className="text-xs text-slate-500">Restant dû</p>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Client</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Réf.</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Contrat</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Payé</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Restant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Échéance</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Dernier paiement</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : receivables.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Aucune créance — créez un contrat pour en générer une automatiquement</td></tr>
            ) : (
              receivables.map((r) => {
                const remaining = Number(r.amount) - Number(r.amount_paid);
                const pct = Number(r.amount) > 0 ? (Number(r.amount_paid) / Number(r.amount)) * 100 : 0;
                const overdue = new Date(r.due_date) < new Date() && remaining > 0;
                return (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">{clientLabels.get(r.client_id) ?? r.client_id}</td>
                    <td className="px-4 py-3 font-mono text-xs">{r.invoice_ref}</td>
                    <td className="px-4 py-3 text-right">{Number(r.amount).toLocaleString("fr-FR")} DA</td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-green-700">{Number(r.amount_paid).toLocaleString("fr-FR")} DA</span>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 mt-1">
                        <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">{remaining.toLocaleString("fr-FR")} DA</td>
                    <td className="px-4 py-3">
                      <span className={overdue ? "text-red-600 font-semibold" : ""}>
                        {r.due_date ? new Date(r.due_date).toLocaleDateString("fr-FR") : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {r.last_payment_date ? new Date(r.last_payment_date).toLocaleDateString("fr-FR") : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {remaining <= 0 ? (
                        <span className="badge-success">Soldée</span>
                      ) : overdue ? (
                        <span className="badge-danger">En retard</span>
                      ) : (
                        <span className="badge-warning">En cours</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Payments ─────────── */
function PaymentsSection({ filters, selectedEntreprise, selectedProjet }: { filters: Record<string, string>; selectedEntreprise: string; selectedProjet: string }) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    client_id: "",
    receivable_id: "",
    amount: 0,
    payment_ref: "",
    bank_ref: "",
    payment_date: new Date().toISOString().slice(0, 10),
    payment_method: "VIREMENT",
  });

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/adv/payments", { params: filters });
      setPayments(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setPayments([]);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => { fetch(); }, [fetch]);

  useEffect(() => {
    api.get("/adv/clients", { params: filters })
      .then(({ data }) => setClients(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setClients([]));

    api.get("/adv/receivables", { params: filters })
      .then(({ data }) => setReceivables(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setReceivables([]));
  }, [JSON.stringify(filters)]);

  const clientLabels = new Map(clients.map((client) => [client.id, `${client.code} - ${client.name}`]));
  const openReceivables = receivables.filter((receivable) => {
    const remaining = Number(receivable.amount) - Number(receivable.amount_paid);
    return remaining > 0 && (!form.client_id || receivable.client_id === form.client_id);
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/adv/payments", {
      ...form,
      amount: Number(form.amount),
      receivable_id: form.receivable_id || undefined,
      entreprise_id: selectedEntreprise || undefined,
      projet_id: selectedProjet || undefined,
    });
    setShowForm(false);
    setForm({
      client_id: "",
      receivable_id: "",
      amount: 0,
      payment_ref: "",
      bank_ref: "",
      payment_date: new Date().toISOString().slice(0, 10),
      payment_method: "VIREMENT",
    });
    fetch();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-lg font-semibold">{payments.length} paiements</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-6 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Client</label>
            <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value, receivable_id: "" })} className="input-field" required>
              <option value="">Sélectionner un client</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.code} - {client.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Créance liée</label>
            <select
              value={form.receivable_id}
              onChange={(e) => {
                const nextReceivableId = e.target.value;
                const selectedReceivable = openReceivables.find((receivable) => receivable.id === nextReceivableId);
                if (!selectedReceivable) {
                  setForm({ ...form, receivable_id: "" });
                  return;
                }
                const remaining = Number(selectedReceivable.amount) - Number(selectedReceivable.amount_paid);
                setForm({
                  ...form,
                  receivable_id: selectedReceivable.id,
                  client_id: selectedReceivable.client_id,
                  amount: remaining,
                });
              }}
              className="input-field"
            >
              <option value="">Aucune</option>
              {openReceivables.map((receivable) => {
                const remaining = Number(receivable.amount) - Number(receivable.amount_paid);
                return (
                  <option key={receivable.id} value={receivable.id}>
                    {(receivable.invoice_ref || receivable.id)} - {remaining.toLocaleString("fr-FR")} DA
                  </option>
                );
              })}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Montant (MAD)</label>
            <input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: +e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Réf. paiement</label>
            <input value={form.payment_ref} onChange={(e) => setForm({ ...form, payment_ref: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Date</label>
            <input type="date" value={form.payment_date} onChange={(e) => setForm({ ...form, payment_date: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Mode</label>
            <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })} className="input-field">
              <option value="VIREMENT">Virement</option>
              <option value="CHEQUE">Chèque</option>
              <option value="ESPECES">Espèces</option>
              <option value="CARTE">Carte</option>
            </select>
          </div>
          <button type="submit" className="btn-primary text-xs">Enregistrer</button>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Client</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Réf.</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Mode</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : payments.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Aucun paiement</td></tr>
            ) : (
              payments.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-700">{clientLabels.get(p.client_id) ?? p.client_id}</td>
                  <td className="px-4 py-3 font-mono">{p.payment_ref}</td>
                  <td className="px-4 py-3 text-right font-semibold">{Number(p.amount).toLocaleString("fr-FR")} DA</td>
                  <td className="px-4 py-3 text-slate-600">{p.payment_method ?? "—"}</td>
                  <td className="px-4 py-3">{new Date(p.payment_date).toLocaleDateString("fr-FR")}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
