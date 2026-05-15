import { useState, useCallback } from "react";
import api from "../api/client";
import {
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  BeakerIcon,
  ScaleIcon,
} from "@heroicons/react/24/outline";

/* ── Types ────────────────────────────────────────── */
interface CheckResult {
  pass: boolean | null;
  value?: number | string;
  expected?: number | string;
  details?: string | string[];
  violations?: number;
  actual?: number;
  ecart?: number;
}

interface SanityResponse {
  sanity_pass: boolean;
  checks: Record<string, CheckResult>;
}

interface KillTestsResponse {
  kill_tests_pass: boolean;
  tests: Record<string, CheckResult>;
}

interface VSRBalance {
  pass: boolean | null;
  actual?: number;
  expected: number;
  ecart?: number;
  details?: string;
}

interface VSRResponse {
  vsr01_pass: boolean;
  balances: Record<string, VSRBalance>;
}

type Tab = "sanity" | "kill-tests" | "vsr" | "detection";

function formatMoney(value: number | null | undefined) {
  if (value == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + " DA";
}

function StatusIcon({ pass }: { pass: boolean | null }) {
  if (pass === null) return <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" />;
  return pass
    ? <CheckCircleIcon className="h-5 w-5 text-emerald-600" />
    : <XCircleIcon className="h-5 w-5 text-red-600" />;
}

function StatusBadge({ pass }: { pass: boolean | null }) {
  if (pass === null) return <span className="badge-info text-xs">N/A</span>;
  return pass
    ? <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">PASS</span>
    : <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">FAIL</span>;
}

export default function KillTestsPage() {
  const [tab, setTab] = useState<Tab>("sanity");
  const [loading, setLoading] = useState(false);

  const [sanity, setSanity] = useState<SanityResponse | null>(null);
  const [killTests, setKillTests] = useState<KillTestsResponse | null>(null);
  const [vsr, setVsr] = useState<VSRResponse | null>(null);

  const fetchSanity = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/kt/sanity");
      setSanity(data);
    } catch {
      setSanity(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchKillTests = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/kt/kill-tests");
      setKillTests(data);
    } catch {
      setKillTests(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchVSR = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/kt/vsr");
      setVsr(data);
    } catch {
      setVsr(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const runAll = async () => {
    setLoading(true);
    try {
      const [s, k, v] = await Promise.allSettled([
        api.get("/kt/sanity"),
        api.get("/kt/kill-tests"),
        api.get("/kt/vsr"),
      ]);
      if (s.status === "fulfilled") setSanity(s.value.data);
      if (k.status === "fulfilled") setKillTests(k.value.data);
      if (v.status === "fulfilled") setVsr(v.value.data);
    } finally {
      setLoading(false);
    }
  };

  const tabs: { key: Tab; label: string; icon: typeof ShieldCheckIcon }[] = [
    { key: "sanity", label: "Sanity Checks", icon: ShieldCheckIcon },
    { key: "kill-tests", label: "Kill Tests KT-01..10", icon: BeakerIcon },
    { key: "detection", label: "D\u00e9tection (15 patterns)", icon: ExclamationTriangleIcon },
    { key: "vsr", label: "VSR Soldes Ref.", icon: ScaleIcon },
  ];

  const overallPass = (sanity?.sanity_pass ?? true) && (killTests?.kill_tests_pass ?? true) && (vsr?.vsr01_pass ?? true);
  const hasData = sanity || killTests || vsr;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Kill Tests & Sante Systeme</h1>
          <p className="mt-1 text-sm text-slate-500">
            Verification des invariants GFI v7.0 : P1 sanity, KT-01 a KT-09, VSR soldes de reference.
          </p>
        </div>
        <button onClick={runAll} disabled={loading} className="btn-primary">
          {loading ? <ArrowPathIcon className="h-4 w-4 animate-spin" /> : <BeakerIcon className="h-4 w-4" />}
          Lancer tout
        </button>
      </div>

      {/* Global status banner */}
      {hasData && (
        <div className={`rounded-xl border-2 p-4 flex items-center gap-3 ${
          overallPass
            ? "border-emerald-300 bg-emerald-50"
            : "border-red-300 bg-red-50"
        }`}>
          {overallPass ? (
            <CheckCircleIcon className="h-8 w-8 text-emerald-600" />
          ) : (
            <XCircleIcon className="h-8 w-8 text-red-600" />
          )}
          <div>
            <p className={`text-lg font-bold ${overallPass ? "text-emerald-800" : "text-red-800"}`}>
              {overallPass ? "Tous les tests passent" : "Des echecs ont ete detectes"}
            </p>
            <p className="text-sm text-slate-600">
              Sanity: {sanity ? (sanity.sanity_pass ? "OK" : "FAIL") : "\u2014"} |
              Kill Tests: {killTests ? (killTests.kill_tests_pass ? "OK" : "FAIL") : "\u2014"} |
              VSR: {vsr ? (vsr.vsr01_pass ? "OK" : "FAIL") : "\u2014"}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Sanity Tab ── */}
      {tab === "sanity" && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">P1 Sanity Checks</h2>
            <button onClick={fetchSanity} className="btn-secondary text-xs" disabled={loading}>
              <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Lancer
            </button>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            Verification des comptages de reference : 9 associes, 12 projets, 15 roles, META_AUTO_DEPLOY=FALSE.
          </p>

          {!sanity ? (
            <p className="text-sm text-slate-400 text-center py-8">Cliquez "Lancer" pour executer les verifications.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(sanity.checks).map(([key, check]) => (
                <div
                  key={key}
                  className={`flex items-center justify-between rounded-xl border p-4 ${
                    check.pass ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <StatusIcon pass={check.pass} />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{key.replace(/_/g, " ")}</p>
                      <p className="text-xs text-slate-600">
                        Valeur: <span className="font-mono font-semibold">{String(check.value)}</span>
                        {check.expected !== undefined && (
                          <> | Attendu: <span className="font-mono font-semibold">{String(check.expected)}</span></>
                        )}
                      </p>
                    </div>
                  </div>
                  <StatusBadge pass={check.pass} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Kill Tests Tab ── */}
      {tab === "kill-tests" && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">Kill Tests KT-01 a KT-09</h2>
            <button onClick={fetchKillTests} className="btn-secondary text-xs" disabled={loading}>
              <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Lancer
            </button>
          </div>

          <div className="mb-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600 space-y-1">
            <p><strong>KT-01:</strong> Yamina = 0% dans DBPI/OC/EP/SEN/BIM</p>
            <p><strong>KT-02:</strong> Ahmed = 25% entreprise, PAS 60% projet</p>
            <p><strong>KT-03:</strong> CFF utilise % entreprise, jamais % projet</p>
            <p><strong>KT-04:</strong> Tolerance double calcul = 0.00 DA strict</p>
            <p><strong>KT-05:</strong> Pas de sortie cash 512 pour avances materiel</p>
            <p><strong>KT-06:</strong> Coherence inter-projets</p>
            <p><strong>KT-07:</strong> Integrite des flux</p>
            <p><strong>KT-08:</strong> Blocage retrait &gt; solde disponible</p>
            <p><strong>KT-09:</strong> Somme parts apres cession = 100%</p>
          </div>

          {!killTests ? (
            <p className="text-sm text-slate-400 text-center py-8">Cliquez "Lancer" pour executer les kill tests.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {Object.entries(killTests.tests).sort().map(([key, test]) => (
                <div
                  key={key}
                  className={`rounded-xl border p-4 ${
                    test.pass ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <StatusIcon pass={test.pass} />
                      <span className="text-sm font-bold text-slate-900">{key}</span>
                    </div>
                    <StatusBadge pass={test.pass} />
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    {typeof test.details === "string"
                      ? test.details
                      : Array.isArray(test.details)
                        ? test.details.join(", ")
                        : "Valide par le service layer"}
                  </p>
                  {test.violations !== undefined && test.violations > 0 && (
                    <p className="mt-1 text-xs font-semibold text-red-600">
                      {test.violations} violation(s) detectee(s)
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── VSR Tab ── */}
      {tab === "vsr" && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">VSR-01 : Soldes de Reference</h2>
            <button onClick={fetchVSR} className="btn-secondary text-xs" disabled={loading}>
              <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Lancer
            </button>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            Verification des soldes CCA de reference pour les associes principaux.
          </p>

          {!vsr ? (
            <p className="text-sm text-slate-400 text-center py-8">Cliquez "Lancer" pour verifier les soldes.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="pb-3">Associe</th>
                    <th className="pb-3 text-right">Solde attendu</th>
                    <th className="pb-3 text-right">Solde actuel</th>
                    <th className="pb-3 text-right">Ecart</th>
                    <th className="pb-3 text-center">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(vsr.balances).map(([name, bal]) => (
                    <tr key={name} className="border-b border-slate-100">
                      <td className="py-3 font-semibold text-slate-900">{name}</td>
                      <td className="py-3 text-right font-mono">{formatMoney(bal.expected)}</td>
                      <td className="py-3 text-right font-mono">
                        {bal.actual !== undefined ? formatMoney(bal.actual) : (
                          <span className="text-slate-400">{bal.details || "Non trouve"}</span>
                        )}
                      </td>
                      <td className={`py-3 text-right font-mono font-semibold ${
                        bal.ecart && bal.ecart !== 0 ? "text-red-600" : "text-emerald-600"
                      }`}>
                        {bal.ecart !== undefined ? formatMoney(bal.ecart) : "\u2014"}
                      </td>
                      <td className="py-3 text-center">
                        <StatusBadge pass={bal.pass} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Detection Tab (Section 16) ── */}
      {tab === "detection" && <DetectionTab />}
    </div>
  );
}


/* ── Detection Engine — 15 Patterns (Section 16) ── */
function DetectionTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const { data: d } = await api.get("/detection/scan");
      setData(d);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Moteur de D&eacute;tection — 15 Patterns (Section 16)</h2>
          <p className="text-sm text-slate-500">Scan autonome de la base de donn&eacute;es</p>
        </div>
        <button onClick={run} disabled={loading} className="btn-primary text-sm flex items-center gap-2">
          <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Scan en cours\u2026" : "Lancer le scan"}
        </button>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="rounded-lg bg-slate-50 p-4 text-center">
              <p className="text-2xl font-bold text-slate-800">{data.total_patterns}</p>
              <p className="text-xs text-slate-500">Patterns analys&eacute;s</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-4 text-center border border-amber-200">
              <p className="text-2xl font-bold text-amber-700">{data.alertes}</p>
              <p className="text-xs text-amber-600">Alertes</p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-4 text-center border border-emerald-200">
              <p className="text-2xl font-bold text-emerald-700">{data.ok}</p>
              <p className="text-xs text-emerald-600">OK</p>
            </div>
          </div>

          <div className="space-y-2">
            {data.patterns.map((p: any) => (
              <div key={p.id} className={`rounded-lg border p-3 ${
                p.statut === "ALERTE" ? "border-amber-200 bg-amber-50" :
                p.statut === "ERREUR" ? "border-red-200 bg-red-50" :
                "border-emerald-200 bg-emerald-50"
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold bg-white/60 px-2 py-0.5 rounded">#{p.id}</span>
                    <span className="font-medium text-sm text-slate-800">{p.nom}</span>
                    <span className="text-xs text-slate-500">{p.description}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.count > 0 && <span className="text-xs font-bold text-amber-700">{p.count}</span>}
                    {p.statut === "OK" && <CheckCircleIcon className="h-5 w-5 text-emerald-500" />}
                    {p.statut === "ALERTE" && <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" />}
                    {p.statut === "ERREUR" && <XCircleIcon className="h-5 w-5 text-red-500" />}
                  </div>
                </div>
                {p.items?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {p.items.map((item: any, i: number) => (
                      <p key={i} className="text-xs text-slate-600 pl-8">{item.detail}</p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
