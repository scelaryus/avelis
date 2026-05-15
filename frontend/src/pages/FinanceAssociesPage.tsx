import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
  BanknotesIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  CurrencyDollarIcon,
} from "@heroicons/react/24/outline";

/* ── Types ────────────────────────────────────────── */
interface Capital {
  id: string;
  associe_id: string;
  projet_id: string;
  montant: number;
  date_versement: string;
  mode_paiement: string;
  reference: string | null;
  associe_nom?: string;
  projet_nom?: string;
}
interface Retrait {
  id: string;
  associe_id: string;
  projet_id: string;
  montant: number;
  date_retrait: string;
  motif: string | null;
  approuve_par: string | null;
  associe_nom?: string;
  projet_nom?: string;
}
interface Consolidation {
  id: string;
  associe_id: string;
  projet_id: string;
  capital_verse: number;
  retraits: number;
  position_nette: number;
  alerte_negative: boolean;
  date_calcul: string;
  associe_nom?: string;
  projet_nom?: string;
}
interface ConsolidationEntreprise {
  id: string;
  projet_id: string;
  total_capital: number;
  total_retraits: number;
  solde_net: number;
  nb_associes: number;
  date_calcul: string;
  projet_nom?: string;
}
interface Bulletin {
  id: string;
  employee_id: string;
  mois: number;
  annee: number;
  salaire_base: number;
  salaire_reel_total: number;
  net_a_payer: number;
  statut: string;
  employee_nom?: string;
}
interface Declaration {
  id: string;
  type_declaration: string;
  periode: string;
  montant_base: number;
  taux: number;
  montant_du: number;
  statut: string;
  date_echeance: string;
}
interface CompteBancaire {
  id: string;
  banque: string;
  numero_compte: string;
  intitule: string;
  devise: string;
  solde_actuel: number;
  is_active: boolean;
}
interface Journal {
  id: string;
  code: string;
  libelle: string;
  type_journal: string;
}
interface Echeance {
  id: string;
  client_id: string;
  projet_id: string;
  montant: number;
  date_echeance: string;
  statut: string;
  date_paiement: string | null;
  client_nom?: string;
  projet_nom?: string;
}

interface EntrepriseAssocieRow {
  id: string;
  entreprise_id: string;
  associe_id: string;
  pourcentage: number;
  est_actif: boolean;
  entreprise_nom?: string;
  associe_nom?: string;
}

type Tab = "capital" | "retraits" | "consolidation" | "pct_entreprise" | "bulletins" | "declarations" | "comptes" | "journaux" | "echeancier";

const TABS: { key: Tab; label: string }[] = [
  { key: "capital", label: "Capital" },
  { key: "retraits", label: "Retraits" },
  { key: "consolidation", label: "Consolidation" },
  { key: "pct_entreprise", label: "% Entreprise" },
  { key: "bulletins", label: "Bulletins de Paie" },
  { key: "declarations", label: "Déclarations" },
  { key: "comptes", label: "Comptes Bancaires" },
  { key: "journaux", label: "Journaux" },
  { key: "echeancier", label: "Échéancier" },
];

const fmtCurrency = (v: number) =>
  new Intl.NumberFormat("fr-DZ", { style: "currency", currency: "DZD", maximumFractionDigits: 2 }).format(v);

const fmtDate = (d: string) =>
  d ? new Date(d).toLocaleDateString("fr-FR") : "—";

const STATUT_BADGE: Record<string, { cls: string; label: string }> = {
  BROUILLON: { cls: "bg-yellow-100 text-yellow-800", label: "Brouillon" },
  VALIDE: { cls: "bg-green-100 text-green-800", label: "Validé" },
  PAYE: { cls: "bg-blue-100 text-blue-800", label: "Payé" },
  EN_ATTENTE: { cls: "bg-yellow-100 text-yellow-800", label: "En attente" },
  DEPOSEE: { cls: "bg-blue-100 text-blue-800", label: "Déposée" },
  PAYEE: { cls: "bg-green-100 text-green-800", label: "Payée" },
  EN_RETARD: { cls: "bg-red-100 text-red-800", label: "En retard" },
  ECHEANCE: { cls: "bg-yellow-100 text-yellow-800", label: "Échéance" },
  REGLE: { cls: "bg-green-100 text-green-800", label: "Réglé" },
  IMPAYE: { cls: "bg-red-100 text-red-800", label: "Impayé" },
};

function Badge({ status }: { status: string }) {
  const b = STATUT_BADGE[status] || { cls: "bg-slate-100 text-slate-600", label: status };
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${b.cls}`}>{b.label}</span>;
}

export default function FinanceAssociesPage() {
  const [tab, setTab] = useState<Tab>("capital");

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Trésorerie & Finance Associés</h1>
      <p className="text-sm text-slate-500 mb-6">Capital, retraits, consolidation, paie & déclarations fiscales</p>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`whitespace-nowrap px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "capital" && <CapitalSection />}
      {tab === "retraits" && <RetraitsSection />}
      {tab === "consolidation" && <ConsolidationSection />}
      {tab === "pct_entreprise" && <EntrepriseAssocieSection />}
      {tab === "bulletins" && <BulletinsSection />}
      {tab === "declarations" && <DeclarationsSection />}
      {tab === "comptes" && <ComptesSection />}
      {tab === "journaux" && <JournauxSection />}
      {tab === "echeancier" && <EcheancierSection />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Capital Section
   ══════════════════════════════════════════════════════ */
function CapitalSection() {
  const [items, setItems] = useState<Capital[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ associe_id: "", projet_id: "", montant: "", date_versement: "", mode_paiement: "VIREMENT", reference: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/capital");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/capital", {
      ...form,
      montant: parseFloat(form.montant),
    });
    setShowForm(false);
    setForm({ associe_id: "", projet_id: "", montant: "", date_versement: "", mode_paiement: "VIREMENT", reference: "" });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer ce versement de capital ?")) return;
    await api.delete(`/treasury/capital/${id}`);
    load();
  };

  const totalCapital = items.reduce((s, i) => s + i.montant, 0);

  return (
    <div>
      {/* Summary card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card p-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
            <ArrowTrendingUpIcon className="h-5 w-5 text-green-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Capital Versé</p>
            <p className="text-lg font-bold text-slate-900">{fmtCurrency(totalCapital)}</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
            <BanknotesIcon className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Nombre de Versements</p>
            <p className="text-lg font-bold text-slate-900">{items.length}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Capital des Associés</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouveau versement
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Associé ID</label>
            <input value={form.associe_id} onChange={(e) => setForm({ ...form, associe_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Projet ID</label>
            <input value={form.projet_id} onChange={(e) => setForm({ ...form, projet_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Montant (DZD)</label>
            <input type="number" step="0.01" min="0.01" value={form.montant} onChange={(e) => setForm({ ...form, montant: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Date versement</label>
            <input type="date" value={form.date_versement} onChange={(e) => setForm({ ...form, date_versement: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Mode de paiement</label>
            <select value={form.mode_paiement} onChange={(e) => setForm({ ...form, mode_paiement: e.target.value })} className="input-field">
              <option value="VIREMENT">Virement</option>
              <option value="CHEQUE">Chèque</option>
              <option value="ESPECES">Espèces</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Référence</label>
            <input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} className="input-field" placeholder="Optionnel" />
          </div>
          <div className="md:col-span-3 flex justify-end">
            <button type="submit" className="btn-primary text-xs">Enregistrer</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Associé</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Projet</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Mode</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Réf.</th>
              <th className="px-4 py-3 w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucun versement de capital</td></tr>
            ) : (
              items.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">{c.associe_nom || c.associe_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3">{c.projet_nom || c.projet_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium text-green-700">{fmtCurrency(c.montant)}</td>
                  <td className="px-4 py-3">{fmtDate(c.date_versement)}</td>
                  <td className="px-4 py-3">{c.mode_paiement}</td>
                  <td className="px-4 py-3 text-slate-500">{c.reference || "—"}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleDelete(c.id)} className="p-1 text-red-400 hover:text-red-600 rounded hover:bg-red-50">
                      <TrashIcon className="h-4 w-4" />
                    </button>
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

/* ══════════════════════════════════════════════════════
   Retraits Section
   ══════════════════════════════════════════════════════ */
function RetraitsSection() {
  const [items, setItems] = useState<Retrait[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ associe_id: "", projet_id: "", montant: "", date_retrait: "", motif: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/retraits");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/retraits", { ...form, montant: parseFloat(form.montant) });
    setShowForm(false);
    setForm({ associe_id: "", projet_id: "", montant: "", date_retrait: "", motif: "" });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer ce retrait ?")) return;
    await api.delete(`/treasury/retraits/${id}`);
    load();
  };

  const totalRetraits = items.reduce((s, i) => s + i.montant, 0);

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="card p-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100">
            <ArrowTrendingDownIcon className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Retraits</p>
            <p className="text-lg font-bold text-red-700">{fmtCurrency(totalRetraits)}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Retraits Associés</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouveau retrait
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Associé ID</label>
            <input value={form.associe_id} onChange={(e) => setForm({ ...form, associe_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Projet ID</label>
            <input value={form.projet_id} onChange={(e) => setForm({ ...form, projet_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Montant (DZD)</label>
            <input type="number" step="0.01" min="0.01" value={form.montant} onChange={(e) => setForm({ ...form, montant: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Date retrait</label>
            <input type="date" value={form.date_retrait} onChange={(e) => setForm({ ...form, date_retrait: e.target.value })} className="input-field" required />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-slate-500 mb-1">Motif</label>
            <input value={form.motif} onChange={(e) => setForm({ ...form, motif: e.target.value })} className="input-field" placeholder="Optionnel" />
          </div>
          <div className="md:col-span-3 flex justify-end">
            <button type="submit" className="btn-primary text-xs">Enregistrer</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Associé</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Projet</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Motif</th>
              <th className="px-4 py-3 w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucun retrait</td></tr>
            ) : (
              items.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">{r.associe_nom || r.associe_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3">{r.projet_nom || r.projet_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium text-red-700">{fmtCurrency(r.montant)}</td>
                  <td className="px-4 py-3">{fmtDate(r.date_retrait)}</td>
                  <td className="px-4 py-3 text-slate-500">{r.motif || "—"}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleDelete(r.id)} className="p-1 text-red-400 hover:text-red-600 rounded hover:bg-red-50">
                      <TrashIcon className="h-4 w-4" />
                    </button>
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

/* ══════════════════════════════════════════════════════
   Consolidation Section
   ══════════════════════════════════════════════════════ */
function ConsolidationSection() {
  const [associes, setAssocies] = useState<Consolidation[]>([]);
  const [entreprises, setEntreprises] = useState<ConsolidationEntreprise[]>([]);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [subTab, setSubTab] = useState<"associes" | "entreprises">("associes");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [aRes, eRes] = await Promise.all([
        api.get("/treasury/consolidation/associes"),
        api.get("/treasury/consolidation/entreprises"),
      ]);
      setAssocies(Array.isArray(aRes.data) ? aRes.data : []);
      setEntreprises(Array.isArray(eRes.data) ? eRes.data : []);
    } catch {
      setAssocies([]);
      setEntreprises([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCompute = async () => {
    setComputing(true);
    try {
      await api.post("/treasury/consolidation/compute");
      load();
    } finally { setComputing(false); }
  };

  const hasAlerts = associes.some((a) => a.alerte_negative);

  return (
    <div>
      {hasAlerts && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <ExclamationTriangleIcon className="h-5 w-5 shrink-0" />
          <span>Attention : certains associés ont une position nette négative !</span>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2">
          <button
            onClick={() => setSubTab("associes")}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${subTab === "associes" ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
          >
            Par Associé
          </button>
          <button
            onClick={() => setSubTab("entreprises")}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${subTab === "entreprises" ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
          >
            Par Entreprise
          </button>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={handleCompute} disabled={computing} className="btn-primary text-xs">
            <CurrencyDollarIcon className="h-4 w-4" />
            {computing ? "Calcul…" : "Recalculer"}
          </button>
        </div>
      </div>

      {subTab === "associes" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">Associé</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Projet</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Capital Versé</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Retraits</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Position Nette</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Alerte</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Date Calcul</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
              ) : associes.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune consolidation — cliquez Recalculer</td></tr>
              ) : (
                associes.map((a) => (
                  <tr key={a.id} className={`hover:bg-slate-50 ${a.alerte_negative ? "bg-red-50/50" : ""}`}>
                    <td className="px-4 py-3">{a.associe_nom || a.associe_id?.substring(0, 8)}</td>
                    <td className="px-4 py-3">{a.projet_nom || a.projet_id?.substring(0, 8)}</td>
                    <td className="px-4 py-3 text-right font-mono text-green-700">{fmtCurrency(a.capital_verse)}</td>
                    <td className="px-4 py-3 text-right font-mono text-red-600">{fmtCurrency(a.retraits)}</td>
                    <td className={`px-4 py-3 text-right font-mono font-bold ${a.position_nette < 0 ? "text-red-700" : "text-slate-900"}`}>
                      {fmtCurrency(a.position_nette)}
                    </td>
                    <td className="px-4 py-3">
                      {a.alerte_negative ? (
                        <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                      ) : (
                        <CheckCircleIcon className="h-5 w-5 text-green-500" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(a.date_calcul)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {subTab === "entreprises" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">Projet</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Total Capital</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Total Retraits</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Solde Net</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Nb Associés</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Date Calcul</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
              ) : entreprises.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune consolidation entreprise</td></tr>
              ) : (
                entreprises.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium">{e.projet_nom || e.projet_id?.substring(0, 8)}</td>
                    <td className="px-4 py-3 text-right font-mono text-green-700">{fmtCurrency(e.total_capital)}</td>
                    <td className="px-4 py-3 text-right font-mono text-red-600">{fmtCurrency(e.total_retraits)}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold">{fmtCurrency(e.solde_net)}</td>
                    <td className="px-4 py-3 text-right">{e.nb_associes}</td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(e.date_calcul)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   % Entreprise (EntrepriseAssocie) — GFI v7.0
   ══════════════════════════════════════════════════════ */
function EntrepriseAssocieSection() {
  const [items, setItems] = useState<EntrepriseAssocieRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/finance/entreprise-associes");
      setItems(Array.isArray(data) ? data : data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetch_(); }, [fetch_]);

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Participations Entreprise (%)</h2>
          <p className="text-xs text-slate-500 mt-1">
            Pourcentages d'entreprise (EntrepriseAssocie) — utilises par CFF et cloture mensuelle. PAS les parts projet.
          </p>
        </div>
        <button onClick={fetch_} className="btn-secondary text-xs">
          <ArrowPathIcon className="h-4 w-4" /> Actualiser
        </button>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 mb-4">
        <div className="flex items-start gap-2">
          <ExclamationTriangleIcon className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="text-xs text-amber-800">
            <p className="font-semibold">Important GFI v7.0</p>
            <p>Le CFF et la cloture mensuelle utilisent TOUJOURS les pourcentages entreprise ci-dessous, jamais les parts de projet. Ceci est l'invariant KT-02/KT-03.</p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-8">
          Aucune participation entreprise trouvee. Les donnees doivent etre saisies via l'API /finance/entreprise-associes.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="pb-2">Associe</th>
                <th className="pb-2">Entreprise</th>
                <th className="pb-2 text-right">% Entreprise</th>
                <th className="pb-2 text-center">Actif</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 font-medium text-slate-800">{row.associe_nom || row.associe_id}</td>
                  <td className="py-2 text-slate-600">{row.entreprise_nom || row.entreprise_id}</td>
                  <td className="py-2 text-right font-bold text-slate-900">{row.pourcentage}%</td>
                  <td className="py-2 text-center">
                    {row.est_actif ? (
                      <CheckCircleIcon className="h-4 w-4 text-emerald-600 inline" />
                    ) : (
                      <span className="text-xs text-slate-400">Inactif</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Sum validation */}
          {(() => {
            const byEntreprise: Record<string, number> = {};
            items.filter(r => r.est_actif).forEach(r => {
              const key = r.entreprise_nom || r.entreprise_id;
              byEntreprise[key] = (byEntreprise[key] || 0) + r.pourcentage;
            });
            const entries = Object.entries(byEntreprise);
            if (entries.length === 0) return null;
            return (
              <div className="mt-4 space-y-1">
                <p className="text-xs font-semibold text-slate-600">Verification somme = 100% par entreprise:</p>
                {entries.map(([name, total]) => (
                  <div key={name} className={`flex items-center justify-between text-xs rounded px-2 py-1 ${
                    Math.abs(total - 100) < 0.01
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-red-50 text-red-700"
                  }`}>
                    <span>{name}</span>
                    <span className="font-mono font-bold">{total.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Bulletins de Paie Section
   ══════════════════════════════════════════════════════ */
function BulletinsSection() {
  const [items, setItems] = useState<Bulletin[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ employee_id: "", mois: new Date().getMonth() + 1, annee: new Date().getFullYear(), salaire_base: "", poste: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/bulletins");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/bulletins", {
      ...form,
      salaire_base: parseFloat(form.salaire_base),
    });
    setShowForm(false);
    load();
  };

  const handleValidate = async (id: string) => {
    await api.patch(`/treasury/bulletins/${id}/validate`);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Bulletins de Paie</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouveau bulletin
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Employee ID</label>
            <input value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Mois</label>
            <input type="number" min={1} max={12} value={form.mois} onChange={(e) => setForm({ ...form, mois: parseInt(e.target.value) })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Année</label>
            <input type="number" min={2020} max={2030} value={form.annee} onChange={(e) => setForm({ ...form, annee: parseInt(e.target.value) })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Salaire de Base (DZD)</label>
            <input type="number" step="0.01" min="0" value={form.salaire_base} onChange={(e) => setForm({ ...form, salaire_base: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Poste</label>
            <input value={form.poste} onChange={(e) => setForm({ ...form, poste: e.target.value })} className="input-field" placeholder="Optionnel" />
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary text-xs">Créer bulletin</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Employé</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Période</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Salaire Base</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Salaire Réel</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Net à Payer</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucun bulletin</td></tr>
            ) : (
              items.map((b) => (
                <tr key={b.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">{b.employee_nom || b.employee_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3">{String(b.mois).padStart(2, "0")}/{b.annee}</td>
                  <td className="px-4 py-3 text-right font-mono">{fmtCurrency(b.salaire_base)}</td>
                  <td className="px-4 py-3 text-right font-mono">{fmtCurrency(b.salaire_reel_total)}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{fmtCurrency(b.net_a_payer)}</td>
                  <td className="px-4 py-3"><Badge status={b.statut} /></td>
                  <td className="px-4 py-3">
                    {b.statut === "BROUILLON" && (
                      <button onClick={() => handleValidate(b.id)} className="btn-primary text-xs px-2 py-1">
                        <CheckCircleIcon className="h-4 w-4" />
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

/* ══════════════════════════════════════════════════════
   Déclarations Fiscales Section
   ══════════════════════════════════════════════════════ */
function DeclarationsSection() {
  const [items, setItems] = useState<Declaration[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ type_declaration: "G50", periode: "", montant_base: "", taux: "19", date_echeance: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/declarations");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/declarations", {
      ...form,
      montant_base: parseFloat(form.montant_base),
      taux: parseFloat(form.taux),
    });
    setShowForm(false);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Déclarations Fiscales</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouvelle déclaration
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
            <select value={form.type_declaration} onChange={(e) => setForm({ ...form, type_declaration: e.target.value })} className="input-field">
              <option value="G50">G50 (TVA mensuelle)</option>
              <option value="G50A">G50A (TVA annuelle)</option>
              <option value="CNAS">CNAS (Cotisations)</option>
              <option value="CACOBATPH">CACOBATPH</option>
              <option value="IBS">IBS (Impôt société)</option>
              <option value="TAP">TAP (Taxe activité pro)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Période</label>
            <input value={form.periode} onChange={(e) => setForm({ ...form, periode: e.target.value })} className="input-field" required placeholder="2025-01" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Montant Base (DZD)</label>
            <input type="number" step="0.01" value={form.montant_base} onChange={(e) => setForm({ ...form, montant_base: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Taux (%)</label>
            <input type="number" step="0.01" value={form.taux} onChange={(e) => setForm({ ...form, taux: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Date échéance</label>
            <input type="date" value={form.date_echeance} onChange={(e) => setForm({ ...form, date_echeance: e.target.value })} className="input-field" required />
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary text-xs">Créer</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Type</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Période</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Base</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Taux</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant Dû</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Échéance</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune déclaration</td></tr>
            ) : (
              items.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{d.type_declaration}</td>
                  <td className="px-4 py-3">{d.periode}</td>
                  <td className="px-4 py-3 text-right font-mono">{fmtCurrency(d.montant_base)}</td>
                  <td className="px-4 py-3 text-right">{d.taux}%</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{fmtCurrency(d.montant_du)}</td>
                  <td className="px-4 py-3">{fmtDate(d.date_echeance)}</td>
                  <td className="px-4 py-3"><Badge status={d.statut} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Comptes Bancaires Section
   ══════════════════════════════════════════════════════ */
function ComptesSection() {
  const [items, setItems] = useState<CompteBancaire[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ banque: "", numero_compte: "", intitule: "", devise: "DZD", solde_actuel: "0" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/comptes-bancaires");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/comptes-bancaires", {
      ...form,
      solde_actuel: parseFloat(form.solde_actuel),
    });
    setShowForm(false);
    setForm({ banque: "", numero_compte: "", intitule: "", devise: "DZD", solde_actuel: "0" });
    load();
  };

  const totalSolde = items.reduce((s, i) => s + i.solde_actuel, 0);

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="card p-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-100">
            <BanknotesIcon className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Solde Total Bancaire</p>
            <p className="text-lg font-bold text-slate-900">{fmtCurrency(totalSolde)}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Comptes Bancaires</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Ajouter compte
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Banque</label>
            <input value={form.banque} onChange={(e) => setForm({ ...form, banque: e.target.value })} className="input-field" required placeholder="BNA, CPA, ..." />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">N° Compte</label>
            <input value={form.numero_compte} onChange={(e) => setForm({ ...form, numero_compte: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Intitulé</label>
            <input value={form.intitule} onChange={(e) => setForm({ ...form, intitule: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Devise</label>
            <input value={form.devise} onChange={(e) => setForm({ ...form, devise: e.target.value })} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Solde initial</label>
            <input type="number" step="0.01" value={form.solde_actuel} onChange={(e) => setForm({ ...form, solde_actuel: e.target.value })} className="input-field" />
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary text-xs">Enregistrer</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <p className="text-slate-400 col-span-full text-center py-8">Chargement…</p>
        ) : items.length === 0 ? (
          <p className="text-slate-400 col-span-full text-center py-8">Aucun compte bancaire</p>
        ) : (
          items.map((c) => (
            <div key={c.id} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-slate-900">{c.banque}</span>
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${c.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                  {c.is_active ? "Actif" : "Inactif"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-1">{c.intitule}</p>
              <p className="text-xs font-mono text-slate-400 mb-3">{c.numero_compte}</p>
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-slate-500">Solde</span>
                <span className="text-lg font-bold text-slate-900">{fmtCurrency(c.solde_actuel)}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Journaux Section
   ══════════════════════════════════════════════════════ */
function JournauxSection() {
  const [items, setItems] = useState<Journal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", libelle: "", type_journal: "BANQUE" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/journaux");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/journaux", form);
    setShowForm(false);
    setForm({ code: "", libelle: "", type_journal: "BANQUE" });
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Journaux Comptables</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Ajouter journal
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 flex items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Code</label>
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input-field w-24" required />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">Libellé</label>
            <input value={form.libelle} onChange={(e) => setForm({ ...form, libelle: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
            <select value={form.type_journal} onChange={(e) => setForm({ ...form, type_journal: e.target.value })} className="input-field w-40">
              <option value="BANQUE">Banque</option>
              <option value="CAISSE">Caisse</option>
              <option value="ACHAT">Achat</option>
              <option value="VENTE">Vente</option>
              <option value="OD">OD</option>
              <option value="PAIE">Paie</option>
              <option value="STOCK">Stock</option>
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
            ) : items.length === 0 ? (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Aucun journal</td></tr>
            ) : (
              items.map((j) => (
                <tr key={j.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono font-medium">{j.code}</td>
                  <td className="px-4 py-3">{j.libelle}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">{j.type_journal}</span>
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

/* ══════════════════════════════════════════════════════
   Échéancier Section
   ══════════════════════════════════════════════════════ */
function EcheancierSection() {
  const [items, setItems] = useState<Echeance[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ client_id: "", projet_id: "", montant: "", date_echeance: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/treasury/echeancier");
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/treasury/echeancier", {
      ...form,
      montant: parseFloat(form.montant),
    });
    setShowForm(false);
    setForm({ client_id: "", projet_id: "", montant: "", date_echeance: "" });
    load();
  };

  const handlePay = async (id: string) => {
    await api.patch(`/treasury/echeancier/${id}/pay`);
    load();
  };

  const totalDu = items.filter((i) => i.statut !== "REGLE").reduce((s, i) => s + i.montant, 0);

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="card p-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
            <CurrencyDollarIcon className="h-5 w-5 text-amber-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Restant Dû</p>
            <p className="text-lg font-bold text-amber-700">{fmtCurrency(totalDu)}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Échéancier Clients</h2>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary text-xs"><ArrowPathIcon className="h-4 w-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <PlusIcon className="h-4 w-4" /> Nouvelle échéance
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Client ID</label>
            <input value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Projet ID</label>
            <input value={form.projet_id} onChange={(e) => setForm({ ...form, projet_id: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Montant (DZD)</label>
            <input type="number" step="0.01" min="0.01" value={form.montant} onChange={(e) => setForm({ ...form, montant: e.target.value })} className="input-field" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Date échéance</label>
            <input type="date" value={form.date_echeance} onChange={(e) => setForm({ ...form, date_echeance: e.target.value })} className="input-field" required />
          </div>
          <div className="md:col-span-2 flex justify-end">
            <button type="submit" className="btn-primary text-xs">Enregistrer</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Client</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Projet</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Montant</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Échéance</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Paiement</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
              <th className="px-4 py-3 w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune échéance</td></tr>
            ) : (
              items.map((e) => (
                <tr key={e.id} className={`hover:bg-slate-50 ${e.statut === "IMPAYE" ? "bg-red-50/50" : ""}`}>
                  <td className="px-4 py-3">{e.client_nom || e.client_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3">{e.projet_nom || e.projet_id?.substring(0, 8)}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium">{fmtCurrency(e.montant)}</td>
                  <td className="px-4 py-3">{fmtDate(e.date_echeance)}</td>
                  <td className="px-4 py-3">{e.date_paiement ? fmtDate(e.date_paiement) : "—"}</td>
                  <td className="px-4 py-3"><Badge status={e.statut} /></td>
                  <td className="px-4 py-3">
                    {e.statut !== "REGLE" && (
                      <button onClick={() => handlePay(e.id)} className="btn-primary text-xs px-2 py-1">Payer</button>
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
