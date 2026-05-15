import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import {
  ArrowUpTrayIcon,
  DocumentTextIcon,
  MagnifyingGlassIcon,
  TrashIcon,
  EyeIcon,
  CpuChipIcon,
  BanknotesIcon,
  PencilIcon,
  ArrowTopRightOnSquareIcon,
  CheckIcon,
  XMarkIcon,
  DocumentDuplicateIcon,
  CloudArrowUpIcon,
  ArrowPathIcon,
  FunnelIcon,
  MagnifyingGlassPlusIcon,
} from "@heroicons/react/24/outline";
import { isGoogleDriveEnabled, pickAndDownloadDriveFiles } from "../lib/googleDrive";
import DocumentViewer from "../components/DocumentViewer";
import { docDownloadUrl } from "../api/docUrl";

interface Document {
  id: string;
  filename: string;
  doc_type: string | null;
  doc_type_confidence: number | null;
  sha256: string;
  mime_type: string | null;
  file_size: number;
  page_count: number | null;
  has_text_layer: boolean | null;
  storage_key: string;
  created_at: string;
  realite_financiere: string | null;
  // AI classification fields
  extracted_montant: number | null;
  extracted_montant_ht: number | null;
  extracted_tva: number | null;
  extracted_date: string | null;
  extracted_reference: string | null;
  extracted_emetteur: string | null;
  extracted_destinataire: string | null;
  classification_reasoning: string | null;
  module_routed_to: string | null;
  entreprise_id: string | null;
  projet_id: string | null;
  statut_ingestion: string | null;
  champs_manquants: string[] | null;
  adv_record_id: string | null;
}

interface EntrepriseOption {
  id: string;
  code: string;
  raison_sociale: string;
}

interface UploadItem extends Document {
  upload_status?: string | null;
  processing_status?: string | null;
  is_duplicate?: boolean;
  workflow_id?: string | null;
  workflow_status?: string | null;
  routed_to?: string | null;
  created_record_ids?: string[];
  journal_entry_ids?: string[];
  warnings?: unknown[] | null;
  errors?: unknown[] | null;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  INVOICE: "Facture",
  RECEIPT: "Reçu",
  CONTRACT: "Contrat",
  BANK_STATEMENT: "Relevé bancaire",
  PAYROLL: "Paie",
  ADV_CONTRACT: "Acte de vente",
  ADV_PAYMENT: "Paiement ADV",
  CHEQUE: "Chèque",
  BON_COMMANDE: "Bon de commande",
  DEVIS: "Devis",
  AVOIR: "Avoir",
  BULLETIN_PAIE: "Bulletin de paie",
  QUITTANCE: "Quittance",
  ATTESTATION: "Attestation",
  BON_LIVRAISON: "Bon de livraison",
  OTHER: "Autre",
};

const DOC_TYPE_COLORS: Record<string, string> = {
  INVOICE: "bg-blue-100 text-blue-700",
  RECEIPT: "bg-green-100 text-green-700",
  CONTRACT: "bg-purple-100 text-purple-700",
  BANK_STATEMENT: "bg-amber-100 text-amber-700",
  CHEQUE: "bg-cyan-100 text-cyan-700",
  BON_COMMANDE: "bg-orange-100 text-orange-700",
  DEVIS: "bg-indigo-100 text-indigo-700",
  AVOIR: "bg-red-100 text-red-700",
  BULLETIN_PAIE: "bg-emerald-100 text-emerald-700",
  QUITTANCE: "bg-teal-100 text-teal-700",
  ATTESTATION: "bg-sky-100 text-sky-700",
  BON_LIVRAISON: "bg-lime-100 text-lime-700",
  ADV_CONTRACT: "bg-violet-100 text-violet-700",
  ADV_PAYMENT: "bg-fuchsia-100 text-fuchsia-700",
  PAYROLL: "bg-emerald-100 text-emerald-700",
  OTHER: "bg-slate-100 text-slate-600",
};

const MODULE_LABELS: Record<string, string> = {
  documents: "Documents",
  comptabilite: "Comptabilite",
  adv: "ADV",
  hr: "RH",
};

const MODULE_PATHS: Record<string, string> = {
  documents: "/documents",
  comptabilite: "/accounting",
  adv: "/adv",
  hr: "/hr",
};

const RF_OPTIONS = [
  { value: "RF1", label: "Reel Declare", desc: "Document reel et declare fiscalement", color: "border-blue-300 bg-blue-50 text-blue-800" },
  { value: "RF2", label: "Reel Non Declare", desc: "Document reel mais non declare", color: "border-amber-300 bg-amber-50 text-amber-800" },
  { value: "RF3", label: "Fictif Declare", desc: "Document fictif mais declare", color: "border-violet-300 bg-violet-50 text-violet-800" },
  { value: "RF4", label: "Fictif Non Declare", desc: "Document fictif et non declare", color: "border-red-300 bg-red-50 text-red-800" },
];

const RF_LABELS: Record<string, string> = {
  RF1: "Reel Declare",
  RF2: "Reel Non Declare",
  RF3: "Fictif Declare",
  RF4: "Fictif Non Declare",
};

const RF_COLORS: Record<string, string> = {
  RF1: "bg-blue-100 text-blue-700",
  RF2: "bg-amber-100 text-amber-700",
  RF3: "bg-violet-100 text-violet-700",
  RF4: "bg-red-100 text-red-700",
};

const PROCESSING_STATUS_COLORS: Record<string, string> = {
  COMMITTED: "text-emerald-700 bg-emerald-50 border-emerald-200",
  READY_TO_COMMIT: "text-emerald-700 bg-emerald-50 border-emerald-200",
  BLOCKED: "text-amber-700 bg-amber-50 border-amber-200",
  FAILED: "text-amber-700 bg-amber-50 border-amber-200",
  INGESTED: "text-blue-700 bg-blue-50 border-blue-200",
  DUPLICATE: "text-slate-600 bg-slate-50 border-slate-200",
};
const PROCESSING_STATUS_LABELS: Record<string, string> = {
  COMMITTED: "Traité",
  READY_TO_COMMIT: "Traité",
  BLOCKED: "En attente",
  FAILED: "Classé (OCR partiel)",
  INGESTED: "Importé",
  DUPLICATE: "Doublon",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatMontant(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("fr-DZ", { style: "decimal", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + " DA";
}

function getModuleLabel(moduleName: string | null | undefined): string {
  if (!moduleName) return "—";
  return MODULE_LABELS[moduleName] ?? moduleName;
}

/* ══════════════════════════════════════════════════════════════════════════ */
/*  Unified Documents Page — tabs: Documents / Import en masse              */
/* ══════════════════════════════════════════════════════════════════════════ */

import ImportPage from "./ImportPage";

export default function DocumentsPage() {
  const [activeTab, setActiveTab] = useState<"documents" | "import" | "pipeline" | "ged">("documents");

  const TABS: { key: typeof activeTab; label: string }[] = [
    { key: "documents", label: "Documents" },
    { key: "import", label: "Import en masse" },
    { key: "pipeline", label: "Pipeline (7 couches)" },
    { key: "ged", label: "GED / Arborescence" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-slate-900">Documents</h1>
      </div>
      <p className="text-sm text-slate-500 mb-4">
        Gestion documentaire unifi&eacute;e &mdash; pipeline 7 couches, GED normalis&eacute;e, recherche full-text
      </p>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "documents" && <DocumentsContent />}
      {activeTab === "import" && <ImportPage />}
      {activeTab === "pipeline" && <PipelineSection />}
      {activeTab === "ged" && <GEDSection />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Pipeline 7 Couches (Section 14)
   ══════════════════════════════════════════════════════ */
function PipelineSection() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => {
    api.get("/documents/pipeline/stats").then(({ data }) => setStats(data)).catch(() => {});
  }, []);

  if (!stats) return <p className="text-slate-400">Chargement&hellip;</p>;

  const COUCHE_COLORS = ["bg-blue-500", "bg-indigo-500", "bg-violet-500", "bg-teal-500", "bg-emerald-500", "bg-amber-500", "bg-rose-500"];

  return (
    <div className="space-y-6">
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Pipeline d'ingestion — 7 couches (Section 14)</h3>
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          {stats.pipeline.map((c: any, i: number) => (
            <div key={c.couche} className="text-center">
              <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center text-white font-bold text-sm ${COUCHE_COLORS[i]}`}>
                {c.couche}
              </div>
              <p className="text-xs font-medium text-slate-700 mt-2">{c.nom}</p>
              <p className="text-lg font-bold text-slate-800">{c.count}</p>
              <div className="w-full h-1.5 rounded-full bg-slate-100 mt-1 overflow-hidden">
                <div className={`h-full rounded-full ${COUCHE_COLORS[i]}`} style={{ width: `${c.pct}%` }} />
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">{c.pct}%</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="card p-4 text-center">
          <p className="text-3xl font-bold text-slate-800">{stats.total_documents}</p>
          <p className="text-xs text-slate-500 mt-1">Documents total</p>
        </div>
        <div className="card p-4 text-center border-2 border-amber-200">
          <p className="text-3xl font-bold text-amber-700">{stats.a_completer}</p>
          <p className="text-xs text-amber-600 mt-1">&Agrave; compl&eacute;ter (EX-ING-002)</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-3xl font-bold text-teal-700">
            {stats.total_documents > 0 ? Math.round(stats.pipeline[6]?.count / stats.total_documents * 100) : 0}%
          </p>
          <p className="text-xs text-slate-500 mt-1">Index&eacute;s full-text (C7)</p>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   GED Arborescence (Section 15 — EX-GED-001)
   ══════════════════════════════════════════════════════ */
function GEDSection() {
  const [tree, setTree] = useState<any>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [aiQuery, setAiQuery] = useState("");
  const [aiAnswer, setAiAnswer] = useState<{ answer: string; calculation_details?: string; documents_analyzed: number; documents_matched: number } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    api.get("/documents/ged/tree").then(({ data }) => setTree(data)).catch(() => {});
  }, []);

  if (!tree) return <p className="text-slate-400">Chargement...</p>;

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const matchesSearch = (text: string) => !search || text.toLowerCase().includes(search.toLowerCase());

  const entities = Object.keys(tree).sort().filter((ent) => {
    if (!search) return true;
    if (matchesSearch(ent)) return true;
    for (const proj of Object.keys(tree[ent])) {
      if (matchesSearch(proj)) return true;
      for (const year of Object.keys(tree[ent][proj])) {
        if (matchesSearch(year)) return true;
        for (const dtype of Object.keys(tree[ent][proj][year])) {
          if (matchesSearch(dtype)) return true;
        }
      }
    }
    return false;
  });

  const handleAiQuery = async () => {
    if (!aiQuery.trim()) return;
    setAiLoading(true);
    setAiAnswer(null);
    try {
      const { data } = await api.post("/documents/ged/ai-query", { question: aiQuery });
      setAiAnswer(data);
    } catch (err: any) {
      setAiAnswer({ answer: err?.response?.data?.detail || "Erreur", documents_analyzed: 0, documents_matched: 0 });
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* AI Query Panel */}
      <div className="card p-4 bg-gradient-to-r from-violet-50 to-indigo-50 border-violet-200">
        <h3 className="text-sm font-semibold text-violet-900 mb-2">Agent IA - Analyse documentaire</h3>
        <p className="text-xs text-violet-600 mb-3">Posez des questions sur vos documents : sommes, totaux, listes, recherches par date/type/montant</p>
        <div className="flex gap-2">
          <input
            className="input-field flex-1"
            placeholder="Ex: Quelle est la somme des chèques de 2024 ? Combien de factures en janvier ?"
            value={aiQuery}
            onChange={(e) => setAiQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAiQuery()}
          />
          <button onClick={handleAiQuery} disabled={aiLoading || !aiQuery.trim()} className="btn-primary text-sm whitespace-nowrap">
            {aiLoading ? "Analyse..." : "Interroger l'IA"}
          </button>
        </div>
        {aiAnswer && (
          <div className="mt-3 rounded-lg bg-white border border-violet-200 p-4">
            <p className="text-sm text-slate-800 whitespace-pre-wrap">{aiAnswer.answer}</p>
            {aiAnswer.calculation_details && (
              <p className="text-xs text-slate-500 mt-2 font-mono bg-slate-50 p-2 rounded">{aiAnswer.calculation_details}</p>
            )}
            <p className="text-xs text-violet-400 mt-2">{aiAnswer.documents_analyzed} documents analysés, {aiAnswer.documents_matched} correspondants</p>
          </div>
        )}
      </div>

      {/* Tree with search */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">Arborescence GED</h3>
            <p className="text-xs text-slate-400">Structure : /Entité/Projet/Année/Type Document</p>
          </div>
          <div className="relative">
            <MagnifyingGlassIcon className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className="input-field pl-9 w-64 text-sm"
              placeholder="Rechercher dans l'arborescence..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {entities.length === 0 ? (
          <p className="text-sm text-slate-400 py-8 text-center">{search ? "Aucun résultat pour cette recherche" : "Aucun document dans la GED"}</p>
        ) : (
          <div className="space-y-1">
            {entities.map((ent) => {
              const entKey = `ent-${ent}`;
              const isEntOpen = expanded.has(entKey) || !!search;
              const projets = Object.keys(tree[ent]).sort().filter((proj) => {
                if (!search) return true;
                if (matchesSearch(ent) || matchesSearch(proj)) return true;
                for (const year of Object.keys(tree[ent][proj])) {
                  if (matchesSearch(year)) return true;
                  for (const dtype of Object.keys(tree[ent][proj][year])) {
                    if (matchesSearch(dtype)) return true;
                  }
                }
                return false;
              });

              return (
                <div key={ent}>
                  <button onClick={() => toggle(entKey)}
                    className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded hover:bg-slate-50 text-sm">
                    <span className="text-xs">{isEntOpen ? "\u25BC" : "\u25B6"}</span>
                    <span className="font-mono text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{ent}</span>
                    <span className="text-slate-500 text-xs">({projets.length} projet(s))</span>
                  </button>
                  {isEntOpen && (
                    <div className="ml-6 space-y-0.5">
                      {projets.map((proj) => {
                        const projKey = `${entKey}-${proj}`;
                        const isProjOpen = expanded.has(projKey) || !!search;
                        const years = Object.keys(tree[ent][proj]).sort();

                        return (
                          <div key={proj}>
                            <button onClick={() => toggle(projKey)}
                              className="flex items-center gap-2 w-full text-left px-2 py-1 rounded hover:bg-slate-50 text-sm">
                              <span className="text-xs">{isProjOpen ? "\u25BC" : "\u25B6"}</span>
                              <span className="font-mono text-xs bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded">{proj}</span>
                            </button>
                            {isProjOpen && (
                              <div className="ml-6 space-y-0.5">
                                {years.map((year) => {
                                  const yearKey = `${projKey}-${year}`;
                                  const isYearOpen = expanded.has(yearKey) || !!search;
                                  const types = Object.entries(tree[ent][proj][year]) as [string, any][];
                                  const filteredTypes = types.filter(([dtype]) => !search || matchesSearch(ent) || matchesSearch(proj) || matchesSearch(year) || matchesSearch(dtype));

                                  if (filteredTypes.length === 0) return null;

                                  return (
                                    <div key={year}>
                                      <button onClick={() => toggle(yearKey)}
                                        className="flex items-center gap-2 w-full text-left px-2 py-1 rounded hover:bg-slate-50 text-sm">
                                        <span className="text-xs">{isYearOpen ? "\u25BC" : "\u25B6"}</span>
                                        <span className="text-xs font-medium text-slate-600">{year}</span>
                                      </button>
                                      {isYearOpen && (
                                        <div className="ml-6">
                                          {filteredTypes.map(([dtype, info]) => (
                                            <div key={dtype} className="flex items-center gap-3 px-2 py-1 text-xs text-slate-600">
                                              <span className="w-3 h-3 rounded bg-teal-200 shrink-0" />
                                              <span className="font-medium">{dtype}</span>
                                              <span className="text-slate-400">{info.count} doc(s)</span>
                                              <span className="text-slate-300">{Math.round(info.size / 1024)} KB</span>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


function DocumentsContent() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [processing, setProcessing] = useState<string | null>(null);
  const [processResult, setProcessResult] = useState<any | null>(null);
  const [correcting, setCorrecting] = useState<Document | null>(null);
  const [correctionForm, setCorrectionForm] = useState<any>({});
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [uploadReport, setUploadReport] = useState<any | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [advInjecting, setAdvInjecting] = useState(false);
  const [advReport, setAdvReport] = useState<any | null>(null);
  const [rfModal, setRfModal] = useState(false);
  const [rfPendingFiles, setRfPendingFiles] = useState<File[]>([]);
  const [rfSelection, setRfSelection] = useState("RF1");
  const [viewerDoc, setViewerDoc] = useState<Document | null>(null);
  const [completingDoc, setCompletingDoc] = useState<Document | null>(null);
  const [entreprises, setEntreprises] = useState<EntrepriseOption[]>([]);
  const [filterEntreprise, setFilterEntreprise] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterRF, setFilterRF] = useState("");
  const advFileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/documents/");
      setDocuments(Array.isArray(data) ? data : (data?.items ?? []));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
    api.get("/entites-juridiques/").then(({ data }) => {
      if (Array.isArray(data)) {
        setEntreprises(data.map((e: any) => ({ id: e.id, code: e.code, raison_sociale: e.raison_sociale })));
      }
    }).catch(() => {});
  }, [fetchDocs]);

  const uploadFiles = async (fileList: FileList | File[], rf?: string) => {
    const files = Array.from(fileList);
    if (!files.length) return;
    setUploading(true);
    setUploadReport(null);
    try {
      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      const params: Record<string, string> = {};
      if (rf) params.realite_financiere = rf;
      const { data } = await api.post("/documents/bulk-upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        params,
      });
      setUploadReport(data);
      await fetchDocs();
    } finally {
      setUploading(false);
    }
  };

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    setRfPendingFiles(Array.from(files));
    setRfSelection("RF1");
    setRfModal(true);
    e.target.value = "";
  };

  const handleRfConfirm = async () => {
    setRfModal(false);
    await uploadFiles(rfPendingFiles, rfSelection);
    setRfPendingFiles([]);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer ce document ?")) return;
    await api.delete(`/documents/${id}`);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (selectedDoc?.id === id) setSelectedDoc(null);
  };

  const handleView = async (doc: Document) => {
    setSelectedDoc(doc);
    setProcessResult(null);
    try {
      const { data } = await api.get(`/documents/${doc.id}/artifacts`);
      setArtifacts(data);
    } catch {
      setArtifacts([]);
    }
  };

  const handleProcess = async (doc: Document) => {
    setProcessing(doc.id);
    setProcessResult(null);
    setSelectedDoc(doc);
    try {
      const { data } = await api.post(`/documents/${doc.id}/process`);
      setProcessResult(data);
      // Refresh artifacts after processing
      try {
        const { data: arts } = await api.get(`/documents/${doc.id}/artifacts`);
        setArtifacts(arts);
      } catch {
        setArtifacts(data.artifacts ?? []);
      }
      // Refresh doc list to pick up doc_type changes
      await fetchDocs();
    } catch (err: any) {
      setProcessResult({
        status: "error",
        error: err.response?.data?.detail ?? err.message ?? "Erreur de traitement",
      });
    } finally {
      setProcessing(null);
    }
  };

  const filtered = documents.filter((d) => {
    // Text search
    if (search) {
      const q = search.toLowerCase();
      const matchText = d.filename.toLowerCase().includes(q) ||
        (d.doc_type && DOC_TYPE_LABELS[d.doc_type]?.toLowerCase().includes(q));
      if (!matchText) return false;
    }
    // Entreprise filter
    if (filterEntreprise && d.entreprise_id !== filterEntreprise) return false;
    // Type filter
    if (filterType && d.doc_type !== filterType) return false;
    // RF filter
    if (filterRF && d.realite_financiere !== filterRF) return false;
    return true;
  });

  const openCorrection = (doc: Document) => {
    setCorrecting(doc);
    setCorrectionForm({
      doc_type: doc.doc_type || "OTHER",
      extracted_montant: doc.extracted_montant ?? "",
      extracted_montant_ht: doc.extracted_montant_ht ?? "",
      extracted_tva: doc.extracted_tva ?? "",
      extracted_date: doc.extracted_date ?? "",
      extracted_reference: doc.extracted_reference ?? "",
      extracted_emetteur: doc.extracted_emetteur ?? "",
      extracted_destinataire: doc.extracted_destinataire ?? "",
    });
  };

  const handleSaveCorrection = async () => {
    if (!correcting) return;
    setSavingCorrection(true);
    try {
      const payload: any = {};
      if (correctionForm.doc_type) payload.doc_type = correctionForm.doc_type;
      if (correctionForm.extracted_montant !== "" && correctionForm.extracted_montant !== null)
        payload.extracted_montant = parseFloat(correctionForm.extracted_montant);
      if (correctionForm.extracted_montant_ht !== "" && correctionForm.extracted_montant_ht !== null)
        payload.extracted_montant_ht = parseFloat(correctionForm.extracted_montant_ht);
      if (correctionForm.extracted_tva !== "" && correctionForm.extracted_tva !== null)
        payload.extracted_tva = parseFloat(correctionForm.extracted_tva);
      if (correctionForm.extracted_date) payload.extracted_date = correctionForm.extracted_date;
      if (correctionForm.extracted_reference) payload.extracted_reference = correctionForm.extracted_reference;
      if (correctionForm.extracted_emetteur) payload.extracted_emetteur = correctionForm.extracted_emetteur;
      if (correctionForm.extracted_destinataire) payload.extracted_destinataire = correctionForm.extracted_destinataire;

      const { data } = await api.patch(`/documents/${correcting.id}`, payload);
      setCorrecting(null);
      setSelectedDoc(data);
      await fetchDocs();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erreur lors de la correction");
    } finally {
      setSavingCorrection(false);
    }
  };

  const handleOpenDocument = (doc: Document) => {
    setViewerDoc(doc);
  };

  const handleAdvBulkInject = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    setAdvInjecting(true);
    setAdvReport(null);
    try {
      const fd = new FormData();
      Array.from(files).forEach((f) => fd.append("files", f));
      const { data } = await api.post("/adv/bulk-classify", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAdvReport(data);
      await fetchDocs();
    } catch (err: any) {
      setAdvReport({ error: err?.response?.data?.detail || "Erreur injection ADV" });
    } finally {
      setAdvInjecting(false);
      e.target.value = "";
    }
  };

  const handleDriveImport = async () => {
    try {
      const files = await pickAndDownloadDriveFiles();
      if (files.length) await uploadFiles(files);
    } catch (err: any) {
      alert(err?.message || "Erreur Google Drive");
    }
  };

  const handleDriveAdvInject = async () => {
    try {
      const files = await pickAndDownloadDriveFiles();
      if (!files.length) return;
      setAdvInjecting(true);
      setAdvReport(null);
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      const { data } = await api.post("/adv/bulk-classify", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAdvReport(data);
      await fetchDocs();
    } catch (err: any) {
      setAdvReport({ error: err?.response?.data?.detail || err?.message || "Erreur injection ADV via Drive" });
    } finally {
      setAdvInjecting(false);
    }
  };

  const driveEnabled = isGoogleDriveEnabled();

  const ADV_SECTION_LABELS: Record<string, string> = {
    clients: "Clients", contracts: "Contrats", receivables: "Créances",
    payments: "Paiements", capital: "Capital", retraits: "Retraits",
    bulletins: "Bulletins de Paie", declarations: "Déclarations",
    comptes: "Comptes Bancaires", journaux: "Journaux", echeancier: "Échéancier",
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm text-slate-500">
            {documents.length} document{documents.length !== 1 && "s"} ing&eacute;r&eacute;{documents.length !== 1 && "s"}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap justify-end">
          <label className={`btn-secondary cursor-pointer flex items-center gap-1.5 text-sm ${advInjecting ? "opacity-50 pointer-events-none" : ""}`}>
            <CloudArrowUpIcon className="h-4 w-4" />
            {advInjecting ? "Injection ADV…" : "Injecter dans ADV"}
            <input ref={advFileRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tiff" className="hidden" onChange={handleAdvBulkInject} />
          </label>
          {driveEnabled && (
            <button onClick={handleDriveAdvInject} disabled={advInjecting}
              className={`btn-secondary flex items-center gap-1.5 text-sm ${advInjecting ? "opacity-50 pointer-events-none" : ""}`}>
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M7.71 3.5L1.15 15l3.44 5.98h6.56l-3.44-5.98L7.71 3.5zm1.15 0l6.56 11.5H22l-6.56-11.5H8.86zm6.73 12.5L12.15 22h12.7l3.44-5.98H15.59z" transform="scale(0.85) translate(1,1)"/></svg>
              Drive → ADV
            </button>
          )}
          {driveEnabled && (
            <button onClick={handleDriveImport} disabled={uploading}
              className={`btn-primary flex items-center gap-1.5 text-sm ${uploading ? "opacity-50 pointer-events-none" : ""}`}>
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M7.71 3.5L1.15 15l3.44 5.98h6.56l-3.44-5.98L7.71 3.5zm1.15 0l6.56 11.5H22l-6.56-11.5H8.86zm6.73 12.5L12.15 22h12.7l3.44-5.98H15.59z" transform="scale(0.85) translate(1,1)"/></svg>
              Importer depuis Drive
            </button>
          )}
          <label className={`btn-primary cursor-pointer flex items-center gap-1.5 text-sm ${uploading ? "opacity-50 pointer-events-none" : ""}`}>
            <ArrowUpTrayIcon className="h-4 w-4" />
            {uploading ? "Import en masse…" : "Importer des documents"}
            <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tiff" className="hidden" onChange={handleUpload} />
          </label>
        </div>
      </div>

      <div
        className={`mb-6 rounded-2xl border-2 border-dashed p-6 transition-colors ${
          dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white"
        } ${uploading ? "opacity-70" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files?.length) {
            setRfPendingFiles(Array.from(e.dataTransfer.files));
            setRfSelection("RF1");
            setRfModal(true);
          }
        }}
      >
        <div className="flex items-start gap-4">
          <DocumentDuplicateIcon className="h-10 w-10 text-teal-600 shrink-0" />
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-900">Import en masse des documents</h2>
            <p className="mt-1 text-sm text-slate-500">
              Déposez plusieurs PDF ou images ici, ou utilisez les boutons d'import. Chaque fichier sera classifié, traité et routé automatiquement.
              {driveEnabled && " Vous pouvez aussi importer directement depuis Google Drive."}
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Formats acceptés: PDF, PNG, JPG, JPEG, TIFF.{driveEnabled && " | Google Drive activé"}
            </p>
          </div>
        </div>
      </div>

      {uploadReport && (
        <div className="card p-5 mb-6 space-y-4 border border-teal-200">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Resultat de l'import en masse</h2>
            <button onClick={() => setUploadReport(null)} className="text-sm text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-2xl font-bold text-slate-800">{uploadReport.total_files ?? 0}</p>
              <p className="text-xs text-slate-500">Fichiers</p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-3 text-center">
              <p className="text-2xl font-bold text-emerald-700">{uploadReport.uploaded_count ?? 0}</p>
              <p className="text-xs text-emerald-600">Importés</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-3 text-center">
              <p className="text-2xl font-bold text-amber-700">{uploadReport.duplicate_count ?? 0}</p>
              <p className="text-xs text-amber-600">Doublons</p>
            </div>
            <div className="rounded-lg bg-red-50 p-3 text-center">
              <p className="text-2xl font-bold text-red-700">{uploadReport.failed_count ?? 0}</p>
              <p className="text-xs text-red-600">Échecs</p>
            </div>
            <div className="rounded-lg bg-teal-50 p-3 text-center">
              <p className="text-2xl font-bold text-teal-700">{uploadReport.processed_count ?? 0}</p>
              <p className="text-xs text-teal-600">Traites</p>
            </div>
          </div>

          {uploadReport.module_counts && Object.keys(uploadReport.module_counts).length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-xs font-semibold text-slate-700">Routage par module</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(uploadReport.module_counts).map(([moduleName, count]) => (
                  <a
                    key={moduleName}
                    href={MODULE_PATHS[moduleName] ?? "/documents"}
                    className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
                  >
                    <span>{getModuleLabel(moduleName)}</span>
                    <span className="rounded-full bg-teal-50 px-2 py-0.5 text-teal-700">{String(count)}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(uploadReport.items) && uploadReport.items.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Fichier</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">Traitement</th>
                    <th className="px-3 py-2">Module</th>
                    <th className="px-3 py-2">Enregistrements crees</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(uploadReport.items as UploadItem[]).map((item) => {
                    const statusLabel = item.processing_status || item.upload_status || (item.is_duplicate ? "DUPLICATE" : "INGESTED");
                    const moduleName = item.routed_to || item.module_routed_to || "documents";
                    const processColor = PROCESSING_STATUS_COLORS[statusLabel] || "text-slate-700 bg-slate-50 border-slate-200";
                    const createdCount = (item.created_record_ids?.length ?? 0) + (item.journal_entry_ids?.length ?? 0);

                    return (
                      <tr key={`${item.id}-${item.filename}`} className="align-top">
                        <td className="px-3 py-3 font-medium text-slate-900">{item.filename}</td>
                        <td className="px-3 py-3 text-slate-600">{item.doc_type ? (DOC_TYPE_LABELS[item.doc_type] ?? item.doc_type) : "—"}</td>
                        <td className="px-3 py-3">
                          <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${processColor}`}>
                            {PROCESSING_STATUS_LABELS[statusLabel] || statusLabel}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <a href={MODULE_PATHS[moduleName] ?? "/documents"} className="text-sm font-medium text-teal-700 hover:text-teal-800 hover:underline">
                            {getModuleLabel(moduleName)}
                          </a>
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {createdCount > 0 ? (
                            <div className="space-y-1 text-xs">
                              {item.journal_entry_ids && item.journal_entry_ids.length > 0 && (
                                <div>{item.journal_entry_ids.length} ecriture(s) comptables</div>
                              )}
                              {item.created_record_ids && item.created_record_ids.length > 0 && (
                                <div>{item.created_record_ids.length} fiche(s) module</div>
                              )}
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {uploadReport.failures?.length > 0 && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="mb-2 text-xs font-semibold text-red-700">Fichiers en erreur</p>
              <ul className="space-y-1 text-xs text-red-600 max-h-32 overflow-y-auto">
                {uploadReport.failures.map((failure: any, index: number) => (
                  <li key={`${failure.filename}-${index}`}>
                    <span className="font-medium">{failure.filename}</span>: {failure.detail}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ADV Injection Report */}
      {advReport && !advReport.error && (
        <div className="card p-5 mb-6 space-y-4 border border-teal-200">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <CloudArrowUpIcon className="h-4 w-4 text-teal-600" />
              Résultat injection ADV — Classification IA
            </h2>
            <button onClick={() => setAdvReport(null)} className="text-sm text-slate-400 hover:text-slate-600">&times;</button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-2xl font-bold text-slate-800">{advReport.total_files ?? 0}</p>
              <p className="text-xs text-slate-500">Fichiers</p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-3 text-center">
              <p className="text-2xl font-bold text-emerald-700">{advReport.classified_count ?? 0}</p>
              <p className="text-xs text-emerald-600">Classifiés IA</p>
            </div>
            {(advReport.failed_count ?? 0) > 0 && (
              <div className="rounded-lg bg-red-50 p-3 text-center">
                <p className="text-2xl font-bold text-red-700">{advReport.failed_count}</p>
                <p className="text-xs text-red-600">Échecs</p>
              </div>
            )}
          </div>

          {advReport.section_counts && Object.keys(advReport.section_counts).length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-xs font-semibold text-slate-700">Documents classés par section ADV</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(advReport.section_counts).map(([section, count]) => (
                  <button
                    key={section}
                    onClick={() => navigate("/adv")}
                    className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-400 hover:text-teal-700"
                  >
                    <span>{ADV_SECTION_LABELS[section] || section}</span>
                    <span className="rounded-full bg-teal-50 px-2 py-0.5 text-teal-700">{String(count)}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(advReport.items) && advReport.items.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Fichier</th>
                    <th className="px-3 py-2">Type IA</th>
                    <th className="px-3 py-2">Section ADV</th>
                    <th className="px-3 py-2">Date doc.</th>
                    <th className="px-3 py-2 text-right">Montant</th>
                    <th className="px-3 py-2 text-right">Confiance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {advReport.items.map((item: any) => (
                    <tr key={item.document_id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium text-slate-900 max-w-48 truncate">{item.filename}</td>
                      <td className="px-3 py-2 text-slate-600">{item.document_type}</td>
                      <td className="px-3 py-2 font-medium text-teal-700">{ADV_SECTION_LABELS[item.adv_section] || item.adv_section}</td>
                      <td className="px-3 py-2 text-slate-600">{item.document_date ? new Date(item.document_date).toLocaleDateString("fr-FR") : "—"}</td>
                      <td className="px-3 py-2 text-right font-mono">{item.amount != null ? new Intl.NumberFormat("fr-DZ", { style: "decimal", minimumFractionDigits: 2 }).format(item.amount) + " DA" : "—"}</td>
                      <td className="px-3 py-2 text-right">{Math.round((item.confidence ?? 0) * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <button onClick={() => navigate("/adv")} className="btn-primary text-sm w-full">
            Voir dans ADV & Trésorerie
          </button>
        </div>
      )}
      {advReport?.error && (
        <div className="card p-4 mb-6 border border-red-200 bg-red-50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-red-700">{advReport.error}</p>
            <button onClick={() => setAdvReport(null)} className="text-sm text-red-400 hover:text-red-600">&times;</button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher par nom ou type…"
            className="input-field pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={filterEntreprise}
          onChange={(e) => setFilterEntreprise(e.target.value)}
          className="input-field w-auto min-w-[180px] text-sm"
        >
          <option value="">Toutes les entit&eacute;s</option>
          {entreprises.map((ent) => (
            <option key={ent.id} value={ent.id}>{ent.code} — {ent.raison_sociale}</option>
          ))}
        </select>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="input-field w-auto min-w-[140px] text-sm"
        >
          <option value="">Tous les types</option>
          {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={filterRF}
          onChange={(e) => setFilterRF(e.target.value)}
          className="input-field w-auto min-w-[130px] text-sm"
        >
          <option value="">Toutes RF</option>
          {Object.entries(RF_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        {(filterEntreprise || filterType || filterRF) && (
          <button
            onClick={() => { setFilterEntreprise(""); setFilterType(""); setFilterRF(""); }}
            className="text-xs text-slate-500 hover:text-red-600 flex items-center gap-1"
          >
            <XMarkIcon className="h-3.5 w-3.5" />
            Effacer filtres
          </button>
        )}
      </div>

      <div className="flex gap-6">
        {/* Documents table */}
        <div className="flex-1">
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Nom</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Type</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Taille</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                      Chargement…
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                      <DocumentTextIcon className="mx-auto h-10 w-10 mb-2" />
                      Aucun document trouvé
                    </td>
                  </tr>
                ) : (
                  filtered.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <DocThumbnail doc={doc} />
                          <div className="min-w-0">
                            <p className="font-medium text-slate-900 truncate max-w-[160px]">{doc.filename}</p>
                            {doc.realite_financiere && (
                              <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium mt-0.5 ${RF_COLORS[doc.realite_financiere] ?? "bg-slate-100 text-slate-600"}`}>
                                {RF_LABELS[doc.realite_financiere] ?? doc.realite_financiere}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {doc.doc_type && doc.doc_type !== "OTHER" ? (
                          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${DOC_TYPE_COLORS[doc.doc_type] ?? DOC_TYPE_COLORS.OTHER}`}>
                            {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                          </span>
                        ) : (
                          <span className="badge-neutral">—</span>
                        )}
                        {doc.module_routed_to && doc.module_routed_to !== "documents" && (
                          <a
                            href={MODULE_PATHS[doc.module_routed_to] ?? "/documents"}
                            className="mt-1 block text-xs font-medium text-teal-700 hover:text-teal-800 hover:underline"
                          >
                            Route vers {getModuleLabel(doc.module_routed_to)}
                          </a>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-slate-700">
                        {doc.extracted_montant ? (
                          <span className="flex items-center justify-end gap-1">
                            <BanknotesIcon className="h-3.5 w-3.5 text-emerald-500" />
                            {formatMontant(doc.extracted_montant)}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{formatBytes(doc.file_size)}</td>
                      <td className="px-4 py-3 text-slate-600">
                        {new Date(doc.created_at).toLocaleDateString("fr-FR")}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => handleView(doc)} className="rounded p-1 text-slate-400 hover:text-teal-600" title="Voir détails">
                          <EyeIcon className="h-4 w-4" />
                        </button>
                        <button onClick={() => handleOpenDocument(doc)} className="rounded p-1 text-slate-400 hover:text-indigo-600 ml-1" title="Ouvrir le fichier">
                          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                        </button>
                        <button onClick={() => openCorrection(doc)} className="rounded p-1 text-slate-400 hover:text-amber-600 ml-1" title="Corriger">
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleProcess(doc)}
                          disabled={processing === doc.id}
                          className={`rounded p-1 ml-1 ${processing === doc.id ? "text-amber-500 animate-pulse" : "text-slate-400 hover:text-emerald-600"}`}
                          title="Traiter avec IA"
                        >
                          <CpuChipIcon className="h-4 w-4" />
                        </button>
                        <button onClick={() => handleDelete(doc.id)} className="rounded p-1 text-slate-400 hover:text-red-600 ml-1" title="Supprimer">
                          <TrashIcon className="h-4 w-4" />
                        </button>
                        {doc.statut_ingestion === "A_COMPLETER" && (
                          <button onClick={() => setCompletingDoc(doc)} className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 hover:bg-amber-200 ml-1" title="Compl&eacute;ter les champs manquants">
                            Compl&eacute;ter
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail panel */}
        {selectedDoc && (
          <div className="w-96 shrink-0 card p-5 space-y-4 self-start">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 truncate">{selectedDoc.filename}</h2>
              <div className="flex items-center gap-1">
                <button onClick={() => handleOpenDocument(selectedDoc)} className="rounded p-1 text-slate-400 hover:text-indigo-600" title="Ouvrir le fichier">
                  <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                </button>
                <button onClick={() => openCorrection(selectedDoc)} className="rounded p-1 text-slate-400 hover:text-amber-600" title="Corriger">
                  <PencilIcon className="h-4 w-4" />
                </button>
                <button onClick={() => setSelectedDoc(null)} className="text-sm text-slate-400 hover:text-slate-600 ml-1">
                  ✕
                </button>
              </div>
            </div>
            {/* Document preview — click to open full viewer */}
            <div
              className="w-full h-48 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-center cursor-pointer hover:bg-slate-100 hover:border-teal-300 transition-all group relative overflow-hidden"
              onClick={() => handleOpenDocument(selectedDoc)}
            >
              {selectedDoc.mime_type?.startsWith("image/") ? (
                <>
                  <img
                    src={docDownloadUrl(selectedDoc.id)}
                    alt={selectedDoc.filename}
                    className="w-full h-full object-contain"
                  />
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                    <span className="opacity-0 group-hover:opacity-100 text-white text-sm font-medium bg-black/60 px-3 py-1.5 rounded-lg transition-opacity flex items-center gap-1.5">
                      <MagnifyingGlassPlusIcon className="h-4 w-4" />
                      Agrandir
                    </span>
                  </div>
                </>
              ) : selectedDoc.mime_type === "application/pdf" ? (
                <div className="text-center">
                  <div className="h-16 w-16 mx-auto rounded-xl bg-red-100 group-hover:bg-red-200 flex items-center justify-center mb-2 transition-colors">
                    <span className="text-2xl font-bold text-red-500">PDF</span>
                  </div>
                  <p className="text-xs text-slate-500 group-hover:text-teal-600 transition-colors flex items-center gap-1 justify-center">
                    <MagnifyingGlassPlusIcon className="h-3.5 w-3.5" />
                    Cliquer pour visualiser
                  </p>
                </div>
              ) : (
                <div className="text-center">
                  <DocumentTextIcon className="h-12 w-12 mx-auto text-slate-300 mb-2" />
                  <p className="text-xs text-slate-400">Cliquer pour ouvrir</p>
                </div>
              )}
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Type</dt>
                <dd className="font-medium">
                  {selectedDoc.doc_type ? (
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DOC_TYPE_COLORS[selectedDoc.doc_type] ?? DOC_TYPE_COLORS.OTHER}`}>
                      {DOC_TYPE_LABELS[selectedDoc.doc_type] ?? selectedDoc.doc_type}
                    </span>
                  ) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Confiance</dt>
                <dd className="font-medium">{selectedDoc.doc_type_confidence != null ? `${(selectedDoc.doc_type_confidence * 100).toFixed(0)}%` : "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Module cible</dt>
                <dd className="font-medium">
                  {selectedDoc.module_routed_to ? (
                    <a href={MODULE_PATHS[selectedDoc.module_routed_to] ?? "/documents"} className="text-teal-700 hover:text-teal-800 hover:underline">
                      {getModuleLabel(selectedDoc.module_routed_to)}
                    </a>
                  ) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Realite Fin.</dt>
                <dd className="font-medium">
                  {selectedDoc.realite_financiere ? (
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${RF_COLORS[selectedDoc.realite_financiere] ?? "bg-slate-100 text-slate-600"}`}>
                      {RF_LABELS[selectedDoc.realite_financiere] ?? selectedDoc.realite_financiere}
                    </span>
                  ) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Taille</dt>
                <dd className="font-medium">{formatBytes(selectedDoc.file_size)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Créé le</dt>
                <dd className="font-medium">{new Date(selectedDoc.created_at).toLocaleString("fr-FR")}</dd>
              </div>
            </dl>

            {/* AI Extraction Results */}
            {(selectedDoc.extracted_montant || selectedDoc.extracted_reference || selectedDoc.extracted_emetteur) && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 space-y-2">
                <h3 className="text-sm font-semibold text-emerald-800 flex items-center gap-1.5">
                  <BanknotesIcon className="h-4 w-4" />
                  Données extraites par l'IA
                </h3>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  {selectedDoc.extracted_montant != null && (
                    <div className="col-span-2">
                      <dt className="text-emerald-600 text-xs">Montant TTC</dt>
                      <dd className="font-bold text-lg text-emerald-800">{formatMontant(selectedDoc.extracted_montant)}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_montant_ht != null && (
                    <div>
                      <dt className="text-emerald-600 text-xs">Montant HT</dt>
                      <dd className="font-medium text-emerald-800">{formatMontant(selectedDoc.extracted_montant_ht)}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_tva != null && (
                    <div>
                      <dt className="text-emerald-600 text-xs">TVA</dt>
                      <dd className="font-medium text-emerald-800">{formatMontant(selectedDoc.extracted_tva)}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_reference && (
                    <div>
                      <dt className="text-emerald-600 text-xs">Référence</dt>
                      <dd className="font-medium text-slate-800">{selectedDoc.extracted_reference}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_date && (
                    <div>
                      <dt className="text-emerald-600 text-xs">Date document</dt>
                      <dd className="font-medium text-slate-800">{selectedDoc.extracted_date}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_emetteur && (
                    <div className="col-span-2">
                      <dt className="text-emerald-600 text-xs">Émetteur</dt>
                      <dd className="font-medium text-slate-800">{selectedDoc.extracted_emetteur}</dd>
                    </div>
                  )}
                  {selectedDoc.extracted_destinataire && (
                    <div className="col-span-2">
                      <dt className="text-emerald-600 text-xs">Destinataire</dt>
                      <dd className="font-medium text-slate-800">{selectedDoc.extracted_destinataire}</dd>
                    </div>
                  )}
                </dl>
                {selectedDoc.classification_reasoning && (
                  <p className="text-xs text-emerald-600 italic mt-1">{selectedDoc.classification_reasoning}</p>
                )}
              </div>
            )}

            {/* Artifacts */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">
                Artefacts ({artifacts.length})
              </h3>
              {artifacts.length === 0 ? (
                <p className="text-xs text-slate-400">Aucun artefact</p>
              ) : (
                <ul className="space-y-1.5 max-h-60 overflow-y-auto">
                  {artifacts.map((a: any) => (
                    <li key={a.id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                      <span className="badge-info">{a.artifact_type}</span>
                      <span className="text-slate-500 truncate flex-1">{a.key ?? ""}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Process button */}
            <button
              onClick={() => handleProcess(selectedDoc)}
              disabled={processing === selectedDoc.id}
              className={`w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                processing === selectedDoc.id
                  ? "bg-amber-50 text-amber-700 border border-amber-200 cursor-wait"
                  : "bg-emerald-600 text-white hover:bg-emerald-700"
              }`}
            >
              <CpuChipIcon className="h-4 w-4" />
              {processing === selectedDoc.id ? "Traitement IA en cours…" : "Traiter avec l'IA"}
            </button>

            {/* AI Processing Result */}
            {processResult && (
              <div className={`rounded-lg border p-4 text-sm ${
                processResult.status === "error"
                  ? "border-red-200 bg-red-50"
                  : "border-emerald-200 bg-emerald-50"
              }`}>
                <h3 className={`font-semibold mb-2 ${
                  processResult.status === "error" ? "text-red-700" : "text-emerald-700"
                }`}>
                  {processResult.status === "error" ? "Erreur" : "Résultat du traitement IA"}
                </h3>
                {processResult.status === "error" ? (
                  <p className="text-red-600 text-xs">{processResult.error}</p>
                ) : (
                  <div className="space-y-2">
                    {processResult.doc_type && (
                      <div>
                        <span className="text-slate-500">Type détecté : </span>
                        <span className="font-medium text-slate-800">
                          {DOC_TYPE_LABELS[processResult.doc_type] ?? processResult.doc_type}
                        </span>
                      </div>
                    )}
                    {processResult.routed_to && (
                      <div>
                        <span className="text-slate-500">Routé vers : </span>
                        <a href={MODULE_PATHS[processResult.routed_to] ?? "/documents"} className="font-medium text-teal-700 hover:text-teal-800 hover:underline">
                          {getModuleLabel(processResult.routed_to)}
                        </a>
                      </div>
                    )}
                    {processResult.workflow_status && (
                      <div>
                        <span className="text-slate-500">Statut : </span>
                        <span className={`font-medium ${
                          processResult.workflow_status === "completed" ? "text-emerald-700" : "text-amber-700"
                        }`}>
                          {processResult.workflow_status}
                        </span>
                      </div>
                    )}
                    {(processResult.created_record_ids?.length > 0 || processResult.journal_entry_ids?.length > 0) && (
                      <div>
                        <span className="text-slate-500 block mb-1">Enregistrements créés :</span>
                        <div className="space-y-1 text-xs text-slate-700">
                          {processResult.journal_entry_ids?.length > 0 && (
                            <div>{processResult.journal_entry_ids.length} ecriture(s) comptables generee(s)</div>
                          )}
                          {processResult.created_record_ids?.length > 0 && (
                            <div>{processResult.created_record_ids.length} fiche(s) metier generee(s)</div>
                          )}
                        </div>
                      </div>
                    )}
                    {processResult.artifacts && processResult.artifacts.length > 0 && (
                      <div>
                        <span className="text-slate-500 block mb-1">
                          {processResult.artifacts.length} artefact(s) produit(s) :
                        </span>
                        <ul className="space-y-1">
                          {processResult.artifacts.map((a: any, i: number) => (
                            <li key={i} className="flex items-center gap-2 text-xs">
                              <span className="badge-info">{a.artifact_type}</span>
                              <span className="text-slate-600 truncate">{a.key ?? ""}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {processResult.extracted_data && Object.keys(processResult.extracted_data).length > 0 && (
                      <div>
                        <span className="text-slate-500 block mb-1">Données extraites :</span>
                        <pre className="bg-white rounded border border-emerald-100 p-2 text-xs overflow-auto max-h-48 text-slate-700">
                          {JSON.stringify(processResult.extracted_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* RF Classification Modal */}
      {rfModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-5 border-b border-slate-200">
              <h2 className="text-lg font-semibold text-slate-900">Classification du document</h2>
              <button onClick={() => { setRfModal(false); setRfPendingFiles([]); }} className="text-slate-400 hover:text-slate-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-slate-500">
                {rfPendingFiles.length} fichier{rfPendingFiles.length > 1 ? "s" : ""} a importer.
                Choisissez la realite financiere :
              </p>
              {/* File previews */}
              <div className="flex flex-wrap gap-2 max-h-24 overflow-y-auto">
                {rfPendingFiles.slice(0, 6).map((f, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600">
                    {f.type.startsWith("image/") ? (
                      <img src={URL.createObjectURL(f)} alt="" className="h-8 w-8 rounded object-cover" />
                    ) : (
                      <DocumentTextIcon className="h-6 w-6 text-red-400 shrink-0" />
                    )}
                    <span className="truncate max-w-[100px]">{f.name}</span>
                  </div>
                ))}
                {rfPendingFiles.length > 6 && (
                  <span className="text-xs text-slate-400 self-center">+{rfPendingFiles.length - 6} autres</span>
                )}
              </div>
              {/* RF selection */}
              <div className="space-y-2">
                {RF_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-start gap-3 rounded-lg border-2 p-3 cursor-pointer transition-colors ${
                      rfSelection === opt.value ? opt.color + " border-current" : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="radio"
                      name="rf"
                      value={opt.value}
                      checked={rfSelection === opt.value}
                      onChange={() => setRfSelection(opt.value)}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-semibold">{opt.label}</p>
                      <p className="text-xs opacity-75">{opt.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 p-5 border-t border-slate-200">
              <button
                onClick={() => { setRfModal(false); setRfPendingFiles([]); }}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleRfConfirm}
                disabled={uploading}
                className="rounded-lg px-4 py-2 text-sm font-medium bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <ArrowUpTrayIcon className="h-4 w-4" />
                {uploading ? "Import en cours..." : "Importer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Correction Modal */}
      {correcting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-slate-200">
              <h2 className="text-lg font-semibold text-slate-900">Corriger le document</h2>
              <button onClick={() => setCorrecting(null)} className="text-slate-400 hover:text-slate-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-slate-500 truncate">{correcting.filename}</p>

              {/* Doc Type */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Type de document</label>
                <select
                  value={correctionForm.doc_type || ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, doc_type: e.target.value })}
                  className="input w-full"
                >
                  {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>

              {/* Montant TTC */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Montant TTC (DA)</label>
                <input
                  type="number"
                  step="0.01"
                  value={correctionForm.extracted_montant ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_montant: e.target.value })}
                  className="input w-full"
                  placeholder="0.00"
                />
              </div>

              {/* Montant HT */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Montant HT (DA)</label>
                <input
                  type="number"
                  step="0.01"
                  value={correctionForm.extracted_montant_ht ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_montant_ht: e.target.value })}
                  className="input w-full"
                  placeholder="0.00"
                />
              </div>

              {/* TVA */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">TVA (DA)</label>
                <input
                  type="number"
                  step="0.01"
                  value={correctionForm.extracted_tva ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_tva: e.target.value })}
                  className="input w-full"
                  placeholder="0.00"
                />
              </div>

              {/* Date */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Date du document</label>
                <input
                  type="text"
                  value={correctionForm.extracted_date ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_date: e.target.value })}
                  className="input w-full"
                  placeholder="ex: 2025-01-15"
                />
              </div>

              {/* Référence */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Référence</label>
                <input
                  type="text"
                  value={correctionForm.extracted_reference ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_reference: e.target.value })}
                  className="input w-full"
                  placeholder="N° facture, bon, etc."
                />
              </div>

              {/* Émetteur */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Émetteur</label>
                <input
                  type="text"
                  value={correctionForm.extracted_emetteur ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_emetteur: e.target.value })}
                  className="input w-full"
                  placeholder="Nom de l'émetteur"
                />
              </div>

              {/* Destinataire */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Destinataire</label>
                <input
                  type="text"
                  value={correctionForm.extracted_destinataire ?? ""}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, extracted_destinataire: e.target.value })}
                  className="input w-full"
                  placeholder="Nom du destinataire"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 p-5 border-t border-slate-200">
              <button
                onClick={() => setCorrecting(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleSaveCorrection}
                disabled={savingCorrection}
                className="rounded-lg px-4 py-2 text-sm font-medium bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <CheckIcon className="h-4 w-4" />
                {savingCorrection ? "Enregistrement…" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Full-screen Document Viewer ── */}
      {viewerDoc && (
        <DocumentViewer
          docId={viewerDoc.id}
          filename={viewerDoc.filename}
          mimeType={viewerDoc.mime_type}
          onClose={() => setViewerDoc(null)}
        />
      )}

      {/* ── Completion Modal (EX-ING-002) ── */}
      {completingDoc && (
        <CompletionModal
          doc={completingDoc}
          onClose={() => setCompletingDoc(null)}
          onCompleted={() => { setCompletingDoc(null); fetchDocs(); }}
        />
      )}
    </div>
  );
}


/* ── Completion Modal — fill missing fields with doc preview ── */
function CompletionModal({ doc, onClose, onCompleted }: { doc: Document; onClose: () => void; onCompleted: () => void }) {
  const [form, setForm] = useState({
    doc_type: doc.doc_type || "",
    extracted_montant: doc.extracted_montant != null ? String(doc.extracted_montant) : "",
    extracted_montant_ht: doc.extracted_montant_ht != null ? String(doc.extracted_montant_ht) : "",
    extracted_tva: doc.extracted_tva != null ? String(doc.extracted_tva) : "",
    extracted_date: doc.extracted_date || "",
    extracted_reference: doc.extracted_reference || "",
    extracted_emetteur: doc.extracted_emetteur || "",
    extracted_destinataire: doc.extracted_destinataire || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const missing = doc.champs_manquants || [];

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, any> = {};
      if (form.doc_type) payload.doc_type = form.doc_type;
      if (form.extracted_montant) payload.extracted_montant = parseFloat(form.extracted_montant);
      if (form.extracted_montant_ht) payload.extracted_montant_ht = parseFloat(form.extracted_montant_ht);
      if (form.extracted_tva) payload.extracted_tva = parseFloat(form.extracted_tva);
      if (form.extracted_date) payload.extracted_date = form.extracted_date;
      if (form.extracted_reference) payload.extracted_reference = form.extracted_reference;
      if (form.extracted_emetteur) payload.extracted_emetteur = form.extracted_emetteur;
      if (form.extracted_destinataire) payload.extracted_destinataire = form.extracted_destinataire;
      await api.post(`/documents/${doc.id}/complete`, payload);
      onCompleted();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Erreur");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-sm">
      {/* Left: Document preview */}
      <div className="w-1/2 h-full bg-slate-900 flex items-center justify-center p-4">
        {doc.mime_type?.startsWith("image/") ? (
          <img src={docDownloadUrl(doc.id)} alt={doc.filename}
            className="max-w-full max-h-full object-contain rounded-lg" />
        ) : doc.mime_type === "application/pdf" ? (
          <iframe src={docDownloadUrl(doc.id)} title={doc.filename}
            className="w-full h-full rounded-lg border-0" />
        ) : (
          <div className="text-white text-center">
            <p className="text-lg mb-2">{doc.filename}</p>
            <p className="text-sm text-slate-400">Aper&ccedil;u non disponible</p>
          </div>
        )}
      </div>

      {/* Right: Completion form */}
      <div className="w-1/2 h-full bg-white overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Compl&eacute;ter le document</h2>
            <p className="text-sm text-slate-500">{doc.filename}</p>
            {missing.length > 0 && (
              <div className="flex gap-1 mt-2">
                {missing.map((m: string) => (
                  <span key={m} className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">{m}</span>
                ))}
              </div>
            )}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-2xl">&times;</button>
        </div>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type de document</label>
            <select className="input-field" value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
              <option value="">S&eacute;lectionner</option>
              <option value="INVOICE">Facture</option>
              <option value="RECEIPT">Re&ccedil;u</option>
              <option value="CHEQUE">Ch&egrave;que</option>
              <option value="CONTRACT">Contrat</option>
              <option value="ADV_CONTRACT">Acte de vente</option>
              <option value="ADV_PAYMENT">Paiement ADV</option>
              <option value="BANK_STATEMENT">Relev&eacute; bancaire</option>
              <option value="BON_COMMANDE">Bon de commande</option>
              <option value="BULLETIN_PAIE">Bulletin de paie</option>
              <option value="DEVIS">Devis</option>
              <option value="OTHER">Autre</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className={missing.includes("montant") ? "ring-2 ring-amber-300 rounded-lg p-2" : ""}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Montant TTC (DA) {missing.includes("montant") && <span className="text-amber-600">*</span>}
              </label>
              <input type="number" step="0.01" className="input-field" value={form.extracted_montant}
                onChange={(e) => setForm({ ...form, extracted_montant: e.target.value })} placeholder="0.00" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Montant HT (DA)</label>
              <input type="number" step="0.01" className="input-field" value={form.extracted_montant_ht}
                onChange={(e) => setForm({ ...form, extracted_montant_ht: e.target.value })} placeholder="0.00" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">TVA (DA)</label>
              <input type="number" step="0.01" className="input-field" value={form.extracted_tva}
                onChange={(e) => setForm({ ...form, extracted_tva: e.target.value })} placeholder="0.00" />
            </div>
            <div className={missing.includes("date") ? "ring-2 ring-amber-300 rounded-lg p-2" : ""}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Date du document {missing.includes("date") && <span className="text-amber-600">*</span>}
              </label>
              <input type="date" className="input-field" value={form.extracted_date}
                onChange={(e) => setForm({ ...form, extracted_date: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">R&eacute;f&eacute;rence</label>
            <input className="input-field" value={form.extracted_reference}
              onChange={(e) => setForm({ ...form, extracted_reference: e.target.value })} placeholder="N\u00b0 facture, ch\u00e8que..." />
          </div>

          <div className={missing.includes("emetteur") ? "ring-2 ring-amber-300 rounded-lg p-2" : ""}>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              &Eacute;metteur {missing.includes("emetteur") && <span className="text-amber-600">*</span>}
            </label>
            <input className="input-field" value={form.extracted_emetteur}
              onChange={(e) => setForm({ ...form, extracted_emetteur: e.target.value })} placeholder="Nom du fournisseur / \u00e9metteur" />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Destinataire</label>
            <input className="input-field" value={form.extracted_destinataire}
              onChange={(e) => setForm({ ...form, extracted_destinataire: e.target.value })} placeholder="Nom du client / destinataire" />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <button onClick={onClose} className="btn-secondary text-sm">Annuler</button>
            <button onClick={handleSave} disabled={saving} className="btn-primary text-sm">
              {saving ? "Enregistrement\u2026" : "Compl\u00e9ter et router"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


/* ── Document Thumbnail ── */
function DocThumbnail({ doc }: { doc: Document }) {
  const isImage = doc.mime_type?.startsWith("image/");
  const isPdf = doc.mime_type === "application/pdf";

  if (isImage) {
    return (
      <img
        src={docDownloadUrl(doc.id)}
        alt={doc.filename}
        className="h-10 w-10 rounded-lg object-cover border border-slate-200 shrink-0"
        loading="lazy"
      />
    );
  }

  if (isPdf) {
    return (
      <div className="h-10 w-10 rounded-lg bg-red-50 border border-red-200 flex items-center justify-center shrink-0">
        <span className="text-[10px] font-bold text-red-500">PDF</span>
      </div>
    );
  }

  return (
    <div className="h-10 w-10 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
      <DocumentTextIcon className="h-5 w-5 text-slate-400" />
    </div>
  );
}
