import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";
import {
  PlusIcon,
  CheckIcon,
  XMarkIcon,
  LockClosedIcon,
  DocumentTextIcon,
  LinkIcon,
  TrashIcon,
  BanknotesIcon,
  EyeIcon,
  ArrowUpTrayIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";

/* ── Types ────────────────────────────────────────── */
interface COA {
  id: string;
  code: string;
  label: string;
  account_type: string;
}
interface Period {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
}
interface JournalEntry {
  id: string;
  entry_ref: string;
  entry_date: string;
  status: string;
  description: string | null;
  lines: any[];
  evidence_anchors: any[];
}

type Tab = "coa" | "periods" | "journal" | "declarations";

/* ── Status badges ─────────────────────────────────── */
const JE_STATUS: Record<string, { cls: string; label: string }> = {
  PROPOSED: { cls: "badge-info", label: "Proposé" },
  VALIDATED: { cls: "badge-success", label: "Validé" },
  COMMITTED: { cls: "badge-success", label: "Engagé" },
  REJECTED: { cls: "badge-danger", label: "Rejeté" },
};

const TAB_LABELS: Record<Tab, string> = {
  journal: "Écritures",
  coa: "Plan comptable SCF",
  periods: "Périodes",
  declarations: "Déclarations",
};

export default function AccountingPage() {
  const [tab, setTab] = useState<Tab>("journal");

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Comptabilit&eacute;</h1>
      <p className="text-sm text-slate-500 mb-6">Plan comptable SCF, p&eacute;riodes, &eacute;critures & d&eacute;clarations fiscales</p>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "coa" && <COASection />}
      {tab === "periods" && <PeriodsSection />}
      {tab === "journal" && <JournalSection />}
      {tab === "declarations" && <DeclarationsSection />}
    </div>
  );
}

/* ── COA Section ────── */
function COASection() {
  const [accounts, setAccounts] = useState<COA[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", label: "", account_type: "asset" });

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/accounting/coa");
      setAccounts(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/accounting/coa", form);
    setShowForm(false);
    setForm({ code: "", label: "", account_type: "asset" });
    fetch();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{accounts.length} comptes</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 flex items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Code</label>
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input-field w-32" required />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">Libellé</label>
            <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
            <select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })} className="input-field w-40">
              <option value="asset">Actif</option>
              <option value="liability">Passif</option>
              <option value="equity">Capitaux propres</option>
              <option value="revenue">Produit</option>
              <option value="expense">Charge</option>
            </select>
          </div>
          <button type="submit" className="btn-primary text-xs">Enregistrer</button>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Code</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Libellé</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : accounts.length === 0 ? (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Aucun compte</td></tr>
            ) : (
              accounts.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-sm">{a.code}</td>
                  <td className="px-4 py-3">{a.label}</td>
                  <td className="px-4 py-3 capitalize">{a.account_type}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Periods Section ── */
function PeriodsSection() {
  const [periods, setPeriods] = useState<Period[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "" });

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/accounting/periods");
      setPeriods(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setPeriods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/accounting/periods", form);
    setShowForm(false);
    setForm({ name: "", start_date: "", end_date: "" });
    fetch();
  };

  const handleClose = async (id: string) => {
    if (!confirm("Clôturer cette période ?")) return;
    await api.post(`/accounting/periods/${id}/close`);
    fetch();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{periods.length} périodes</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
          <PlusIcon className="h-4 w-4" /> Ajouter
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">Nom</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" required placeholder="Q1 2025" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Début</label>
            <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Fin</label>
            <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input-field" required />
          </div>
          <button type="submit" className="btn-primary text-xs">Créer</button>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Nom</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Début</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Fin</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : periods.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Aucune période</td></tr>
            ) : (
              periods.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3">{new Date(p.start_date).toLocaleDateString("fr-FR")}</td>
                  <td className="px-4 py-3">{new Date(p.end_date).toLocaleDateString("fr-FR")}</td>
                  <td className="px-4 py-3">
                    {p.is_closed ? <span className="badge-neutral">Clôturée</span> : <span className="badge-success">Ouverte</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!p.is_closed && (
                      <button onClick={() => handleClose(p.id)} className="btn-secondary text-xs px-2 py-1">
                        <LockClosedIcon className="h-3 w-3" /> Clôturer
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
  );
}

/* ── Journal Section ── */
interface DocOption { id: string; filename: string; doc_type: string | null; extracted_montant: number | null; }
interface JournalLineForm { account_code: string; label: string; debit: string; credit: string; }

const DOC_TYPE_LABELS: Record<string, string> = {
  INVOICE: "Facture", RECEIPT: "Reçu", CONTRACT: "Contrat", CHEQUE: "Chèque",
  BON_COMMANDE: "Bon de commande", DEVIS: "Devis", AVOIR: "Avoir",
  BULLETIN_PAIE: "Bulletin de paie", QUITTANCE: "Quittance",
  ATTESTATION: "Attestation", BON_LIVRAISON: "Bon de livraison",
  BANK_STATEMENT: "Relevé bancaire", PAYROLL: "Paie",
  ADV_CONTRACT: "Acte de vente", ADV_PAYMENT: "Paiement ADV", OTHER: "Autre",
};

function formatMontant(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("fr-DZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + " DA";
}

function JournalSection() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [availableDocs, setAvailableDocs] = useState<DocOption[]>([]);

  /* ── Create form state ── */
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [lines, setLines] = useState<JournalLineForm[]>([
    { account_code: "", label: "", debit: "", credit: "" },
    { account_code: "", label: "", debit: "", credit: "" },
  ]);
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);

  /* ── Upload state ── */
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [showUploadResult, setShowUploadResult] = useState(false);
  const [showUnmatched, setShowUnmatched] = useState(false);
  const [unmatchedData, setUnmatchedData] = useState<any>(null);
  const [rematching, setRematching] = useState(false);

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/accounting/journal-entries");
      const list = Array.isArray(data) ? data : (data?.items ?? []);
      setEntries(
        list.map((entry: any) => ({
          ...entry,
          entry_ref: entry.entry_ref ?? entry.reference ?? "—",
          evidence_anchors: entry.evidence_anchors ?? [],
        })),
      );
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDocs = useCallback(async () => {
    try {
      const { data } = await api.get("/documents/?page_size=100");
      const items = Array.isArray(data) ? data : (data?.items ?? []);
      setAvailableDocs(items.map((d: any) => ({
        id: d.id,
        filename: d.filename,
        doc_type: d.doc_type,
        extracted_montant: d.extracted_montant,
      })));
    } catch { setAvailableDocs([]); }
  }, []);

  useEffect(() => { fetchEntries(); fetchDocs(); }, [fetchEntries, fetchDocs]);

  const handleApprove = async (id: string) => {
    await api.post(`/accounting/journal-entries/${id}/approve`);
    fetchEntries();
  };
  const handleReject = async (id: string) => {
    await api.post(`/accounting/journal-entries/${id}/reject`);
    fetchEntries();
  };

  const toggleDocId = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  const updateLine = (i: number, field: keyof JournalLineForm, val: string) => {
    setLines((prev) => prev.map((l, idx) => idx === i ? { ...l, [field]: val } : l));
  };
  const addLine = () => setLines((p) => [...p, { account_code: "", label: "", debit: "", credit: "" }]);
  const removeLine = (i: number) => {
    if (lines.length <= 2) return;
    setLines((p) => p.filter((_, idx) => idx !== i));
  };

  const totalDebit = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
  const totalCredit = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01 && totalDebit > 0;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    if (!balanced) { setCreateError("L'écriture n'est pas équilibrée."); return; }
    if (lines.some((l) => !l.account_code)) { setCreateError("Chaque ligne doit avoir un code comptable."); return; }

    setCreating(true);
    try {
      await api.post("/accounting/journal-entries", {
        entry_date: entryDate,
        reference: reference || null,
        description: description || null,
        source_doc_ids: selectedDocIds,
        lines: lines.map((l) => ({
          account_code: l.account_code,
          label: l.label || null,
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
        })),
      });
      setShowCreate(false);
      setReference(""); setDescription(""); setSelectedDocIds([]);
      setLines([
        { account_code: "", label: "", debit: "", credit: "" },
        { account_code: "", label: "", debit: "", credit: "" },
      ]);
      fetchEntries();
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || "Erreur lors de la création");
    } finally {
      setCreating(false);
    }
  };

  /* ── Upload CSV/Excel handler ── */
  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/accounting/journal-entries/upload?auto_match=true", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadResult(data);
      setShowUploadResult(true);
      fetchEntries();
    } catch (err: any) {
      setUploadResult({ error: err.response?.data?.detail || "Erreur lors de l'import" });
      setShowUploadResult(true);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFetchUnmatched = async () => {
    try {
      const { data } = await api.get("/accounting/journal-entries/unmatched");
      setUnmatchedData(data);
      setShowUnmatched(true);
    } catch { /* ignore */ }
  };

  const handleRematch = async () => {
    setRematching(true);
    try {
      const { data } = await api.post("/accounting/journal-entries/rematch");
      setUploadResult({ ...data, rematch: true });
      setShowUploadResult(true);
      fetchEntries();
    } catch (err: any) {
      setUploadResult({ error: err.response?.data?.detail || "Erreur re-matching" });
      setShowUploadResult(true);
    } finally {
      setRematching(false);
    }
  };

  return (
    <div>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.txt,.xlsx,.xls"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleUpload(f);
        }}
      />

      {/* Header buttons */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{entries.length} &eacute;criture{entries.length !== 1 && "s"}</h2>
        <div className="flex items-center gap-2">
          <button onClick={handleFetchUnmatched} className="btn-secondary text-xs flex items-center gap-1" title="Écritures non justifiées">
            <ExclamationTriangleIcon className="h-4 w-4 text-amber-500" /> Non justifi&eacute;es
          </button>
          <button onClick={handleRematch} disabled={rematching} className="btn-secondary text-xs flex items-center gap-1" title="Re-rapprocher les écritures avec les documents">
            <ArrowPathIcon className={`h-4 w-4 ${rematching ? "animate-spin" : ""}`} /> {rematching ? "Rapprochement\u2026" : "Re-rapprocher"}
          </button>
          <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="btn-primary text-xs flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700">
            <ArrowUpTrayIcon className="h-4 w-4" /> {uploading ? "Import en cours\u2026" : "Importer CSV/Excel"}
          </button>
          <button onClick={() => setShowCreate(!showCreate)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouvelle &eacute;criture
          </button>
        </div>
      </div>

      {/* PDF Export bar */}
      <PDFExportBar />

      {/* ── Upload Results Panel ── */}
      {showUploadResult && uploadResult && (
        <div className="card p-5 mb-6 border-2 border-emerald-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-slate-800">
              {uploadResult.error ? "Erreur d'import" : uploadResult.rematch ? "Résultat du re-rapprochement" : "Résultat de l'import"}
            </h3>
            <button onClick={() => setShowUploadResult(false)} className="text-sm text-slate-400 hover:text-slate-600">✕</button>
          </div>

          {uploadResult.error ? (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">{uploadResult.error}</div>
          ) : (
            <>
              {/* Summary stats */}
              {!uploadResult.rematch && (
                <div className="grid grid-cols-4 gap-3">
                  <div className="rounded-lg bg-blue-50 p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700">{uploadResult.entries_created ?? 0}</p>
                    <p className="text-xs text-teal-600">Écritures créées</p>
                  </div>
                  <div className="rounded-lg bg-emerald-50 p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-700">{uploadResult.matching?.stats?.matched ?? 0}</p>
                    <p className="text-xs text-emerald-600">Rapprochées</p>
                  </div>
                  <div className="rounded-lg bg-amber-50 p-3 text-center">
                    <p className="text-2xl font-bold text-amber-700">{uploadResult.matching?.stats?.unmatched ?? 0}</p>
                    <p className="text-xs text-amber-600">Non justifiées</p>
                  </div>
                  <div className="rounded-lg bg-purple-50 p-3 text-center">
                    <p className="text-2xl font-bold text-purple-700">{uploadResult.cc_recalculated ?? 0}</p>
                    <p className="text-xs text-purple-600">Centres de coût</p>
                  </div>
                </div>
              )}

              {/* Parse errors */}
              {uploadResult.parse_errors?.length > 0 && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-3 space-y-1">
                  <p className="text-xs font-semibold text-red-700">Erreurs de parsing ({uploadResult.parse_errors.length})</p>
                  <ul className="list-disc list-inside text-xs text-red-600 max-h-24 overflow-y-auto">
                    {uploadResult.parse_errors.map((err: string, i: number) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Matches */}
              {(uploadResult.matching?.matches ?? uploadResult.matches)?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-emerald-700 mb-2">Rapprochements effectués</p>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {(uploadResult.matching?.matches ?? uploadResult.matches).map((m: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 rounded-lg bg-emerald-50 border border-emerald-200 p-2.5 text-xs">
                        <CheckIcon className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="font-medium text-slate-700">
                            Écriture → {m.matched_doc_ids?.length ?? 0} document(s)
                            <span className="ml-2 text-emerald-600">({Math.round((m.confidence ?? 0) * 100)}% confiance)</span>
                          </p>
                          {m.reasoning && <p className="text-slate-500 mt-0.5">{m.reasoning}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Unmatched entries */}
              {(uploadResult.matching?.unmatched_entries ?? uploadResult.unmatched_entries)?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-2">Écritures sans justificatif</p>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {(uploadResult.matching?.unmatched_entries ?? uploadResult.unmatched_entries).map((u: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-xs">
                        <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="font-medium text-slate-700">{u.reference || u.entry_ref || u.entry_id}</p>
                          {u.reason && <p className="text-slate-500 mt-0.5">{u.reason}</p>}
                          {u.description && <p className="text-slate-500 mt-0.5">{u.description}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Unmatched Entries Panel ── */}
      {showUnmatched && unmatchedData && (
        <div className="card p-5 mb-6 border-2 border-amber-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" />
              Écritures non justifiées ({unmatchedData.unmatched_count ?? 0} / {(unmatchedData.matched_count ?? 0) + (unmatchedData.unmatched_count ?? 0)})
            </h3>
            <div className="flex gap-2">
              <button onClick={handleRematch} disabled={rematching} className="btn-secondary text-xs flex items-center gap-1">
                <ArrowPathIcon className={`h-3.5 w-3.5 ${rematching ? "animate-spin" : ""}`} /> Re-rapprocher
              </button>
              <button onClick={() => setShowUnmatched(false)} className="text-sm text-slate-400 hover:text-slate-600">✕</button>
            </div>
          </div>
          {unmatchedData.unmatched_entries?.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {unmatchedData.unmatched_entries.map((u: any) => (
                <div key={u.id} className="flex items-center gap-3 rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs">
                  <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 shrink-0" />
                  <span className="font-mono font-medium">{u.entry_ref}</span>
                  <span className="text-slate-500">{u.entry_date ? new Date(u.entry_date).toLocaleDateString("fr-FR") : ""}</span>
                  <span className="flex-1 text-slate-600 truncate">{u.description || "—"}</span>
                  <span className="font-medium text-slate-700">{u.total_debit != null ? formatMontant(u.total_debit) : ""}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-emerald-600 text-center py-4">Toutes les écritures sont justifiées ✓</p>
          )}
        </div>
      )}

      {/* ── Create Form ── */}
      {showCreate && (
        <form onSubmit={handleCreate} className="card p-5 mb-6 space-y-4 border-2 border-blue-200">
          <h3 className="text-base font-semibold text-slate-800">Nouvelle écriture comptable</h3>

          {createError && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">{createError}</div>
          )}

          {/* Header fields */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Date</label>
              <input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Référence</label>
              <input value={reference} onChange={(e) => setReference(e.target.value)} className="input-field" placeholder="JV-2026-001" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} className="input-field" placeholder="Achat matériaux chantier…" />
            </div>
          </div>

          {/* ── Document justificatifs (cross-reference) ── */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-2">
              <LinkIcon className="inline h-3.5 w-3.5 mr-1" />
              Documents justificatifs
            </label>
            {availableDocs.length === 0 ? (
              <p className="text-xs text-slate-400">Aucun document disponible. Importez d'abord des fichiers depuis la page Documents.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto rounded-lg border border-slate-200 p-2 bg-slate-50">
                {availableDocs.map((doc) => (
                  <label
                    key={doc.id}
                    className={`flex items-center gap-2 rounded-lg p-2 cursor-pointer text-xs transition-colors ${
                      selectedDocIds.includes(doc.id)
                        ? "bg-blue-100 border border-blue-300"
                        : "bg-white border border-slate-100 hover:bg-slate-100"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={() => toggleDocId(doc.id)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-teal-600"
                    />
                    <DocumentTextIcon className="h-4 w-4 text-slate-400 shrink-0" />
                    <span className="truncate flex-1">{doc.filename}</span>
                    {doc.doc_type && doc.doc_type !== "OTHER" && (
                      <span className="text-[10px] bg-slate-200 text-slate-600 rounded px-1">
                        {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                      </span>
                    )}
                    {doc.extracted_montant != null && (
                      <span className="text-[10px] font-medium text-emerald-700">{formatMontant(doc.extracted_montant)}</span>
                    )}
                  </label>
                ))}
              </div>
            )}
            {selectedDocIds.length > 0 && (
              <p className="text-xs text-teal-600 mt-1">{selectedDocIds.length} document(s) sélectionné(s)</p>
            )}
          </div>

          {/* ── Journal Lines ── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-700">Lignes d'écriture</label>
              <button type="button" onClick={addLine} className="text-xs text-teal-600 hover:text-teal-800 flex items-center gap-0.5">
                <PlusIcon className="h-3 w-3" /> Ajouter ligne
              </button>
            </div>
            <table className="w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
              <thead>
                <tr className="bg-slate-50 border-b">
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-500">Compte</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-500">Libellé</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-500">Débit (DA)</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-500">Crédit (DA)</th>
                  <th className="px-3 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td className="px-2 py-1">
                      <input value={l.account_code} onChange={(e) => updateLine(i, "account_code", e.target.value)}
                        className="input-field text-xs font-mono w-24" placeholder="601" required />
                    </td>
                    <td className="px-2 py-1">
                      <input value={l.label} onChange={(e) => updateLine(i, "label", e.target.value)}
                        className="input-field text-xs" placeholder="Achats de matières premières" />
                    </td>
                    <td className="px-2 py-1">
                      <input type="number" step="0.01" min="0" value={l.debit} onChange={(e) => updateLine(i, "debit", e.target.value)}
                        className="input-field text-xs text-right w-28" placeholder="0.00" />
                    </td>
                    <td className="px-2 py-1">
                      <input type="number" step="0.01" min="0" value={l.credit} onChange={(e) => updateLine(i, "credit", e.target.value)}
                        className="input-field text-xs text-right w-28" placeholder="0.00" />
                    </td>
                    <td className="px-1 py-1 text-center">
                      {lines.length > 2 && (
                        <button type="button" onClick={() => removeLine(i)} className="text-slate-400 hover:text-red-500 p-0.5">
                          <TrashIcon className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50 border-t font-semibold text-xs">
                  <td className="px-3 py-2" colSpan={2}>Total</td>
                  <td className={`px-3 py-2 text-right ${balanced ? "text-emerald-700" : "text-red-600"}`}>
                    {totalDebit.toFixed(2)}
                  </td>
                  <td className={`px-3 py-2 text-right ${balanced ? "text-emerald-700" : "text-red-600"}`}>
                    {totalCredit.toFixed(2)}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
            {!balanced && totalDebit > 0 && (
              <p className="text-xs text-red-500 mt-1">Différence : {Math.abs(totalDebit - totalCredit).toFixed(2)} DA</p>
            )}
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary text-xs">Annuler</button>
            <button type="submit" disabled={creating || !balanced} className="btn-primary text-xs disabled:opacity-50">
              {creating ? "Enregistrement…" : "Enregistrer l'écriture"}
            </button>
          </div>
        </form>
      )}

      <div className="flex gap-6">
        {/* Entries table */}
        <div className="flex-1">
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">Référence</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Description</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600">Justif.</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
              ) : entries.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune écriture — cliquez «Nouvelle écriture» pour commencer</td></tr>
              ) : (
                entries.map((je) => (
                  <tr
                    key={je.id}
                    className={`hover:bg-slate-50 cursor-pointer ${selected?.id === je.id ? "bg-blue-50" : ""}`}
                    onClick={() => setSelected(je)}
                  >
                    <td className="px-4 py-3 font-mono text-sm">{je.entry_ref}</td>
                    <td className="px-4 py-3">{new Date(je.entry_date).toLocaleDateString("fr-FR")}</td>
                    <td className="px-4 py-3">
                      <span className={JE_STATUS[je.status]?.cls ?? "badge-neutral"}>
                        {JE_STATUS[je.status]?.label ?? je.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 truncate max-w-[200px]">{je.description ?? "—"}</td>
                    <td className="px-4 py-3 text-center">
                      {(je as any).source_doc_ids?.length > 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-teal-600">
                          <LinkIcon className="h-3.5 w-3.5" /> {(je as any).source_doc_ids.length}
                        </span>
                      ) : (
                        <span className="text-xs text-amber-500">Non justifié</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right space-x-1">
                      {je.status === "PROPOSED" && (
                        <>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleApprove(je.id); }}
                            className="rounded p-1 text-green-600 hover:bg-green-50"
                            title="Valider"
                          >
                            <CheckIcon className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleReject(je.id); }}
                            className="rounded p-1 text-red-600 hover:bg-red-50"
                            title="Rejeter"
                          >
                            <XMarkIcon className="h-4 w-4" />
                          </button>
                        </>
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
      {selected && (
        <div className="w-96 shrink-0 card p-5 space-y-4 self-start">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Écriture {selected.entry_ref}</h2>
            <button onClick={() => setSelected(null)} className="text-sm text-slate-400 hover:text-slate-600">✕</button>
          </div>

          {/* Lines */}
          <div>
            <h3 className="text-xs font-semibold text-slate-700 mb-2">Lignes d'écriture</h3>
            {selected.lines?.length ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="py-1 text-left">Compte</th>
                    <th className="py-1 text-right">Débit</th>
                    <th className="py-1 text-right">Crédit</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {selected.lines.map((l: any, i: number) => (
                    <tr key={i}>
                      <td className="py-1 font-mono">{l.account_code}</td>
                      <td className="py-1 text-right">{l.debit ? `${Number(l.debit).toFixed(2)} DA` : ""}</td>
                      <td className="py-1 text-right">{l.credit ? `${Number(l.credit).toFixed(2)} DA` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-slate-400">Aucune ligne</p>
            )}
          </div>

          {/* Linked Documents */}
          {(selected as any).source_doc_ids?.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                <LinkIcon className="h-3.5 w-3.5" /> Documents justificatifs
              </h3>
              <ul className="space-y-1.5">
                {(selected as any).source_doc_ids.map((docId: string) => {
                  const doc = availableDocs.find((d) => d.id === docId);
                  return (
                    <li key={docId} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                      <DocumentTextIcon className="h-4 w-4 text-blue-500 shrink-0" />
                      <span className="truncate flex-1">{doc?.filename ?? docId}</span>
                      {doc?.extracted_montant != null && (
                        <span className="flex items-center gap-0.5 text-emerald-700 font-medium">
                          <BanknotesIcon className="h-3 w-3" />
                          {formatMontant(doc.extracted_montant)}
                        </span>
                      )}
                      <button
                        className="text-teal-500 hover:text-teal-700"
                        title="Ouvrir le document"
                        onClick={() => window.open(`/api/v1/documents/${docId}/download`, "_blank")}
                      >
                        <EyeIcon className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  );
}


/* ── PDF Export Bar ── */
interface EntrepriseOption { id: string; code: string; raison_sociale: string; }

function PDFExportBar() {
  const [entreprises, setEntreprises] = useState<EntrepriseOption[]>([]);
  const [ent, setEnt] = useState("");
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1); d.setDate(1);
    return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    api.get("/entites-juridiques/").then(({ data }) => {
      if (Array.isArray(data)) {
        const ents = data.map((e: any) => ({ id: e.id, code: e.code, raison_sociale: e.raison_sociale }));
        setEntreprises(ents);
        if (ents.length > 0 && !ent) setEnt(ents[0].id);
      }
    }).catch(() => {});
  }, []);

  const [pdfLoading, setPdfLoading] = useState<string | null>(null);

  const openPdf = async (type: string) => {
    if (!ent) return;
    setPdfLoading(type);
    try {
      const { data } = await api.get(`/accounting/pdf/${type}`, {
        params: { entreprise_id: ent, date_from: dateFrom, date_to: dateTo },
        responseType: "blob",
      });
      const blob = new Blob([data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch {
      alert("Erreur lors de la generation du PDF");
    } finally {
      setPdfLoading(null);
    }
  };

  return (
    <div className="card p-3 mb-4 flex flex-wrap items-end gap-3">
      <div className="min-w-[170px]">
        <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Entit&eacute;</label>
        <select className="input-field text-xs py-1.5" value={ent} onChange={(e) => setEnt(e.target.value)}>
          {entreprises.map((e) => <option key={e.id} value={e.id}>{e.code}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Du</label>
        <input type="date" className="input-field text-xs py-1.5" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </div>
      <div>
        <label className="block text-[10px] font-medium text-slate-500 mb-0.5">Au</label>
        <input type="date" className="input-field text-xs py-1.5" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </div>
      <button onClick={() => openPdf("journal")} disabled={!ent || !!pdfLoading} className="btn-secondary text-xs py-1.5">
        {pdfLoading === "journal" ? "G\u00e9n\u00e9ration\u2026" : "PDF Journal"}
      </button>
      <button onClick={() => openPdf("balance")} disabled={!ent || !!pdfLoading} className="btn-secondary text-xs py-1.5">
        {pdfLoading === "balance" ? "G\u00e9n\u00e9ration\u2026" : "PDF Balance"}
      </button>
      <button onClick={() => openPdf("grand-livre")} disabled={!ent || !!pdfLoading} className="btn-secondary text-xs py-1.5">
        {pdfLoading === "grand-livre" ? "G\u00e9n\u00e9ration\u2026" : "PDF Grand Livre"}
      </button>
    </div>
  );
}


/* ── Déclarations Fiscales ── */

function DeclarationsSection() {
  const [entreprises, setEntreprises] = useState<EntrepriseOption[]>([]);
  const [selectedEnt, setSelectedEnt] = useState("");
  const [declType, setDeclType] = useState<"G50" | "CNAS">("G50");
  const [mois, setMois] = useState(new Date().getMonth() + 1);
  const [trimestre, setTrimestre] = useState(Math.ceil((new Date().getMonth() + 1) / 3));
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const [initMsg, setInitMsg] = useState("");

  useEffect(() => {
    api.get("/entites-juridiques/").then(({ data }) => {
      if (Array.isArray(data)) {
        const ents = data.map((e: any) => ({ id: e.id, code: e.code, raison_sociale: e.raison_sociale }));
        setEntreprises(ents);
        if (ents.length > 0 && !selectedEnt) setSelectedEnt(ents[0].id);
      }
    }).catch(() => {});
  }, []);

  const handleCompute = async () => {
    if (!selectedEnt) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      if (declType === "G50") {
        const { data } = await api.get("/accounting/declarations/g50", {
          params: { entreprise_id: selectedEnt, mois, annee },
        });
        setResult(data);
      } else {
        const { data } = await api.get("/accounting/declarations/cnas", {
          params: { entreprise_id: selectedEnt, trimestre, annee },
        });
        setResult(data);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur de calcul");
    } finally {
      setLoading(false);
    }
  };

  const handleInitSCF = async () => {
    setInitLoading(true);
    setInitMsg("");
    try {
      const { data } = await api.post("/accounting/scf/init");
      setInitMsg(`Plan SCF : ${data.accounts_created} comptes, ${data.journals_created} journaux cr&eacute;&eacute;s`);
    } catch (err: any) {
      setInitMsg(err?.response?.data?.detail ?? "Erreur d'initialisation");
    } finally {
      setInitLoading(false);
    }
  };

  const MOIS_LABELS = ["Janvier","F\u00e9vrier","Mars","Avril","Mai","Juin","Juillet","Ao\u00fbt","Septembre","Octobre","Novembre","D\u00e9cembre"];

  return (
    <div className="space-y-6">
      {/* SCF Init */}
      <div className="card p-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Initialisation Plan Comptable SCF</h3>
          <p className="text-xs text-slate-400">EX-SCF-001 &amp; EX-SCF-002 : plan comptable alg&eacute;rien + journaux par entit&eacute;</p>
        </div>
        <div className="flex items-center gap-3">
          {initMsg && <span className="text-xs text-teal-700">{initMsg}</span>}
          <button onClick={handleInitSCF} disabled={initLoading} className="btn-primary text-sm">
            {initLoading ? "Initialisation\u2026" : "Initialiser SCF"}
          </button>
        </div>
      </div>

      {/* Declaration computation */}
      <div className="card p-4 space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Calcul des d&eacute;clarations fiscales (EX-SCF-005)</h3>

        <div className="flex flex-wrap items-end gap-4">
          <div className="min-w-[200px]">
            <label className="block text-xs font-medium text-slate-500 mb-1">Entit&eacute; juridique</label>
            <select className="input-field text-sm" value={selectedEnt} onChange={(e) => setSelectedEnt(e.target.value)}>
              <option value="">S&eacute;lectionner</option>
              {entreprises.map((ent) => (
                <option key={ent.id} value={ent.id}>{ent.code} &mdash; {ent.raison_sociale}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
            <select className="input-field text-sm" value={declType} onChange={(e) => setDeclType(e.target.value as "G50" | "CNAS")}>
              <option value="G50">G50 (Mensuelle)</option>
              <option value="CNAS">CNAS (Trimestrielle)</option>
            </select>
          </div>

          {declType === "G50" ? (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Mois</label>
              <select className="input-field text-sm" value={mois} onChange={(e) => setMois(Number(e.target.value))}>
                {MOIS_LABELS.map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Trimestre</label>
              <select className="input-field text-sm" value={trimestre} onChange={(e) => setTrimestre(Number(e.target.value))}>
                <option value={1}>T1 (Jan-Mar)</option>
                <option value={2}>T2 (Avr-Jun)</option>
                <option value={3}>T3 (Jul-Sep)</option>
                <option value={4}>T4 (Oct-D&eacute;c)</option>
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Ann&eacute;e</label>
            <input type="number" className="input-field text-sm w-24" value={annee} onChange={(e) => setAnnee(Number(e.target.value))} />
          </div>

          <button onClick={handleCompute} disabled={loading || !selectedEnt} className="btn-primary text-sm">
            {loading ? "Calcul\u2026" : "Calculer"}
          </button>
          {result && (
            <button
              onClick={async () => {
                try {
                  const params = declType === "G50"
                    ? { entreprise_id: selectedEnt, mois, annee }
                    : { entreprise_id: selectedEnt, trimestre, annee };
                  const { data: blob } = await api.get(`/accounting/pdf/${declType.toLowerCase()}`, {
                    params,
                    responseType: "blob",
                  });
                  const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
                  window.open(url, "_blank");
                } catch {
                  alert("Erreur lors de la generation du PDF");
                }
              }}
              className="btn-secondary text-sm flex items-center gap-1.5"
            >
              <ArrowUpTrayIcon className="h-4 w-4 rotate-180" />
              T&eacute;l&eacute;charger PDF
            </button>
          )}
        </div>

        {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {result && declType === "G50" && (
          <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
            <h4 className="font-semibold text-teal-800 mb-3">G50 &mdash; {result.periode}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">CA HT</p>
                <p className="text-lg font-bold text-slate-800">{Number(result.ca_ht || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">TVA Collect&eacute;e</p>
                <p className="text-lg font-bold text-blue-700">{Number(result.tva_collectee || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">TVA D&eacute;ductible</p>
                <p className="text-lg font-bold text-emerald-700">{Number(result.tva_deductible || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">TVA Nette</p>
                <p className="text-lg font-bold text-amber-700">{Number(result.tva_nette || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">TAP</p>
                <p className="text-lg font-bold text-slate-800">{Number(result.tap || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">IBS Acompte</p>
                <p className="text-lg font-bold text-slate-800">{Number(result.ibs_acompte || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">IRG</p>
                <p className="text-lg font-bold text-slate-800">{Number(result.irg || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3 border-2 border-teal-300">
                <p className="text-xs text-teal-600 font-semibold">TOTAL &Agrave; PAYER</p>
                <p className="text-xl font-bold text-teal-800">{Number(result.total_a_payer || 0).toLocaleString("fr-FR")} DA</p>
              </div>
            </div>
          </div>
        )}

        {result && declType === "CNAS" && (
          <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
            <h4 className="font-semibold text-teal-800 mb-3">CNAS &mdash; {result.periode}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">Masse salariale brute</p>
                <p className="text-lg font-bold text-slate-800">{Number(result.masse_salariale_brute || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">Cotisation patronale</p>
                <p className="text-lg font-bold text-blue-700">{Number(result.cotisation_patronale || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3">
                <p className="text-xs text-slate-500">Cotisation salari&eacute;e</p>
                <p className="text-lg font-bold text-emerald-700">{Number(result.cotisation_salariale || 0).toLocaleString("fr-FR")} DA</p>
              </div>
              <div className="bg-white rounded-lg p-3 border-2 border-teal-300">
                <p className="text-xs text-teal-600 font-semibold">TOTAL COTISATIONS</p>
                <p className="text-xl font-bold text-teal-800">{Number(result.total_cotisations || 0).toLocaleString("fr-FR")} DA</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
