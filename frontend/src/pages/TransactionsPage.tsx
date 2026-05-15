import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  PlusIcon,
  ArrowPathIcon,
  FunnelIcon,
  DocumentTextIcon,
  HashtagIcon,
} from "@heroicons/react/24/outline";

/* ── Types ────────────────────────────────────────── */
interface Transaction {
  id: string;
  entreprise_id: string;
  projet_id: string | null;
  realite_financiere: string | null;
  type_transaction: string | null;
  montant: number;
  date_transaction: string;
  hash_sha256: string | null;
  description?: string;
  reference?: string;
  compte_debit?: string;
  compte_credit?: string;
  created_at?: string;
}

interface TransactionForm {
  entreprise_id: string;
  projet_id: string;
  realite_financiere: string;
  type_transaction: string;
  montant: string;
  date_transaction: string;
  description: string;
  reference: string;
  compte_debit: string;
  compte_credit: string;
}

const RF_OPTIONS = [
  { value: "RF1", label: "RF1 - Reel Declare", color: "bg-emerald-100 text-emerald-800" },
  { value: "RF2", label: "RF2 - Reel Non Declare", color: "bg-amber-100 text-amber-800" },
  { value: "RF3", label: "RF3 - Fictif Declare (CFF)", color: "bg-red-100 text-red-800" },
  { value: "RF4", label: "RF4 - Fictif Non Declare", color: "bg-slate-100 text-slate-800" },
];

const TYPE_OPTIONS = [
  "ENCAISSEMENT",
  "DECAISSEMENT",
  "VIREMENT_INTERNE",
  "COMPENSATION",
  "AVANCE_MATERIEL",
  "LIBERATION_CAPITAL",
  "RETRAIT_ASSOCIE",
  "CESSION_PARTS",
  "HONORAIRE",
  "CHARGE_COMMUNE",
];

function formatMoney(value: number | null | undefined) {
  if (value == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + " DA";
}

function rfBadge(rf: string | null) {
  const opt = RF_OPTIONS.find((o) => o.value === rf);
  if (!opt) return <span className="badge-neutral text-xs">{rf || "?"}</span>;
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${opt.color}`}>{opt.value}</span>;
}

const emptyForm: TransactionForm = {
  entreprise_id: "",
  projet_id: "",
  realite_financiere: "RF1",
  type_transaction: "ENCAISSEMENT",
  montant: "",
  date_transaction: new Date().toISOString().slice(0, 10),
  description: "",
  reference: "",
  compte_debit: "",
  compte_credit: "",
};

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TransactionForm>({ ...emptyForm });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [detail, setDetail] = useState<Transaction | null>(null);

  /* ── Filters ── */
  const [filterRF, setFilterRF] = useState("");
  const [filterEntreprise, setFilterEntreprise] = useState("");

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterRF) params.realite_financiere = filterRF;
      if (filterEntreprise) params.entreprise_id = filterEntreprise;
      const { data } = await api.get("/transactions/", { params });
      setTransactions(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [filterRF, filterEntreprise]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleSubmit = async () => {
    setFormError("");
    if (!form.entreprise_id || !form.montant || !form.realite_financiere) {
      setFormError("Entreprise, montant et realite financiere sont obligatoires.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/transactions/", {
        entreprise_id: form.entreprise_id,
        projet_id: form.projet_id || null,
        realite_financiere: form.realite_financiere,
        type_transaction: form.type_transaction,
        montant: parseFloat(form.montant),
        date_transaction: form.date_transaction,
        description: form.description || null,
        reference: form.reference || null,
        compte_debit: form.compte_debit || null,
        compte_credit: form.compte_credit || null,
      });
      setShowForm(false);
      setForm({ ...emptyForm });
      fetchTransactions();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || "Erreur lors de la creation.");
    } finally {
      setSaving(false);
    }
  };

  const viewDetail = async (id: string) => {
    try {
      const { data } = await api.get(`/transactions/${id}`);
      setDetail(data);
    } catch {
      /* ignore */
    }
  };

  const updateForm = (field: keyof TransactionForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Transactions</h1>
          <p className="mt-1 text-sm text-slate-500">
            Toutes les transactions avec Realite Financiere (RF1-RF4) obligatoire et hash SHA-256.
          </p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <PlusIcon className="h-4 w-4" /> Nouvelle transaction
        </button>
      </div>

      {/* RF Legend */}
      <div className="flex flex-wrap gap-3">
        {RF_OPTIONS.map((rf) => (
          <div key={rf.value} className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${rf.color}`}>
            {rf.label}
          </div>
        ))}
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="card p-6 space-y-4 border-l-4 border-teal-500">
          <h2 className="text-base font-semibold text-slate-900">Nouvelle Transaction</h2>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-slate-700">Entreprise ID *</label>
              <input
                type="text"
                value={form.entreprise_id}
                onChange={(e) => updateForm("entreprise_id", e.target.value)}
                className="input-field mt-1"
                placeholder="UUID entreprise"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Projet ID</label>
              <input
                type="text"
                value={form.projet_id}
                onChange={(e) => updateForm("projet_id", e.target.value)}
                className="input-field mt-1"
                placeholder="UUID projet (optionnel)"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Realite Financiere *</label>
              <select
                value={form.realite_financiere}
                onChange={(e) => updateForm("realite_financiere", e.target.value)}
                className="input-field mt-1"
              >
                {RF_OPTIONS.map((rf) => (
                  <option key={rf.value} value={rf.value}>{rf.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Type Transaction *</label>
              <select
                value={form.type_transaction}
                onChange={(e) => updateForm("type_transaction", e.target.value)}
                className="input-field mt-1"
              >
                {TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Montant (DA) *</label>
              <input
                type="number"
                value={form.montant}
                onChange={(e) => updateForm("montant", e.target.value)}
                className="input-field mt-1"
                placeholder="0.00"
                min="0.01"
                step="0.01"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Date Transaction</label>
              <input
                type="date"
                value={form.date_transaction}
                onChange={(e) => updateForm("date_transaction", e.target.value)}
                className="input-field mt-1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Reference</label>
              <input
                type="text"
                value={form.reference}
                onChange={(e) => updateForm("reference", e.target.value)}
                className="input-field mt-1"
                placeholder="REF-2024-001"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Compte debit</label>
              <input
                type="text"
                value={form.compte_debit}
                onChange={(e) => updateForm("compte_debit", e.target.value)}
                className="input-field mt-1"
                placeholder="512000"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Compte credit</label>
              <input
                type="text"
                value={form.compte_credit}
                onChange={(e) => updateForm("compte_credit", e.target.value)}
                className="input-field mt-1"
                placeholder="401000"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => updateForm("description", e.target.value)}
              className="input-field mt-1"
              rows={2}
              placeholder="Description de la transaction..."
            />
          </div>

          {formError && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {formError}
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={handleSubmit} disabled={saving} className="btn-primary">
              {saving ? <ArrowPathIcon className="h-4 w-4 animate-spin" /> : null}
              Enregistrer
            </button>
            <button onClick={() => { setShowForm(false); setFormError(""); }} className="btn-secondary">
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-slate-600">
            <FunnelIcon className="inline h-3 w-3" /> Filtrer par RF
          </label>
          <select
            value={filterRF}
            onChange={(e) => setFilterRF(e.target.value)}
            className="input-field mt-1 text-sm"
          >
            <option value="">Toutes</option>
            {RF_OPTIONS.map((rf) => (
              <option key={rf.value} value={rf.value}>{rf.value}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600">Entreprise ID</label>
          <input
            type="text"
            value={filterEntreprise}
            onChange={(e) => setFilterEntreprise(e.target.value)}
            className="input-field mt-1 text-sm"
            placeholder="Filtrer..."
          />
        </div>
        <button onClick={fetchTransactions} className="btn-secondary text-xs">
          <ArrowPathIcon className="h-4 w-4" /> Actualiser
        </button>
      </div>

      {/* Transactions Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : transactions.length === 0 ? (
          <p className="text-sm text-slate-400 py-12 text-center">Aucune transaction trouvee.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
                  <th className="px-4 py-3">RF</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Entreprise</th>
                  <th className="px-4 py-3 text-right">Montant</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Hash SHA-256</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3">{rfBadge(txn.realite_financiere)}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {txn.type_transaction?.replace(/_/g, " ") || "\u2014"}
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs font-mono">
                      {txn.entreprise_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-900">
                      {formatMoney(txn.montant)}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {new Date(txn.date_transaction).toLocaleDateString("fr-FR")}
                    </td>
                    <td className="px-4 py-3">
                      {txn.hash_sha256 ? (
                        <span className="inline-flex items-center gap-1 text-xs font-mono text-slate-400" title={txn.hash_sha256}>
                          <HashtagIcon className="h-3 w-3" />
                          {txn.hash_sha256.slice(0, 12)}...
                        </span>
                      ) : "\u2014"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => viewDetail(txn.id)}
                        className="text-xs text-teal-600 hover:text-teal-800 font-medium"
                      >
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setDetail(null)}>
          <div className="card w-full max-w-lg mx-4 p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Detail Transaction</h2>
              <button onClick={() => setDetail(null)} className="text-slate-400 hover:text-slate-600 text-xl">&times;</button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500">Realite Financiere</p>
                <div className="mt-1">{rfBadge(detail.realite_financiere)}</div>
              </div>
              <div>
                <p className="text-xs text-slate-500">Type</p>
                <p className="mt-1 font-medium">{detail.type_transaction?.replace(/_/g, " ")}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Montant</p>
                <p className="mt-1 font-bold text-lg">{formatMoney(detail.montant)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Date</p>
                <p className="mt-1">{new Date(detail.date_transaction).toLocaleDateString("fr-FR")}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-slate-500">Entreprise ID</p>
                <p className="mt-1 font-mono text-xs">{detail.entreprise_id}</p>
              </div>
              {detail.projet_id && (
                <div className="col-span-2">
                  <p className="text-xs text-slate-500">Projet ID</p>
                  <p className="mt-1 font-mono text-xs">{detail.projet_id}</p>
                </div>
              )}
              {detail.description && (
                <div className="col-span-2">
                  <p className="text-xs text-slate-500">Description</p>
                  <p className="mt-1">{detail.description}</p>
                </div>
              )}
              {detail.reference && (
                <div>
                  <p className="text-xs text-slate-500">Reference</p>
                  <p className="mt-1">{detail.reference}</p>
                </div>
              )}
              {detail.compte_debit && (
                <div>
                  <p className="text-xs text-slate-500">Debit</p>
                  <p className="mt-1 font-mono">{detail.compte_debit}</p>
                </div>
              )}
              {detail.compte_credit && (
                <div>
                  <p className="text-xs text-slate-500">Credit</p>
                  <p className="mt-1 font-mono">{detail.compte_credit}</p>
                </div>
              )}
              <div className="col-span-2">
                <p className="text-xs text-slate-500">SHA-256</p>
                <p className="mt-1 font-mono text-xs break-all text-slate-600">{detail.hash_sha256 || "\u2014"}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
