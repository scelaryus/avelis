import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";

interface ImportSession {
  id: string;
  source_type: string;
  source_path?: string;
  processing_mode: string;
  nombre_fichiers: number;
  fichiers_traites: number;
  fichiers_erreur: number;
  fichiers_dupliques: number;
  statut: string;
  resultats?: FileResult[];
  erreurs?: { code: string; message: string }[];
  date_import?: string;
  completed_at?: string;
}

interface FileResult {
  filename: string;
  doc_id?: string;
  workflow_id?: string;
  workflow_status?: string;
  status: string;
  doc_type?: string;
  routed_to?: string;
  confidence?: number;
  created_record_ids?: string[];
  journal_entry_ids?: string[];
  error?: string;
}

interface GDriveItem {
  id: string;
  name: string;
  mimeType: string;
  size: number;
}

interface GDriveListing {
  folder_id: string;
  folders: GDriveItem[];
  files: GDriveItem[];
}

const STATUS_COLORS: Record<string, string> = {
  EN_COURS: "bg-yellow-100 text-yellow-800",
  TERMINE: "bg-green-100 text-green-800",
  ERREUR: "bg-red-100 text-red-800",
  PARTIEL: "bg-orange-100 text-orange-800",
};

const FILE_STATUS_COLORS: Record<string, string> = {
  OK: "text-green-600",
  INGESTED: "text-blue-600",
  DUPLICATE: "text-yellow-600",
  ERROR: "text-red-600",
};

const MODULE_LABELS: Record<string, string> = {
  comptabilite: "Comptabilité",
  adv: "ADV",
  hr: "RH",
  documents: "Documents",
};

export default function ImportPage() {
  const [sessions, setSessions] = useState<ImportSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedSession, setSelectedSession] = useState<ImportSession | null>(null);
  const [tab, setTab] = useState<"upload" | "gdrive" | "sessions">("upload");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Google Drive state
  const [gdriveConnected, setGdriveConnected] = useState(false);
  const [gdriveEmail, setGdriveEmail] = useState<string>("");
  const [gdriveBrowse, setGdriveBrowse] = useState<GDriveListing | null>(null);
  const [gdrivePath, setGdrivePath] = useState<{ id: string; name: string }[]>([
    { id: "root", name: "Mon Drive" },
  ]);
  const [gdriveLoading, setGdriveLoading] = useState(false);

  // Drag & drop
  const [dragActive, setDragActive] = useState(false);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await api.get("/imports/import-sessions");
      setSessions(res.data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    checkGdriveStatus();
  }, [fetchSessions]);

  // Poll active sessions
  useEffect(() => {
    const active = sessions.some((s) => s.statut === "EN_COURS");
    if (!active) return;
    const interval = setInterval(fetchSessions, 3000);
    return () => clearInterval(interval);
  }, [sessions, fetchSessions]);

  const checkGdriveStatus = async () => {
    try {
      const res = await api.get("/imports/google-drive/status");
      setGdriveConnected(res.data.connected);
      setGdriveEmail(res.data.email || "");
    } catch {
      setGdriveConnected(false);
    }
  };

  // ── Upload handlers ──────────────────────────────────

  const handleUpload = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    if (!files.length) return;

    setUploading(true);
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    try {
      const res = await api.post("/imports/import-sessions/upload?processing_mode=FULL_AUTO", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 300000, // 5 min for large batches
      });
      setSessions((prev) => [res.data, ...prev]);
      setTab("sessions");
      setSelectedSession(res.data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files) handleUpload(e.dataTransfer.files);
  };

  // ── Google Drive handlers ────────────────────────────

  const connectGdrive = async () => {
    try {
      const res = await api.get("/imports/google-drive/auth-url");
      window.open(res.data.auth_url, "_blank", "width=600,height=700");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to get auth URL");
    }
  };

  const browseFolder = async (folderId: string) => {
    setGdriveLoading(true);
    try {
      const res = await api.get(`/imports/google-drive/browse?folder_id=${folderId}`);
      setGdriveBrowse(res.data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Browse failed");
    } finally {
      setGdriveLoading(false);
    }
  };

  const navigateFolder = (folder: GDriveItem) => {
    setGdrivePath((prev) => [...prev, { id: folder.id, name: folder.name }]);
    browseFolder(folder.id);
  };

  const navigateBack = (index: number) => {
    const newPath = gdrivePath.slice(0, index + 1);
    setGdrivePath(newPath);
    browseFolder(newPath[newPath.length - 1].id);
  };

  const importGdriveFolder = async () => {
    const current = gdrivePath[gdrivePath.length - 1];
    setUploading(true);
    try {
      const res = await api.post("/imports/import-sessions/google-drive?processing_mode=FULL_AUTO", {
        folder_id: current.id,
        folder_name: current.name,
      });
      setSessions((prev) => [res.data, ...prev]);
      setTab("sessions");
      setSelectedSession(res.data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Import failed");
    } finally {
      setUploading(false);
    }
  };

  const disconnectGdrive = async () => {
    try {
      await api.delete("/imports/google-drive/disconnect");
      setGdriveConnected(false);
      setGdriveEmail("");
      setGdriveBrowse(null);
    } catch { /* ignore */ }
  };

  // ── Session detail ──────────────────────────────────

  const refreshSession = async (id: string) => {
    try {
      const res = await api.get(`/imports/import-sessions/${id}`);
      setSelectedSession(res.data);
      setSessions((prev) => prev.map((s) => (s.id === id ? res.data : s)));
    } catch { /* ignore */ }
  };

  // ── Render ──────────────────────────────────────────

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">
            Importez des fichiers depuis votre PC ou Google Drive. L'IA classifie, extrait et route automatiquement.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1">
        {[
          { key: "upload" as const, label: "📁 Import PC" },
          { key: "gdrive" as const, label: "☁️ Google Drive" },
          { key: "sessions" as const, label: `📋 Sessions (${sessions.length})` },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-teal-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Upload Tab */}
      {tab === "upload" && (
        <div className="space-y-6">
          {/* Drop Zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
              dragActive
                ? "border-teal-500 bg-teal-50"
                : "border-slate-300 bg-white hover:border-teal-400 hover:bg-slate-50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
              className="hidden"
              onChange={(e) => e.target.files && handleUpload(e.target.files)}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
                <p className="text-lg font-medium text-teal-700">Importation en cours...</p>
                <p className="text-sm text-slate-500">Classification IA et stockage des fichiers</p>
              </div>
            ) : (
              <>
                <div className="mb-4 text-5xl">📂</div>
                <p className="text-lg font-medium text-slate-700">
                  Glissez vos fichiers ici ou cliquez pour sélectionner
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  PDF, PNG, JPG, TIFF — Max 500 fichiers, {100}MB par fichier
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  L'IA classifiera automatiquement chaque document et l'acheminera vers le bon module
                </p>
              </>
            )}
          </div>

          {/* Process Info */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            {[
              { step: "1", title: "Upload & Classement", desc: "L'IA identifie le type de chaque document" },
              { step: "2", title: "OCR & Extraction", desc: "Extraction des montants, dates, références" },
              { step: "3", title: "Vérification", desc: "Contrôle arithmétique HT+TVA=TTC" },
              { step: "4", title: "Routage Module", desc: "Auto-création dans ADV, Comptabilité ou RH" },
            ].map((item) => (
              <div key={item.step} className="rounded-lg border bg-white p-4">
                <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-teal-100 text-sm font-bold text-teal-700">
                  {item.step}
                </div>
                <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                <p className="mt-1 text-xs text-slate-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Google Drive Tab */}
      {tab === "gdrive" && (
        <div className="space-y-6">
          {/* Connection status */}
          <div className="flex items-center justify-between rounded-lg border bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="text-3xl">☁️</div>
              <div>
                <h3 className="font-semibold text-slate-900">Google Drive</h3>
                <p className="text-sm text-slate-500">
                  {gdriveConnected
                    ? `Connecté — ${gdriveEmail}`
                    : "Non connecté"}
                </p>
              </div>
            </div>
            {gdriveConnected ? (
              <div className="flex gap-2">
                <button
                  onClick={() => browseFolder(gdrivePath[gdrivePath.length - 1].id)}
                  className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
                >
                  Parcourir
                </button>
                <button
                  onClick={disconnectGdrive}
                  className="rounded-lg border px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  Déconnecter
                </button>
              </div>
            ) : (
              <button
                onClick={connectGdrive}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Connecter Google Drive
              </button>
            )}
          </div>

          {/* Folder browser */}
          {gdriveConnected && gdriveBrowse && (
            <div className="rounded-lg border bg-white">
              {/* Breadcrumb */}
              <div className="flex items-center gap-1 border-b px-4 py-3 text-sm">
                {gdrivePath.map((p, i) => (
                  <span key={p.id} className="flex items-center gap-1">
                    {i > 0 && <span className="text-slate-400">/</span>}
                    <button
                      onClick={() => navigateBack(i)}
                      className="text-teal-600 hover:underline"
                    >
                      {p.name}
                    </button>
                  </span>
                ))}
              </div>

              {/* Folders */}
              {gdriveBrowse.folders.length > 0 && (
                <div className="border-b">
                  {gdriveBrowse.folders.map((folder) => (
                    <button
                      key={folder.id}
                      onClick={() => navigateFolder(folder)}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-50"
                    >
                      <span className="text-lg">📁</span>
                      <span className="text-slate-900">{folder.name}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Files */}
              {gdriveBrowse.files.length > 0 && (
                <div className="max-h-64 overflow-y-auto">
                  {gdriveBrowse.files.map((file) => (
                    <div key={file.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                      <span className="text-lg">📄</span>
                      <span className="flex-1 text-slate-700">{file.name}</span>
                      <span className="text-xs text-slate-400">
                        {(file.size / 1024).toFixed(0)} KB
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Import button */}
              <div className="flex items-center justify-between border-t px-4 py-3">
                <span className="text-sm text-slate-500">
                  {gdriveBrowse.files.length} fichier(s) importable(s)
                </span>
                <button
                  onClick={importGdriveFolder}
                  disabled={uploading || gdriveBrowse.files.length === 0}
                  className="rounded-lg bg-teal-600 px-6 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                >
                  {uploading ? "Importation..." : "Importer ce dossier"}
                </button>
              </div>
            </div>
          )}

          {gdriveLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
            </div>
          )}
        </div>
      )}

      {/* Sessions Tab */}
      {tab === "sessions" && (
        <div className="space-y-4">
          {/* Session detail overlay */}
          {selectedSession && (
            <div className="rounded-lg border bg-white">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-3">
                  <h3 className="font-semibold text-slate-900">
                    Session {selectedSession.id.substring(0, 8)}...
                  </h3>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[selectedSession.statut] || "bg-slate-100 text-slate-800"}`}>
                    {selectedSession.statut}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedSession.statut === "EN_COURS" && (
                    <button
                      onClick={() => refreshSession(selectedSession.id)}
                      className="text-sm text-teal-600 hover:underline"
                    >
                      Actualiser
                    </button>
                  )}
                  <button
                    onClick={() => setSelectedSession(null)}
                    className="text-sm text-slate-400 hover:text-slate-600"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* Progress bar */}
              {selectedSession.statut === "EN_COURS" && selectedSession.nombre_fichiers > 0 && (
                <div className="px-4 py-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">
                      {selectedSession.fichiers_traites} / {selectedSession.nombre_fichiers} traités
                    </span>
                    <span className="text-slate-500">
                      {Math.round((selectedSession.fichiers_traites / selectedSession.nombre_fichiers) * 100)}%
                    </span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-slate-200">
                    <div
                      className="h-2 rounded-full bg-teal-600 transition-all"
                      style={{
                        width: `${(selectedSession.fichiers_traites / selectedSession.nombre_fichiers) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 border-b px-4 py-3">
                <div>
                  <p className="text-xs text-slate-500">Total</p>
                  <p className="text-lg font-bold text-slate-900">{selectedSession.nombre_fichiers}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Traités</p>
                  <p className="text-lg font-bold text-green-600">{selectedSession.fichiers_traites}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Erreurs</p>
                  <p className="text-lg font-bold text-red-600">{selectedSession.fichiers_erreur}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Doublons</p>
                  <p className="text-lg font-bold text-yellow-600">{selectedSession.fichiers_dupliques}</p>
                </div>
              </div>

              {/* File results */}
              {selectedSession.resultats && selectedSession.resultats.length > 0 && (
                <div className="max-h-80 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-slate-50">
                      <tr className="text-left text-xs text-slate-500">
                        <th className="px-4 py-2">Fichier</th>
                        <th className="px-4 py-2">Statut</th>
                        <th className="px-4 py-2">Type</th>
                        <th className="px-4 py-2">Module</th>
                        <th className="px-4 py-2">Résultat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedSession.resultats.map((r, i) => (
                        <tr key={i} className="border-t hover:bg-slate-50">
                          <td className="px-4 py-2 font-medium text-slate-900">{r.filename}</td>
                          <td className={`px-4 py-2 font-medium ${FILE_STATUS_COLORS[r.status] || "text-slate-600"}`}>
                            {r.status}
                          </td>
                          <td className="px-4 py-2 text-slate-600">{r.doc_type || "—"}</td>
                          <td className="px-4 py-2 text-slate-600">
                            {r.routed_to ? MODULE_LABELS[r.routed_to] || r.routed_to : "—"}
                          </td>
                          <td className="px-4 py-2 text-slate-600">
                            {(r.created_record_ids?.length || r.journal_entry_ids?.length) ? (
                              <span>
                                {(r.journal_entry_ids?.length ?? 0) + (r.created_record_ids?.length ?? 0)} enregistrement(s)
                              </span>
                            ) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Sessions list */}
          <div className="rounded-lg border bg-white">
            <div className="border-b px-4 py-3">
              <h3 className="font-semibold text-slate-900">Historique des imports</h3>
            </div>
            {sessions.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-500">
                Aucune session d'import. Commencez par importer des fichiers.
              </div>
            ) : (
              <div className="divide-y">
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setSelectedSession(s);
                      if (s.statut === "EN_COURS") refreshSession(s.id);
                    }}
                    className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{s.source_type === "GOOGLE_DRIVE" ? "☁️" : "📁"}</span>
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {s.source_path || s.source_type} — {s.nombre_fichiers} fichiers
                        </p>
                        <p className="text-xs text-slate-500">
                          {s.date_import ? new Date(s.date_import).toLocaleString("fr-FR") : "—"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {s.statut === "EN_COURS" && (
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
                      )}
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[s.statut] || "bg-slate-100 text-slate-800"}`}>
                        {s.statut}
                      </span>
                      <span className="text-xs text-slate-500">
                        {s.fichiers_traites}/{s.nombre_fichiers}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
