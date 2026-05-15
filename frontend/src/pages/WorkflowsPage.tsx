import { useState, useEffect, useCallback } from "react";
import api from "../api/client";
import {
  PlayIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";

interface Workflow {
  id: string;
  graph_type: string;
  status: string;
  doc_ids: string[];
  blocking_reasons: string[];
  errors: string[];
  warnings: string[];
  created_at: string;
  updated_at: string;
}

const STATUS_STYLES: Record<string, { cls: string; label: string; Icon: any }> = {
  CREATED: { cls: "badge-neutral", label: "Créé", Icon: ClockIcon },
  RUNNING: { cls: "badge-info", label: "En cours", Icon: ArrowPathIcon },
  BLOCKED: { cls: "badge-warning", label: "Bloqué", Icon: ExclamationTriangleIcon },
  READY_TO_COMMIT: { cls: "badge-info", label: "Prêt", Icon: CheckCircleIcon },
  COMMITTED: { cls: "badge-success", label: "Validé", Icon: CheckCircleIcon },
  REJECTED: { cls: "badge-danger", label: "Rejeté", Icon: XCircleIcon },
  FAILED: { cls: "badge-danger", label: "Échoué", Icon: XCircleIcon },
};

const GRAPH_LABELS: Record<string, string> = {
  document_to_ledger: "Document → Grand Livre",
  adv: "Administration des Ventes",
  hr: "Ressources Humaines",
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [selectedWf, setSelectedWf] = useState<Workflow | null>(null);

  // Create form
  const [graphType, setGraphType] = useState("document_to_ledger");
  const [docIdsInput, setDocIdsInput] = useState("");

  const fetchWorkflows = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/workflows/");
      setWorkflows(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const doc_ids = docIdsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await api.post("/workflows/", { graph_type: graphType, doc_ids });
      setDocIdsInput("");
      await fetchWorkflows();
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (id: string) => {
    await api.post(`/workflows/${id}/run`);
    await fetchWorkflows();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Workflows</h1>
          <p className="text-sm text-slate-500 mt-1">Orchestration & pipelines agentic</p>
        </div>
      </div>

      {/* Create form */}
      <div className="card p-5 mb-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Nouveau workflow</h2>
        <form onSubmit={handleCreate} className="flex items-end gap-4">
          <div className="w-56">
            <label className="block text-xs font-medium text-slate-500 mb-1">Type de graphe</label>
            <select value={graphType} onChange={(e) => setGraphType(e.target.value)} className="input-field">
              <option value="document_to_ledger">Document → Grand Livre</option>
              <option value="adv">ADV</option>
              <option value="hr">RH</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">
              IDs documents (séparés par virgule)
            </label>
            <input
              value={docIdsInput}
              onChange={(e) => setDocIdsInput(e.target.value)}
              className="input-field"
              placeholder="uuid1, uuid2, …"
            />
          </div>
          <button type="submit" disabled={creating} className="btn-primary">
            <PlayIcon className="h-4 w-4" />
            Créer
          </button>
        </form>
      </div>

      <div className="flex gap-6">
        {/* List */}
        <div className="flex-1">
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Graphe</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Statut</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Docs</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Date</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-slate-400">Chargement…</td>
                  </tr>
                ) : workflows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-slate-400">Aucun workflow</td>
                  </tr>
                ) : (
                  workflows.map((wf) => {
                    const style = STATUS_STYLES[wf.status] ?? STATUS_STYLES.CREATED;
                    return (
                      <tr
                        key={wf.id}
                        className={`hover:bg-slate-50 cursor-pointer transition-colors ${selectedWf?.id === wf.id ? "bg-blue-50" : ""}`}
                        onClick={() => setSelectedWf(wf)}
                      >
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {GRAPH_LABELS[wf.graph_type] ?? wf.graph_type}
                        </td>
                        <td className="px-4 py-3">
                          <span className={style.cls}>
                            <style.Icon className="mr-1 h-3 w-3 inline" />
                            {style.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{wf.doc_ids?.length ?? 0}</td>
                        <td className="px-4 py-3 text-slate-600">
                          {new Date(wf.created_at).toLocaleDateString("fr-FR")}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {(wf.status === "CREATED" || wf.status === "BLOCKED") && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRun(wf.id);
                              }}
                              className="btn-primary text-xs px-3 py-1"
                            >
                              <PlayIcon className="h-3 w-3" /> Exécuter
                            </button>
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

        {/* Detail panel */}
        {selectedWf && (
          <div className="w-96 shrink-0 card p-5 space-y-4 self-start">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Détails</h2>
              <button onClick={() => setSelectedWf(null)} className="text-sm text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-slate-500">ID</dt>
                <dd className="font-mono text-xs break-all">{selectedWf.id}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Graphe</dt>
                <dd className="font-medium">{GRAPH_LABELS[selectedWf.graph_type] ?? selectedWf.graph_type}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Statut</dt>
                <dd>
                  <span className={STATUS_STYLES[selectedWf.status]?.cls ?? "badge-neutral"}>
                    {STATUS_STYLES[selectedWf.status]?.label ?? selectedWf.status}
                  </span>
                </dd>
              </div>
            </dl>

            {selectedWf.blocking_reasons?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-amber-700 mb-1">Raisons de blocage</h3>
                <ul className="space-y-1">
                  {selectedWf.blocking_reasons.map((r, i) => (
                    <li key={i} className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1">{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {selectedWf.errors?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-red-700 mb-1">Erreurs</h3>
                <ul className="space-y-1">
                  {selectedWf.errors.map((r, i) => (
                    <li key={i} className="text-xs text-red-600 bg-red-50 rounded px-2 py-1">{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {selectedWf.warnings?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-amber-700 mb-1">Avertissements</h3>
                <ul className="space-y-1">
                  {selectedWf.warnings.map((r, i) => (
                    <li key={i} className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1">{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
