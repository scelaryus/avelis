import { useState, useEffect } from "react";
import api from "../api/client";

interface Workflow {
  code: string;
  titre: string;
  description: string;
  entites: string[];
  projets: string[];
  exigence: string;
  actions_attendues: string[];
  montant?: number;
  categorie_cc: string;
  statut: string;
  progress: number;
  transactions_count: number;
  transactions_montant: number;
  journal_entries_count: number;
}

interface Summary {
  total: number;
  termine: number;
  en_cours: number;
  non_demarre: number;
  completion_pct: number;
}

const STATUT_CONFIG: Record<string, { bg: string; text: string; label: string; icon: string }> = {
  TERMINE: { bg: "bg-emerald-100", text: "text-emerald-800", label: "Termin\u00e9", icon: "\u2713" },
  EN_COURS: { bg: "bg-amber-100", text: "text-amber-800", label: "En cours", icon: "\u25B6" },
  NON_DEMARRE: { bg: "bg-slate-100", text: "text-slate-600", label: "Non d\u00e9marr\u00e9", icon: "\u25CB" },
};

const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(Math.round(n));

export default function WorkflowsDendaniPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/workflows-dendani/"),
      api.get("/workflows-dendani/summary"),
    ]).then(([wRes, sRes]) => {
      setWorkflows(wRes.data || []);
      setSummary(sRes.data || null);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
      </div>
    );
  }

  const selectedWf = workflows.find((w) => w.code === selected);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">
        Workflows M&eacute;tier Dendani
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Section 13 &mdash; 8 workflows historiques sp&eacute;cifiques au Groupe Dendani &agrave; assainir et tracer
      </p>

      {/* ── Summary cards ── */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="card p-4 text-center">
            <p className="text-3xl font-bold text-slate-800">{summary.total}</p>
            <p className="text-xs text-slate-500 mt-1">Workflows total</p>
          </div>
          <div className="card p-4 text-center border-2 border-emerald-200">
            <p className="text-3xl font-bold text-emerald-700">{summary.termine}</p>
            <p className="text-xs text-emerald-600 mt-1">Termin&eacute;s</p>
          </div>
          <div className="card p-4 text-center border-2 border-amber-200">
            <p className="text-3xl font-bold text-amber-700">{summary.en_cours}</p>
            <p className="text-xs text-amber-600 mt-1">En cours</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-3xl font-bold text-slate-400">{summary.non_demarre}</p>
            <p className="text-xs text-slate-500 mt-1">Non d&eacute;marr&eacute;s</p>
          </div>
          <div className="card p-4 text-center">
            <div className="relative w-16 h-16 mx-auto">
              <svg viewBox="0 0 36 36" className="w-16 h-16">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none" stroke="#e2e8f0" strokeWidth="3" />
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none" stroke="#0d9488" strokeWidth="3"
                  strokeDasharray={`${summary.completion_pct}, 100`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-teal-700">
                {summary.completion_pct}%
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Progression</p>
          </div>
        </div>
      )}

      {/* ── Workflow cards grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {workflows.map((wf) => {
          const cfg = STATUT_CONFIG[wf.statut] || STATUT_CONFIG.NON_DEMARRE;
          return (
            <button
              key={wf.code}
              onClick={() => setSelected(selected === wf.code ? null : wf.code)}
              className={`text-left card p-5 border-2 transition-all hover:shadow-md ${
                selected === wf.code
                  ? "border-teal-500 ring-2 ring-teal-200"
                  : "border-transparent hover:border-slate-200"
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-teal-600 bg-teal-50 px-2 py-0.5 rounded">
                    {wf.code}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${cfg.bg} ${cfg.text}`}>
                    {cfg.icon} {cfg.label}
                  </span>
                </div>
                <span className="text-xs text-slate-400 font-mono">{wf.exigence}</span>
              </div>

              <h3 className="font-semibold text-slate-900 text-sm mb-1">{wf.titre}</h3>
              <p className="text-xs text-slate-500 mb-3 line-clamp-2">{wf.description}</p>

              {/* Progress bar */}
              <div className="mb-3">
                <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                  <span>Progression</span>
                  <span className="font-medium">{wf.progress}%</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      wf.progress >= 100 ? "bg-emerald-500" : wf.progress > 0 ? "bg-amber-400" : "bg-slate-200"
                    }`}
                    style={{ width: `${Math.max(wf.progress, 2)}%` }}
                  />
                </div>
              </div>

              {/* Metrics */}
              <div className="flex items-center gap-4 text-[10px] text-slate-400">
                <span>{wf.transactions_count} transaction(s)</span>
                {wf.transactions_montant > 0 && <span>{fmt(wf.transactions_montant)} DA</span>}
                <span>{wf.journal_entries_count} &eacute;criture(s)</span>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1 mt-2">
                {wf.entites.map((e) => (
                  <span key={e} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">{e}</span>
                ))}
                {wf.projets.map((p) => (
                  <span key={p} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600">{p}</span>
                ))}
              </div>
            </button>
          );
        })}
      </div>

      {/* ── Detail panel ── */}
      {selectedWf && (
        <div className="card p-6 border-2 border-teal-100">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <span className="text-xs font-mono bg-teal-50 text-teal-600 px-2 py-0.5 rounded">{selectedWf.code}</span>
                {selectedWf.titre}
              </h2>
              <p className="text-sm text-slate-500 mt-1">{selectedWf.exigence}</p>
            </div>
            <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600 text-xl">&times;</button>
          </div>

          <p className="text-sm text-slate-600 mb-4">{selectedWf.description}</p>

          {selectedWf.montant && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 mb-4">
              <p className="text-sm text-amber-800">
                <strong>Montant concern&eacute; :</strong> {fmt(selectedWf.montant)} DA
              </p>
            </div>
          )}

          {/* Actions checklist */}
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Actions &agrave; r&eacute;aliser</h3>
          <div className="space-y-2 mb-4">
            {selectedWf.actions_attendues.map((action, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${
                  selectedWf.statut === "TERMINE"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-400"
                }`}>
                  {selectedWf.statut === "TERMINE" ? "\u2713" : (i + 1)}
                </span>
                <span className="text-slate-700">{action}</span>
              </div>
            ))}
          </div>

          {/* Data status */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-slate-800">{selectedWf.transactions_count}</p>
              <p className="text-[10px] text-slate-500">Transactions</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-slate-800">{selectedWf.journal_entries_count}</p>
              <p className="text-[10px] text-slate-500">&Eacute;critures comptables</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-teal-700">{fmt(selectedWf.transactions_montant)} DA</p>
              <p className="text-[10px] text-slate-500">Montant trac&eacute;</p>
            </div>
          </div>

          {/* Links */}
          <div className="flex flex-wrap gap-2">
            <span className="text-xs text-slate-500">Entit&eacute;s :</span>
            {selectedWf.entites.map((e) => (
              <span key={e} className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-medium">{e}</span>
            ))}
            {selectedWf.projets.length > 0 && (
              <>
                <span className="text-xs text-slate-500 ml-2">Projets :</span>
                {selectedWf.projets.map((p) => (
                  <span key={p} className="text-xs px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-medium">{p}</span>
                ))}
              </>
            )}
            <span className="text-xs text-slate-500 ml-2">CC :</span>
            <span className="text-xs px-2 py-0.5 rounded bg-teal-50 text-teal-700 font-mono">{selectedWf.categorie_cc}</span>
          </div>
        </div>
      )}
    </div>
  );
}
