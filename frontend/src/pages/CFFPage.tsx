import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  CalculatorIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";

/* ── Types ────────────────────────────────────────── */
interface CFFImputation {
  associe_id: string;
  pourcentage: number;
  montant_impute: number;
}

interface CFFResult {
  entreprise_code: string;
  montant_facture: number;
  cff_tva: number;
  cff_ibs: number;
  cff_tap: number;
  cff_cnas: number;
  cff_timbre: number;
  cff_total: number;
  imputations: CFFImputation[];
}

interface CFFFacture {
  id: string;
  entreprise_id: string;
  periode: string;
  montant_facture_ht: number;
  cff_tva: number;
  cff_ibs: number;
  cff_tap: number;
  cff_cnas: number;
  cff_timbre: number;
  cff_total: number;
  created_at: string;
  entreprise_nom?: string;
}

interface KTResult {
  pass: boolean;
  details?: string;
  violations?: number;
}

type Tab = "calculer" | "factures" | "kill-tests";

function formatMoney(value: number | null | undefined) {
  if (value == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + " DA";
}

export default function CFFPage() {
  const [tab, setTab] = useState<Tab>("calculer");

  /* ── Calculate tab state ── */
  const [montant, setMontant] = useState("");
  const [entrepriseCode, setEntrepriseCode] = useState("");
  const [participations, setParticipations] = useState([
    { associe_id: "", pourcentage: "" },
  ]);
  const [calcResult, setCalcResult] = useState<CFFResult | null>(null);
  const [calcError, setCalcError] = useState("");
  const [calculating, setCalculating] = useState(false);

  /* ── Factures tab state ── */
  const [factures, setFactures] = useState<CFFFacture[]>([]);
  const [facturesLoading, setFacturesLoading] = useState(false);

  /* ── Kill tests tab state ── */
  const [ktResults, setKtResults] = useState<Record<string, KTResult>>({});
  const [ktLoading, setKtLoading] = useState(false);
  const [kt01Code, setKt01Code] = useState("SARL-DBPI");
  const [kt01Result, setKt01Result] = useState<{ pass: boolean; message: string } | null>(null);

  /* ── Handlers ── */
  const addParticipant = () => {
    setParticipations([...participations, { associe_id: "", pourcentage: "" }]);
  };

  const removeParticipant = (idx: number) => {
    setParticipations(participations.filter((_, i) => i !== idx));
  };

  const updateParticipant = (idx: number, field: "associe_id" | "pourcentage", value: string) => {
    const updated = [...participations];
    updated[idx] = { ...updated[idx], [field]: value };
    setParticipations(updated);
  };

  const handleCalculate = async () => {
    setCalcError("");
    setCalcResult(null);
    if (!montant || !entrepriseCode) {
      setCalcError("Montant et code entreprise requis.");
      return;
    }
    const totalPct = participations.reduce((s, p) => s + (parseFloat(p.pourcentage) || 0), 0);
    if (Math.abs(totalPct - 100) > 0.01) {
      setCalcError(`Total participations = ${totalPct.toFixed(2)}%. Doit = 100%.`);
      return;
    }
    setCalculating(true);
    try {
      const { data } = await api.post("/cff/calculer", {
        montant_facture_ht: parseFloat(montant),
        entreprise_code: entrepriseCode,
        participations: participations.map((p) => ({
          associe_id: p.associe_id,
          pourcentage: parseFloat(p.pourcentage),
        })),
      });
      setCalcResult(data);
    } catch (err: any) {
      setCalcError(err.response?.data?.detail || "Erreur de calcul CFF.");
    } finally {
      setCalculating(false);
    }
  };

  const fetchFactures = useCallback(async () => {
    setFacturesLoading(true);
    try {
      const { data } = await api.get("/cff/factures");
      setFactures(data);
    } catch {
      /* ignore */
    } finally {
      setFacturesLoading(false);
    }
  }, []);

  const fetchKillTests = useCallback(async () => {
    setKtLoading(true);
    try {
      const { data } = await api.get("/kt/kill-tests");
      setKtResults(data.tests || {});
    } catch {
      /* ignore */
    } finally {
      setKtLoading(false);
    }
  }, []);

  const verifyKT01 = async () => {
    try {
      const { data } = await api.get(`/cff/verifier-kt01/${encodeURIComponent(kt01Code)}`);
      setKt01Result(data);
    } catch (err: any) {
      setKt01Result({ pass: false, message: err.response?.data?.detail || "Erreur" });
    }
  };

  useEffect(() => {
    if (tab === "factures") fetchFactures();
    if (tab === "kill-tests") fetchKillTests();
  }, [tab, fetchFactures, fetchKillTests]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "calculer", label: "Calculer CFF" },
    { key: "factures", label: "Factures CFF" },
    { key: "kill-tests", label: "Kill Tests CFF" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Charges Fiscales & Financieres (CFF)</h1>
        <p className="mt-1 text-sm text-slate-500">
          Calcul TVA + IBS + TAP par entreprise, distribution par % entreprise (jamais % projet).
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Calculer Tab ── */}
      {tab === "calculer" && (
        <div className="card p-6 space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700">Montant Facture HT (DA)</label>
              <input
                type="number"
                value={montant}
                onChange={(e) => setMontant(e.target.value)}
                className="input-field mt-1"
                placeholder="1 000 000"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Code Entreprise</label>
              <input
                type="text"
                value={entrepriseCode}
                onChange={(e) => setEntrepriseCode(e.target.value)}
                className="input-field mt-1"
                placeholder="SARL-DP"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-700">
                Participations entreprise (% entreprise, PAS % projet)
              </label>
              <button onClick={addParticipant} className="btn-secondary text-xs">
                <PlusIcon className="h-4 w-4" /> Ajouter
              </button>
            </div>
            <div className="space-y-2">
              {participations.map((p, idx) => (
                <div key={idx} className="flex gap-3 items-center">
                  <input
                    type="text"
                    value={p.associe_id}
                    onChange={(e) => updateParticipant(idx, "associe_id", e.target.value)}
                    className="input-field flex-1"
                    placeholder="ID ou nom associe"
                  />
                  <input
                    type="number"
                    value={p.pourcentage}
                    onChange={(e) => updateParticipant(idx, "pourcentage", e.target.value)}
                    className="input-field w-28"
                    placeholder="%"
                    min="0"
                    max="100"
                  />
                  <span className="text-sm text-slate-400">%</span>
                  {participations.length > 1 && (
                    <button
                      onClick={() => removeParticipant(idx)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <XCircleIcon className="h-5 w-5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-2 text-xs text-amber-600">
              Important: utilisez les pourcentages ENTREPRISE (EntrepriseAssocie), jamais les parts projet.
            </p>
          </div>

          {calcError && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {calcError}
            </div>
          )}

          <button
            onClick={handleCalculate}
            disabled={calculating}
            className="btn-primary"
          >
            {calculating ? (
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
            ) : (
              <CalculatorIcon className="h-4 w-4" />
            )}
            Calculer CFF
          </button>

          {/* Result */}
          {calcResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                  <p className="text-xs text-blue-600">TVA (19%)</p>
                  <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_tva)}</p>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <p className="text-xs text-emerald-600">IBS (19% ou 26%)</p>
                  <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_ibs)}</p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-xs text-amber-600">TAP (2%)</p>
                  <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_tap)}</p>
                </div>
                {calcResult.cff_cnas > 0 && (
                  <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
                    <p className="text-xs text-orange-600">CNAS (26%)</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_cnas)}</p>
                  </div>
                )}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs text-slate-600">Timbre</p>
                  <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_timbre)}</p>
                </div>
                <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
                  <p className="text-xs text-violet-600">CFF Total</p>
                  <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(calcResult.cff_total)}</p>
                </div>
              </div>

              <div className="card p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Imputations par associe</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                      <th className="pb-2">Associe</th>
                      <th className="pb-2">% Entreprise</th>
                      <th className="pb-2 text-right">Montant impute</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calcResult.imputations.map((imp, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="py-2 font-medium text-slate-800">{imp.associe_id}</td>
                        <td className="py-2 text-slate-600">{imp.pourcentage}%</td>
                        <td className="py-2 text-right font-semibold text-slate-900">
                          {formatMoney(imp.montant_impute)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Factures Tab ── */}
      {tab === "factures" && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">Factures CFF enregistrees</h2>
            <button onClick={fetchFactures} className="btn-secondary text-xs">
              <ArrowPathIcon className="h-4 w-4" /> Actualiser
            </button>
          </div>
          {facturesLoading ? (
            <div className="flex items-center justify-center py-12">
              <ArrowPathIcon className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : factures.length === 0 ? (
            <p className="text-sm text-slate-400 py-8 text-center">Aucune facture CFF enregistree.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="pb-2">Entreprise</th>
                    <th className="pb-2">Periode</th>
                    <th className="pb-2 text-right">Montant HT</th>
                    <th className="pb-2 text-right">TVA</th>
                    <th className="pb-2 text-right">IBS</th>
                    <th className="pb-2 text-right">TAP</th>
                    <th className="pb-2 text-right">Timbre</th>
                    <th className="pb-2 text-right">CFF Total</th>
                    <th className="pb-2">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {factures.map((f) => (
                    <tr key={f.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2 font-medium text-slate-800">{f.entreprise_nom || f.entreprise_id}</td>
                      <td className="py-2 text-slate-600">{f.periode}</td>
                      <td className="py-2 text-right">{formatMoney(f.montant_facture_ht)}</td>
                      <td className="py-2 text-right">{formatMoney(f.cff_tva)}</td>
                      <td className="py-2 text-right">{formatMoney(f.cff_ibs)}</td>
                      <td className="py-2 text-right">{formatMoney(f.cff_tap)}</td>
                      <td className="py-2 text-right">{formatMoney(f.cff_timbre)}</td>
                      <td className="py-2 text-right font-semibold text-slate-900">{formatMoney(f.cff_total)}</td>
                      <td className="py-2 text-slate-500 text-xs">
                        {f.created_at ? new Date(f.created_at).toLocaleDateString("fr-FR") : "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Kill Tests CFF Tab ── */}
      {tab === "kill-tests" && (
        <div className="space-y-6">
          {/* KT-01 verification */}
          <div className="card p-6">
            <h2 className="text-base font-semibold text-slate-900 mb-4">KT-01: Yamina = 0% dans entreprises restreintes</h2>
            <p className="text-sm text-slate-500 mb-4">
              Yamina ne doit avoir aucune participation dans DBPI, OC, EP, SEN, BIM.
            </p>
            <div className="flex gap-3 items-end">
              <div>
                <label className="block text-xs font-medium text-slate-600">Code entreprise</label>
                <select
                  value={kt01Code}
                  onChange={(e) => setKt01Code(e.target.value)}
                  className="input-field mt-1"
                >
                  <option value="SARL-DBPI">SARL-DBPI</option>
                  <option value="SARL-OC">SARL-OC</option>
                  <option value="SARL-EP">SARL-EP</option>
                  <option value="SARL-SEN">SARL-SEN</option>
                  <option value="EURL-BIM">EURL-BIM</option>
                </select>
              </div>
              <button onClick={verifyKT01} className="btn-primary text-sm">Verifier KT-01</button>
            </div>
            {kt01Result && (
              <div className={`mt-4 rounded-lg p-3 flex items-center gap-2 ${
                kt01Result.pass
                  ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                  : "bg-red-50 border border-red-200 text-red-700"
              }`}>
                {kt01Result.pass ? (
                  <CheckCircleIcon className="h-5 w-5" />
                ) : (
                  <XCircleIcon className="h-5 w-5" />
                )}
                <span className="text-sm font-medium">{kt01Result.message}</span>
              </div>
            )}
          </div>

          {/* All KT results */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-900">Resultats Kill Tests</h2>
              <button onClick={fetchKillTests} className="btn-secondary text-xs" disabled={ktLoading}>
                <ArrowPathIcon className={`h-4 w-4 ${ktLoading ? "animate-spin" : ""}`} /> Actualiser
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {Object.entries(ktResults).sort().map(([key, result]) => (
                <div
                  key={key}
                  className={`rounded-xl border p-4 ${
                    result.pass
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-red-200 bg-red-50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {result.pass ? (
                      <CheckCircleIcon className="h-5 w-5 text-emerald-600" />
                    ) : (
                      <XCircleIcon className="h-5 w-5 text-red-600" />
                    )}
                    <span className="text-sm font-bold text-slate-900">{key}</span>
                    <span className={`ml-auto text-xs font-semibold ${result.pass ? "text-emerald-600" : "text-red-600"}`}>
                      {result.pass ? "PASS" : "FAIL"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    {typeof result.details === "string" ? result.details : JSON.stringify(result.details || "")}
                  </p>
                  {result.violations !== undefined && (
                    <p className="mt-1 text-xs font-medium text-red-600">
                      {result.violations} violation(s)
                    </p>
                  )}
                </div>
              ))}
              {Object.keys(ktResults).length === 0 && !ktLoading && (
                <p className="text-sm text-slate-400 col-span-full text-center py-4">
                  Cliquez sur Actualiser pour lancer les kill tests.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
