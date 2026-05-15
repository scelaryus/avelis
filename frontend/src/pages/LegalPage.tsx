import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";
import {
  ScaleIcon,
  FolderIcon,
  PlusIcon,
  ArrowUpTrayIcon,
  SparklesIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  TruckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

/* ── Shared Types ────────────────────────────────── */

interface LegalCase {
  id: string;
  title: string;
  reference: string | null;
  direction: "AGAINST_US" | "AGAINST_OTHERS";
  opposing_party: string | null;
  court_name: string | null;
  status: string;
  description: string | null;
  opened_on: string | null;
  folder_count: number;
  document_count: number;
  created_at: string | null;
}
interface LegalFolder {
  id: string;
  case_id: string;
  parent_folder_id: string | null;
  name: string;
  description: string | null;
  sort_order: number;
  document_count: number;
  created_at: string | null;
}
interface LegalDocument {
  id: string;
  filename: string;
  mime_type: string | null;
  file_size: number | null;
  doc_type: string | null;
  created_at: string | null;
  legal_case_id: string | null;
  legal_folder_id: string | null;
}
interface CaseSummary {
  summary: string;
  key_points: string[];
  recommended_next_steps: string[];
  folder_count: number;
  document_count: number;
  artifact_count: number;
  ai_model?: string;
  context_snapshot: string;
}
interface DossierJuridique {
  id: string;
  reference: string | null;
  titre: string;
  description: string | null;
  type_dossier: string | null;
  est_succession: boolean;
  partie_adverse: string | null;
  tribunal: string | null;
  montant_litige: number | null;
  statut: string | null;
  date_ouverture: string | null;
  date_cloture: string | null;
  avocat_responsable: string | null;
  created_at: string | null;
}
interface Permis {
  id: string;
  type_permis: string;
  numero: string | null;
  date_delivrance: string | null;
  date_expiration: string | null;
  autorite_delivrance: string | null;
  est_valide: boolean;
}
interface Commande {
  id: string;
  reference: string | null;
  entreprise_id: string;
  realite_financiere: string | null;
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;
  est_avance_materiel: boolean;
  statut: string | null;
  date_commande: string | null;
  date_livraison_prevue: string | null;
  description: string | null;
}
type TopTab = "contentieux" | "dossiers_gfi" | "permis" | "commandes";
type DirectionTab = "AGAINST_US" | "AGAINST_OTHERS";

const TOP_TABS: { key: TopTab; label: string; icon: typeof ScaleIcon }[] = [
  { key: "contentieux", label: "Contentieux", icon: ScaleIcon },
  { key: "dossiers_gfi", label: "Dossiers GFI", icon: FolderIcon },
  { key: "permis", label: "Permis & Autorisations", icon: ShieldCheckIcon },
  { key: "commandes", label: "Commandes d'Achat", icon: TruckIcon },
];

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Ouvert", IN_PROGRESS: "En cours", WON: "Gagne", LOST: "Perdu", SETTLED: "Regle", CLOSED: "Cloture",
  OUVERT: "Ouvert", EN_COURS: "En cours", CLOS: "Clos", ARCHIVE: "Archive",
  BROUILLON: "Brouillon", VALIDEE: "Validee", LIVREE: "Livree", ANNULEE: "Annulee",
};

const DOSSIER_TYPES = ["CONTENTIEUX", "SUCCESSION", "RECOUVREMENT", "FISCAL", "SOCIAL", "FONCIER", "AUTRE"];
const PERMIS_TYPES = ["CONSTRUIRE", "CONFORMITE", "HABITER", "EXPLOITATION", "DEMOLIR", "AUTRE"];

const RF_COLORS: Record<string, string> = {
  RF1: "bg-emerald-100 text-emerald-800",
  RF2: "bg-amber-100 text-amber-800",
  RF3: "bg-red-100 text-red-800",
  RF4: "bg-slate-100 text-slate-800",
};

function formatBytes(bytes?: number | null) {
  if (!bytes) return "\u2014";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtMoney(v: number | null | undefined) {
  if (v == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v) + " DA";
}

function fmtDate(d: string | null | undefined) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("fr-FR");
}

/* ══════════════════════════════════════════════════════════════════════════ */

export default function LegalPage() {
  const { user } = useAuth();
  const isManager = ["SUPER_ADMIN", "PDG_SUPER_ADMIN", "DAF", "CHARGE_MISSION", "admin", "hr_manager"].includes(user?.role ?? "");
  const [topTab, setTopTab] = useState<TopTab>("contentieux");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Juridique</h1>
        <p className="text-sm text-slate-500 mt-1">
          Contentieux, dossiers juridiques GFI v7.0, permis et commandes d'achat.
        </p>
      </div>

      {/* Top Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1 overflow-x-auto">
        {TOP_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTopTab(t.key)}
            className={`flex items-center gap-2 whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              topTab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {topTab === "contentieux" && <ContentieuxSection isManager={isManager} />}
      {topTab === "dossiers_gfi" && <DossiersGFISection isManager={isManager} />}
      {topTab === "permis" && <PermisSection isManager={isManager} />}
      {topTab === "commandes" && <CommandesSection isManager={isManager} />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Contentieux Section (existing legal cases)
   ══════════════════════════════════════════════════════════════════════════ */

function ContentieuxSection({ isManager }: { isManager: boolean }) {
  const [direction, setDirection] = useState<DirectionTab>("AGAINST_US");
  const [cases, setCases] = useState<LegalCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState("");
  const [folders, setFolders] = useState<LegalFolder[]>([]);
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [folderDocuments, setFolderDocuments] = useState<LegalDocument[]>([]);
  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showCaseForm, setShowCaseForm] = useState(false);
  const [showFolderForm, setShowFolderForm] = useState(false);
  const [caseForm, setCaseForm] = useState({ title: "", reference: "", direction: "AGAINST_US", opposing_party: "", court_name: "", status: "OPEN", description: "", opened_on: "" });
  const [folderForm, setFolderForm] = useState({ name: "", description: "", parent_folder_id: "", sort_order: 0 });

  const filteredCases = useMemo(() => cases.filter((c) => c.direction === direction), [cases, direction]);
  const selectedCase = filteredCases.find((c) => c.id === selectedCaseId) ?? cases.find((c) => c.id === selectedCaseId) ?? null;
  const selectedFolder = folders.find((f) => f.id === selectedFolderId) ?? null;

  const fetchCases = useCallback(async () => {
    try {
      const { data } = await api.get("/legal/cases");
      const arr = Array.isArray(data) ? data : [];
      setCases(arr);
      return arr as LegalCase[];
    } catch {
      setCases([]);
      return [] as LegalCase[];
    }
  }, []);

  const fetchCaseDetail = useCallback(async (caseId: string) => {
    const { data } = await api.get(`/legal/cases/${caseId}`);
    setFolders(Array.isArray(data?.folders) ? data.folders : []);
    setDocuments(Array.isArray(data?.documents) ? data.documents : []);
    return data;
  }, []);

  const fetchFolder = useCallback(async (folderId: string) => {
    const { data } = await api.get(`/legal/folders/${folderId}`);
    setFolderDocuments(Array.isArray(data?.documents) ? data.documents : []);
  }, []);

  const fetchSummary = useCallback(async (caseId: string) => {
    setSummaryLoading(true);
    try {
      const { data } = await api.get(`/legal/cases/${caseId}/summary`);
      setSummary(data);
    } catch {
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        const arr = await fetchCases();
        const matching = arr.filter((c) => c.direction === direction);
        const nextId = matching[0]?.id ?? arr[0]?.id ?? "";
        setSelectedCaseId(nextId);
        if (nextId) {
          const detail = await fetchCaseDetail(nextId);
          const flds = Array.isArray(detail?.folders) ? detail.folders : [];
          setSelectedFolderId(flds[0]?.id ?? "");
          if (flds[0]?.id) await fetchFolder(flds[0].id);
          await fetchSummary(nextId);
        }
      } catch (err: any) {
        setError(err?.response?.data?.detail ?? "Erreur lors du chargement.");
      } finally {
        setLoading(false);
      }
    })();
  }, [direction]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectCase = async (caseId: string) => {
    setSelectedCaseId(caseId);
    setMessage(""); setError("");
    const detail = await fetchCaseDetail(caseId);
    const flds = Array.isArray(detail?.folders) ? detail.folders : [];
    setSelectedFolderId(flds[0]?.id ?? "");
    if (flds[0]?.id) await fetchFolder(flds[0].id); else setFolderDocuments([]);
    await fetchSummary(caseId);
  };

  const handleSelectFolder = async (fid: string) => { setSelectedFolderId(fid); await fetchFolder(fid); };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setMessage("");
    try {
      const { data } = await api.post("/legal/cases", { ...caseForm, opened_on: caseForm.opened_on || null });
      setShowCaseForm(false);
      setCaseForm({ title: "", reference: "", direction, opposing_party: "", court_name: "", status: "OPEN", description: "", opened_on: "" });
      setDirection(data.direction);
      setSelectedCaseId(data.id);
      await fetchCases();
      const detail = await fetchCaseDetail(data.id);
      const flds = Array.isArray(detail?.folders) ? detail.folders : [];
      setSelectedFolderId(flds[0]?.id ?? "");
      if (flds[0]?.id) await fetchFolder(flds[0].id);
      await fetchSummary(data.id);
      setMessage("Dossier juridique cree.");
    } catch (err: any) { setError(err?.response?.data?.detail ?? "Creation impossible."); }
  };

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault(); if (!selectedCaseId) return; setError(""); setMessage("");
    try {
      const { data } = await api.post(`/legal/cases/${selectedCaseId}/folders`, { ...folderForm, parent_folder_id: folderForm.parent_folder_id || null });
      setShowFolderForm(false);
      setFolderForm({ name: "", description: "", parent_folder_id: "", sort_order: 0 });
      await fetchCaseDetail(selectedCaseId);
      setSelectedFolderId(data.id); await fetchFolder(data.id); await fetchSummary(selectedCaseId);
      setMessage("Dossier interne cree.");
    } catch (err: any) { setError(err?.response?.data?.detail ?? "Creation impossible."); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files; if (!selectedFolderId || !files?.length) return;
    setUploading(true); setError(""); setMessage("");
    try {
      for (const file of Array.from(files)) {
        const form = new FormData(); form.append("file", file);
        await api.post(`/legal/folders/${selectedFolderId}/documents/upload`, form, { headers: { "Content-Type": "multipart/form-data" } });
      }
      await fetchCaseDetail(selectedCaseId); await fetchFolder(selectedFolderId); await fetchSummary(selectedCaseId);
      setMessage("Document(s) ajoute(s).");
    } catch (err: any) { setError(err?.response?.data?.detail ?? "Ajout impossible."); }
    finally { setUploading(false); e.target.value = ""; }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-slate-900">Suivi des contentieux</h2>
        {isManager && (
          <button onClick={() => setShowCaseForm((p) => !p)} className="btn-primary">
            <PlusIcon className="h-4 w-4" /> Nouveau dossier
          </button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}

      {showCaseForm && isManager && (
        <form onSubmit={handleCreateCase} className="card p-4 grid md:grid-cols-3 gap-4">
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Intitule</label><input className="input-field" value={caseForm.title} onChange={(e) => setCaseForm({ ...caseForm, title: e.target.value })} required /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Reference</label><input className="input-field" value={caseForm.reference} onChange={(e) => setCaseForm({ ...caseForm, reference: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Type</label><select className="input-field" value={caseForm.direction} onChange={(e) => setCaseForm({ ...caseForm, direction: e.target.value })}><option value="AGAINST_US">Contre nous</option><option value="AGAINST_OTHERS">Contre des tiers</option></select></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Partie adverse</label><input className="input-field" value={caseForm.opposing_party} onChange={(e) => setCaseForm({ ...caseForm, opposing_party: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Juridiction</label><input className="input-field" value={caseForm.court_name} onChange={(e) => setCaseForm({ ...caseForm, court_name: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Statut</label><select className="input-field" value={caseForm.status} onChange={(e) => setCaseForm({ ...caseForm, status: e.target.value })}>{["OPEN","IN_PROGRESS","WON","LOST","SETTLED","CLOSED"].map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}</select></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Date d'ouverture</label><input type="date" className="input-field" value={caseForm.opened_on} onChange={(e) => setCaseForm({ ...caseForm, opened_on: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="block text-xs font-medium text-slate-500 mb-1">Description</label><textarea className="input-field min-h-24" value={caseForm.description} onChange={(e) => setCaseForm({ ...caseForm, description: e.target.value })} /></div>
          <div className="md:col-span-3 flex justify-end gap-2">
            <button type="button" onClick={() => setShowCaseForm(false)} className="btn-secondary">Annuler</button>
            <button type="submit" className="btn-primary">Creer</button>
          </div>
        </form>
      )}

      <div className="flex gap-2 border-b border-slate-200">
        <button onClick={() => setDirection("AGAINST_US")} className={`px-4 py-2 text-sm font-medium border-b-2 ${direction === "AGAINST_US" ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500"}`}>Contre nous</button>
        <button onClick={() => setDirection("AGAINST_OTHERS")} className={`px-4 py-2 text-sm font-medium border-b-2 ${direction === "AGAINST_OTHERS" ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500"}`}>Contre des tiers</button>
      </div>

      <div className="grid xl:grid-cols-[320px,1fr] gap-6">
        <div className="card p-4 space-y-3 self-start">
          <div className="flex items-center gap-2 text-slate-900 font-semibold"><ScaleIcon className="h-5 w-5 text-slate-400" />{direction === "AGAINST_US" ? "Affaires contre nous" : "Affaires engagees"}</div>
          {loading ? <p className="text-sm text-slate-400">Chargement...</p> : filteredCases.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 px-4 py-6 text-center text-sm text-slate-400">Aucun dossier. Cliquez "Nouveau dossier" pour en creer un.</div>
          ) : filteredCases.map((c) => (
            <button key={c.id} onClick={() => handleSelectCase(c.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedCaseId === c.id ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}>
              <div className="flex items-start justify-between gap-3"><div><p className="font-medium text-slate-900">{c.title}</p><p className="text-xs text-slate-500 mt-1">{c.reference || c.opposing_party || "Sans ref."}</p></div><span className="badge-info">{STATUS_LABELS[c.status] ?? c.status}</span></div>
              <div className="mt-2 text-xs text-slate-500">{c.folder_count} dossier(s) - {c.document_count} document(s)</div>
            </button>
          ))}
        </div>

        <div className="space-y-6">
          {selectedCase ? (
            <>
              <div className="grid lg:grid-cols-[1.2fr,0.8fr] gap-6">
                <div className="card p-5">
                  <div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-slate-900">{selectedCase.title}</h2><p className="text-sm text-slate-500 mt-1">{selectedCase.reference || "Ref. non renseignee"}</p></div><span className="badge-info">{STATUS_LABELS[selectedCase.status] ?? selectedCase.status}</span></div>
                  <dl className="grid sm:grid-cols-2 gap-4 mt-4 text-sm">
                    <div><dt className="text-slate-500">Partie adverse</dt><dd className="font-medium text-slate-800">{selectedCase.opposing_party || "\u2014"}</dd></div>
                    <div><dt className="text-slate-500">Juridiction</dt><dd className="font-medium text-slate-800">{selectedCase.court_name || "\u2014"}</dd></div>
                    <div><dt className="text-slate-500">Ouvert le</dt><dd className="font-medium text-slate-800">{selectedCase.opened_on || "\u2014"}</dd></div>
                    <div><dt className="text-slate-500">Documents</dt><dd className="font-medium text-slate-800">{selectedCase.document_count}</dd></div>
                  </dl>
                  <p className="mt-4 text-sm text-slate-600 whitespace-pre-wrap">{selectedCase.description || "Aucune description."}</p>
                </div>
                <div className="card p-5">
                  <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><SparklesIcon className="h-5 w-5 text-violet-500" /><h3 className="font-semibold text-slate-900">Resume IA</h3></div><button onClick={() => fetchSummary(selectedCase.id)} className="btn-secondary text-xs px-2 py-1">Actualiser</button></div>
                  {summaryLoading ? <p className="text-sm text-slate-400 mt-4">Analyse...</p> : summary ? (
                    <div className="space-y-4 mt-4 text-sm">
                      <p className="text-slate-700 leading-6">{summary.summary}</p>
                      <div><p className="font-medium text-slate-800 mb-2">Points cles</p><ul className="space-y-1 text-slate-600">{summary.key_points.length ? summary.key_points.map((p, i) => <li key={i}>- {p}</li>) : <li>Aucun.</li>}</ul></div>
                      <div><p className="font-medium text-slate-800 mb-2">Actions suivantes</p><ul className="space-y-1 text-slate-600">{summary.recommended_next_steps.map((s, i) => <li key={i}>- {s}</li>)}</ul></div>
                    </div>
                  ) : <p className="text-sm text-slate-400 mt-4">Aucun resume.</p>}
                </div>
              </div>

              <div className="grid lg:grid-cols-[0.9fr,1.1fr] gap-6">
                <div className="card p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><FolderIcon className="h-5 w-5 text-slate-400" /><h3 className="font-semibold text-slate-900">Arborescence</h3></div>
                    {isManager && <button onClick={() => setShowFolderForm((p) => !p)} className="btn-secondary text-xs px-2 py-1"><PlusIcon className="h-4 w-4" /> Ajouter</button>}
                  </div>
                  {showFolderForm && isManager && (
                    <form onSubmit={handleCreateFolder} className="rounded-xl border border-slate-200 p-3 space-y-3">
                      <div><label className="block text-xs font-medium text-slate-500 mb-1">Nom</label><input className="input-field" value={folderForm.name} onChange={(e) => setFolderForm({ ...folderForm, name: e.target.value })} required /></div>
                      <div><label className="block text-xs font-medium text-slate-500 mb-1">Parent</label><select className="input-field" value={folderForm.parent_folder_id} onChange={(e) => setFolderForm({ ...folderForm, parent_folder_id: e.target.value })}><option value="">Racine</option>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>
                      <button type="submit" className="btn-primary text-xs">Creer</button>
                    </form>
                  )}
                  <div className="space-y-2">
                    {folders.length === 0 ? <p className="text-sm text-slate-400">Aucun dossier interne.</p> : folders.map((f) => (
                      <button key={f.id} onClick={() => handleSelectFolder(f.id)} className={`w-full rounded-xl border p-3 text-left ${selectedFolderId === f.id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}>
                        <div className="flex items-center justify-between gap-3"><p className="font-medium text-slate-900">{f.name}</p><span className="text-xs text-slate-500">{f.document_count} doc(s)</span></div>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="card p-5 space-y-4">
                  <div className="flex items-center justify-between gap-4">
                    <h3 className="font-semibold text-slate-900">{selectedFolder?.name || "Documents"}</h3>
                    {isManager && selectedFolderId && (
                      <label className={`btn-primary cursor-pointer ${uploading ? "opacity-50 pointer-events-none" : ""}`}><ArrowUpTrayIcon className="h-4 w-4" />{uploading ? "Envoi..." : "Ajouter"}<input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tiff" className="hidden" onChange={handleUpload} /></label>
                    )}
                  </div>
                  <table className="w-full text-sm"><thead><tr className="border-b bg-slate-50"><th className="px-4 py-3 text-left font-medium text-slate-600">Document</th><th className="px-4 py-3 text-left font-medium text-slate-600">Type</th><th className="px-4 py-3 text-left font-medium text-slate-600">Taille</th><th className="px-4 py-3 text-left font-medium text-slate-600">Date</th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {!selectedFolderId ? <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-400">Selectionnez un dossier.</td></tr>
                        : folderDocuments.length === 0 ? <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-400">Aucun document.</td></tr>
                        : folderDocuments.map((d) => (
                          <tr key={d.id} className="hover:bg-slate-50">
                            <td className="px-4 py-3"><div className="flex items-center gap-2"><DocumentTextIcon className="h-4 w-4 text-slate-400" /><span className="font-medium text-slate-800">{d.filename}</span></div></td>
                            <td className="px-4 py-3 text-slate-600">{d.doc_type || d.mime_type || "\u2014"}</td>
                            <td className="px-4 py-3 text-slate-600">{formatBytes(d.file_size)}</td>
                            <td className="px-4 py-3 text-slate-600">{fmtDate(d.created_at)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="card p-10 text-center text-slate-400">
              {loading ? "Chargement..." : "Selectionnez ou creez un dossier juridique."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Dossiers GFI v7.0 Section
   ══════════════════════════════════════════════════════════════════════════ */

function DossiersGFISection({ isManager }: { isManager: boolean }) {
  const [items, setItems] = useState<DossierJuridique[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ titre: "", reference: "", type_dossier: "CONTENTIEUX", est_succession: false, partie_adverse: "", tribunal: "", montant_litige: "", date_ouverture: "", avocat_responsable: "", description: "" });
  const [error, setError] = useState("");

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try { const { data } = await api.get("/juridique/dossiers"); setItems(Array.isArray(data) ? data : []); } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError("");
    try {
      await api.post("/juridique/dossiers", { ...form, montant_litige: form.montant_litige ? parseFloat(form.montant_litige) : null, date_ouverture: form.date_ouverture || null });
      setShowForm(false); setForm({ titre: "", reference: "", type_dossier: "CONTENTIEUX", est_succession: false, partie_adverse: "", tribunal: "", montant_litige: "", date_ouverture: "", avocat_responsable: "", description: "" });
      fetch_();
    } catch (err: any) { setError(err?.response?.data?.detail || "Erreur."); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Dossiers Juridiques GFI v7.0</h2>
        <div className="flex gap-2">
          <button onClick={fetch_} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /> Actualiser</button>
          {isManager && <button onClick={() => setShowForm((p) => !p)} className="btn-primary"><PlusIcon className="h-4 w-4" /> Nouveau</button>}
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-4 grid md:grid-cols-3 gap-4 border-l-4 border-teal-500">
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Titre *</label><input className="input-field" value={form.titre} onChange={(e) => setForm({ ...form, titre: e.target.value })} required /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Reference</label><input className="input-field" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Type</label><select className="input-field" value={form.type_dossier} onChange={(e) => setForm({ ...form, type_dossier: e.target.value })}>{DOSSIER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Partie adverse</label><input className="input-field" value={form.partie_adverse} onChange={(e) => setForm({ ...form, partie_adverse: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Tribunal</label><input className="input-field" value={form.tribunal} onChange={(e) => setForm({ ...form, tribunal: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant litige (DA)</label><input type="number" className="input-field" value={form.montant_litige} onChange={(e) => setForm({ ...form, montant_litige: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Avocat</label><input className="input-field" value={form.avocat_responsable} onChange={(e) => setForm({ ...form, avocat_responsable: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Date ouverture</label><input type="date" className="input-field" value={form.date_ouverture} onChange={(e) => setForm({ ...form, date_ouverture: e.target.value })} /></div>
          <div className="flex items-center gap-2 pt-5"><input type="checkbox" checked={form.est_succession} onChange={(e) => setForm({ ...form, est_succession: e.target.checked })} /><label className="text-sm text-slate-700">Dossier succession (FC-002)</label></div>
          <div className="md:col-span-3"><label className="block text-xs font-medium text-slate-500 mb-1">Description</label><textarea className="input-field" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></div>
          {error && <div className="md:col-span-3 text-sm text-red-600">{error}</div>}
          <div className="md:col-span-3 flex justify-end gap-2"><button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Annuler</button><button type="submit" className="btn-primary">Creer</button></div>
        </form>
      )}

      {loading ? <div className="flex justify-center py-8"><ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" /></div> : items.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">Aucun dossier juridique GFI. Cliquez "Nouveau" pour en creer.</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((d) => (
            <div key={d.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{d.titre}</p>
                  <p className="text-xs text-slate-500 mt-1">{d.reference || "Sans ref."} | {d.type_dossier || "Non type"}</p>
                </div>
                <div className="flex items-center gap-2">
                  {d.est_succession && <span className="inline-flex items-center rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-800">Succession</span>}
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${d.statut === "OUVERT" ? "bg-blue-100 text-blue-800" : d.statut === "CLOS" ? "bg-slate-100 text-slate-800" : "bg-amber-100 text-amber-800"}`}>{STATUS_LABELS[d.statut ?? ""] ?? d.statut}</span>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div>Partie adverse: <span className="font-medium text-slate-800">{d.partie_adverse || "\u2014"}</span></div>
                <div>Tribunal: <span className="font-medium text-slate-800">{d.tribunal || "\u2014"}</span></div>
                <div>Montant litige: <span className="font-medium text-slate-800">{d.montant_litige ? fmtMoney(d.montant_litige) : "\u2014"}</span></div>
                <div>Avocat: <span className="font-medium text-slate-800">{d.avocat_responsable || "\u2014"}</span></div>
                <div>Ouvert le: <span className="font-medium text-slate-800">{fmtDate(d.date_ouverture)}</span></div>
                {d.date_cloture && <div>Clos le: <span className="font-medium text-slate-800">{fmtDate(d.date_cloture)}</span></div>}
              </div>
              {d.description && <p className="mt-2 text-xs text-slate-500">{d.description}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Permis & Autorisations Section
   ══════════════════════════════════════════════════════════════════════════ */

function PermisSection({ isManager }: { isManager: boolean }) {
  const [items, setItems] = useState<Permis[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ type_permis: "CONSTRUIRE", numero: "", date_delivrance: "", date_expiration: "", autorite_delivrance: "" });
  const [error, setError] = useState("");

  const fetch_ = useCallback(async () => { setLoading(true); try { const { data } = await api.get("/juridique/permis"); setItems(Array.isArray(data) ? data : []); } catch { setItems([]); } finally { setLoading(false); } }, []);
  useEffect(() => { fetch_(); }, [fetch_]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError("");
    try {
      await api.post("/juridique/permis", { ...form, date_delivrance: form.date_delivrance || null, date_expiration: form.date_expiration || null });
      setShowForm(false); setForm({ type_permis: "CONSTRUIRE", numero: "", date_delivrance: "", date_expiration: "", autorite_delivrance: "" }); fetch_();
    } catch (err: any) { setError(err?.response?.data?.detail || "Erreur."); }
  };

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Permis & Autorisations</h2>
        <div className="flex gap-2">
          <button onClick={fetch_} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /> Actualiser</button>
          {isManager && <button onClick={() => setShowForm((p) => !p)} className="btn-primary"><PlusIcon className="h-4 w-4" /> Nouveau</button>}
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-4 grid md:grid-cols-3 gap-4 border-l-4 border-teal-500">
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Type *</label><select className="input-field" value={form.type_permis} onChange={(e) => setForm({ ...form, type_permis: e.target.value })}>{PERMIS_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Numero</label><input className="input-field" value={form.numero} onChange={(e) => setForm({ ...form, numero: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Autorite</label><input className="input-field" value={form.autorite_delivrance} onChange={(e) => setForm({ ...form, autorite_delivrance: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Date delivrance</label><input type="date" className="input-field" value={form.date_delivrance} onChange={(e) => setForm({ ...form, date_delivrance: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Date expiration</label><input type="date" className="input-field" value={form.date_expiration} onChange={(e) => setForm({ ...form, date_expiration: e.target.value })} /></div>
          {error && <div className="md:col-span-3 text-sm text-red-600">{error}</div>}
          <div className="md:col-span-3 flex justify-end gap-2"><button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Annuler</button><button type="submit" className="btn-primary">Creer</button></div>
        </form>
      )}

      {loading ? <div className="flex justify-center py-8"><ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" /></div> : items.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">Aucun permis enregistre.</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="border-b bg-slate-50 text-left text-xs text-slate-500"><th className="px-4 py-3">Type</th><th className="px-4 py-3">Numero</th><th className="px-4 py-3">Autorite</th><th className="px-4 py-3">Delivrance</th><th className="px-4 py-3">Expiration</th><th className="px-4 py-3 text-center">Statut</th></tr></thead>
            <tbody>
              {items.map((p) => {
                const expired = p.date_expiration && p.date_expiration < today;
                return (
                  <tr key={p.id} className={`border-b border-slate-100 ${expired ? "bg-red-50" : ""}`}>
                    <td className="px-4 py-3 font-medium text-slate-900">{p.type_permis}</td>
                    <td className="px-4 py-3 text-slate-600">{p.numero || "\u2014"}</td>
                    <td className="px-4 py-3 text-slate-600">{p.autorite_delivrance || "\u2014"}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtDate(p.date_delivrance)}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtDate(p.date_expiration)}</td>
                    <td className="px-4 py-3 text-center">
                      {expired ? <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800"><XCircleIcon className="h-3 w-3" />Expire</span>
                        : <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800"><CheckCircleIcon className="h-3 w-3" />Valide</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Commandes d'Achat Section
   ══════════════════════════════════════════════════════════════════════════ */

function CommandesSection({ isManager }: { isManager: boolean }) {
  const [items, setItems] = useState<Commande[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ entreprise_id: "", reference: "", realite_financiere: "RF1", montant_ht: "", montant_tva: "", est_avance_materiel: false, date_commande: new Date().toISOString().slice(0, 10), description: "" });
  const [error, setError] = useState("");

  const fetch_ = useCallback(async () => { setLoading(true); try { const { data } = await api.get("/juridique/commandes"); setItems(Array.isArray(data) ? data : []); } catch { setItems([]); } finally { setLoading(false); } }, []);
  useEffect(() => { fetch_(); }, [fetch_]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError("");
    try {
      await api.post("/juridique/commandes", { ...form, montant_ht: parseFloat(form.montant_ht), montant_tva: parseFloat(form.montant_tva || "0") });
      setShowForm(false); setForm({ entreprise_id: "", reference: "", realite_financiere: "RF1", montant_ht: "", montant_tva: "", est_avance_materiel: false, date_commande: new Date().toISOString().slice(0, 10), description: "" }); fetch_();
    } catch (err: any) { setError(err?.response?.data?.detail || "Erreur."); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Commandes d'Achat</h2>
        <div className="flex gap-2">
          <button onClick={fetch_} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /> Actualiser</button>
          {isManager && <button onClick={() => setShowForm((p) => !p)} className="btn-primary"><PlusIcon className="h-4 w-4" /> Nouvelle</button>}
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-4 grid md:grid-cols-3 gap-4 border-l-4 border-teal-500">
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Entreprise ID *</label><input className="input-field" value={form.entreprise_id} onChange={(e) => setForm({ ...form, entreprise_id: e.target.value })} required /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Reference</label><input className="input-field" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Realite Financiere *</label><select className="input-field" value={form.realite_financiere} onChange={(e) => setForm({ ...form, realite_financiere: e.target.value })}><option value="RF1">RF1 - Reel Declare</option><option value="RF2">RF2 - Reel Non Declare</option><option value="RF3">RF3 - Fictif Declare</option><option value="RF4">RF4 - Fictif Non Declare</option></select></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant HT *</label><input type="number" className="input-field" value={form.montant_ht} onChange={(e) => setForm({ ...form, montant_ht: e.target.value })} required /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant TVA</label><input type="number" className="input-field" value={form.montant_tva} onChange={(e) => setForm({ ...form, montant_tva: e.target.value })} /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Date commande</label><input type="date" className="input-field" value={form.date_commande} onChange={(e) => setForm({ ...form, date_commande: e.target.value })} required /></div>
          <div className="flex items-center gap-2 pt-5"><input type="checkbox" checked={form.est_avance_materiel} onChange={(e) => setForm({ ...form, est_avance_materiel: e.target.checked })} /><label className="text-sm text-slate-700">Avance materiel (KT-05: pas de sortie cash 512)</label></div>
          <div className="md:col-span-2"><label className="block text-xs font-medium text-slate-500 mb-1">Description</label><textarea className="input-field" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></div>
          {error && <div className="md:col-span-3 text-sm text-red-600">{error}</div>}
          <div className="md:col-span-3 flex justify-end gap-2"><button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Annuler</button><button type="submit" className="btn-primary">Creer</button></div>
        </form>
      )}

      {loading ? <div className="flex justify-center py-8"><ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" /></div> : items.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">Aucune commande d'achat.</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="border-b bg-slate-50 text-left text-xs text-slate-500"><th className="px-4 py-3">Ref.</th><th className="px-4 py-3">RF</th><th className="px-4 py-3 text-right">HT</th><th className="px-4 py-3 text-right">TTC</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Statut</th><th className="px-4 py-3 text-center">Avance Mat.</th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{c.reference || c.id.slice(0, 8)}</td>
                  <td className="px-4 py-3">{c.realite_financiere ? <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${RF_COLORS[c.realite_financiere] || ""}`}>{c.realite_financiere}</span> : "\u2014"}</td>
                  <td className="px-4 py-3 text-right">{fmtMoney(c.montant_ht)}</td>
                  <td className="px-4 py-3 text-right font-semibold">{fmtMoney(c.montant_ttc)}</td>
                  <td className="px-4 py-3 text-slate-600">{fmtDate(c.date_commande)}</td>
                  <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${c.statut === "LIVREE" ? "bg-emerald-100 text-emerald-800" : c.statut === "ANNULEE" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"}`}>{STATUS_LABELS[c.statut ?? ""] ?? c.statut}</span></td>
                  <td className="px-4 py-3 text-center">{c.est_avance_materiel ? <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 inline" title="KT-05" /> : "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

