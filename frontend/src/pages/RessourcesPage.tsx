import { useState, useCallback, useEffect, useRef } from "react";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";
import JsBarcode from "jsbarcode";
import {
  CubeIcon,
  CameraIcon,
  ArrowUpTrayIcon,
  ArrowPathIcon,
  PlusIcon,
  SparklesIcon,
  PrinterIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

/* ── Types ──────────────────────────────────────────── */

interface StockItem {
  id: string;
  entreprise_id: string;
  code_article: string;
  designation: string;
  unite: string;
  quantite: number;
  valeur_unitaire: number;
  valeur_totale: number;
  emplacement: string | null;
  seuil_alerte: number;
  est_actif: boolean;
  en_alerte: boolean;
  created_at: string | null;
}

interface AIResult {
  designation: string;
  code_article_suggestion: string;
  unite_suggestion: string;
  category: string;
  confidence: number;
  description: string;
  ai_model?: string;
}

interface StockStats {
  total_articles: number;
  articles_en_alerte: number;
  valeur_totale_stock: number;
}

/* ── Helpers ────────────────────────────────────────── */

function fmtMoney(v: number | null | undefined) {
  if (v == null) return "\u2014";
  return new Intl.NumberFormat("fr-DZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v) + " DA";
}

/* ── Barcode Print Component ────────────────────────── */

function BarcodePrintModal({ item, onClose }: { item: StockItem; onClose: () => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const barcodeValue = `${item.code_article}-${item.id.slice(0, 8).toUpperCase()}`;

  useEffect(() => {
    if (svgRef.current) {
      JsBarcode(svgRef.current, barcodeValue, {
        format: "CODE128",
        width: 2,
        height: 60,
        displayValue: true,
        fontSize: 14,
        margin: 10,
      });
    }
  }, [barcodeValue]);

  const handlePrint = () => {
    const svgEl = svgRef.current;
    if (!svgEl) return;
    const svgData = new XMLSerializer().serializeToString(svgEl);
    const printWindow = window.open("", "_blank", "width=400,height=300");
    if (!printWindow) return;
    printWindow.document.write(`<!DOCTYPE html><html><head><title>Barcode - ${item.code_article}</title>
      <style>
        body { margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; font-family: sans-serif; }
        .label { text-align: center; padding: 16px; border: 1px dashed #ccc; border-radius: 8px; }
        .designation { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
        .details { font-size: 11px; color: #666; margin-bottom: 8px; }
        @media print { .no-print { display: none; } body { margin: 0; } .label { border: none; } }
      </style></head><body>
      <div class="label">
        <div class="designation">${item.designation}</div>
        <div class="details">${item.emplacement || ""} | ${item.unite}</div>
        ${svgData}
      </div>
      <button class="no-print" onclick="window.print()" style="margin-top:16px;padding:8px 24px;cursor:pointer;">Imprimer</button>
    </body></html>`);
    printWindow.document.close();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">Code-barres</h3>
          <button onClick={onClose} className="rounded-full p-1 hover:bg-slate-100"><XMarkIcon className="h-5 w-5" /></button>
        </div>
        <div className="text-center mb-4">
          <p className="font-semibold text-slate-800">{item.designation}</p>
          <p className="text-xs text-slate-500">{item.code_article} | {item.emplacement || "Sans emplacement"}</p>
        </div>
        <div className="flex justify-center bg-white rounded-xl border border-slate-200 p-4">
          <svg ref={svgRef} />
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={onClose} className="btn-secondary">Fermer</button>
          <button onClick={handlePrint} className="btn-primary"><PrinterIcon className="h-4 w-4" /> Imprimer</button>
        </div>
      </div>
    </div>
  );
}

/* ── AI Identification Modal ────────────────────────── */

function AIIdentifyModal({
  onClose,
  onItemIdentified,
}: {
  onClose: () => void;
  onItemIdentified: (ai: AIResult, preview: string) => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraMode, setCameraMode] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setError("");
    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result as string);
    reader.readAsDataURL(f);
  };

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      setStream(mediaStream);
      setCameraMode(true);
      setError("");
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
          videoRef.current.play();
        }
      }, 100);
    } catch {
      setError("Impossible d'acceder a la camera. Verifiez les permissions.");
    }
  };

  const capturePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) {
        const capturedFile = new File([blob], "photo.jpg", { type: "image/jpeg" });
        setFile(capturedFile);
        setPreview(canvas.toDataURL("image/jpeg"));
        stopCamera();
      }
    }, "image/jpeg", 0.9);
  };

  const stopCamera = () => {
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setCameraMode(false);
  };

  const handleIdentify = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post("/ressources/ai-identify", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onItemIdentified(data as AIResult, preview || "");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Erreur lors de l'identification IA.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => { stream?.getTracks().forEach((t) => t.stop()); };
  }, [stream]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => { stopCamera(); onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <SparklesIcon className="h-5 w-5 text-violet-500" />
            <h3 className="text-lg font-semibold text-slate-900">Identification IA</h3>
          </div>
          <button onClick={() => { stopCamera(); onClose(); }} className="rounded-full p-1 hover:bg-slate-100"><XMarkIcon className="h-5 w-5" /></button>
        </div>

        <p className="text-sm text-slate-500 mb-4">
          Prenez une photo ou importez une image de l'article. L'IA identifiera automatiquement l'objet.
        </p>

        {cameraMode ? (
          <div className="space-y-3">
            <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            </div>
            <canvas ref={canvasRef} className="hidden" />
            <div className="flex gap-2 justify-center">
              <button onClick={stopCamera} className="btn-secondary">Annuler</button>
              <button onClick={capturePhoto} className="btn-primary"><CameraIcon className="h-4 w-4" /> Capturer</button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {preview ? (
              <div className="relative">
                <img src={preview} alt="Preview" className="w-full max-h-64 object-contain rounded-xl border border-slate-200" />
                <button
                  onClick={() => { setPreview(null); setFile(null); }}
                  className="absolute top-2 right-2 rounded-full bg-white/80 p-1 hover:bg-white shadow"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="rounded-xl border-2 border-dashed border-slate-300 p-8 text-center">
                <CubeIcon className="h-10 w-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500 mb-4">Photographiez ou importez l'article a identifier</p>
                <div className="flex gap-3 justify-center">
                  <button onClick={startCamera} className="btn-secondary">
                    <CameraIcon className="h-4 w-4" /> Camera
                  </button>
                  <label className="btn-primary cursor-pointer">
                    <ArrowUpTrayIcon className="h-4 w-4" /> Importer
                    <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileSelect} />
                  </label>
                </div>
              </div>
            )}

            {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

            {file && (
              <button onClick={handleIdentify} disabled={loading} className="btn-primary w-full justify-center">
                {loading ? (
                  <><ArrowPathIcon className="h-4 w-4 animate-spin" /> Analyse en cours...</>
                ) : (
                  <><SparklesIcon className="h-4 w-4" /> Identifier avec l'IA</>
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────── */

type RessTab = "stock" | "demandes" | "receptions" | "factures" | "entrepots";

export default function RessourcesPage() {
  const [ressTab, setRessTab] = useState<RessTab>("stock");

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Ressources — Achats, Stock & Logistique</h1>
      <p className="text-sm text-slate-500 mb-4">Cycle d'approvisionnement complet, inventaire multi-entrep&ocirc;ts</p>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([
          ["stock", "Stock & Inventaire"],
          ["demandes", "Demandes d'achat"],
          ["receptions", "R\u00e9ceptions"],
          ["factures", "Factures fournisseur"],
          ["entrepots", "Entrep\u00f4ts"],
        ] as [RessTab, string][]).map(([k, label]) => (
          <button key={k} onClick={() => setRessTab(k)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${ressTab === k ? "border-teal-600 text-teal-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}>
            {label}
          </button>
        ))}
      </div>

      {ressTab === "stock" && <StockSection />}
      {ressTab === "demandes" && <DemandesSection />}
      {ressTab === "receptions" && <ReceptionsSection />}
      {ressTab === "factures" && <FacturesSection />}
      {ressTab === "entrepots" && <EntrepotsSection />}
    </div>
  );
}


/* ══════════════════════════════════════════════════════
   Demandes d'achat (EX-ACH-001 step 1)
   ══════════════════════════════════════════════════════ */
function DemandesSection() {
  const { user } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState({ reference: "", objet: "", description: "", montant_estime: 0, urgence: "NORMALE", date_demande: new Date().toISOString().slice(0, 10) });
  const [justifFile, setJustifFile] = useState<File | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.get("/achats/demandes").then(({ data }) => setItems(data || [])).catch(() => setItems([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true); setFormError("");
    try {
      const fd = new FormData();
      const body = JSON.stringify({ ...form, montant_estime: Number(form.montant_estime), entreprise_id: "default", lignes: [] });
      fd.append("body", new Blob([body], { type: "application/json" }));
      if (justifFile) fd.append("file", justifFile);
      await api.post("/achats/demandes", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setShowForm(false); setJustifFile(null);
      setForm({ reference: "", objet: "", description: "", montant_estime: 0, urgence: "NORMALE", date_demande: new Date().toISOString().slice(0, 10) });
      load();
    } catch (err: any) { setFormError(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  const approuver = async (id: string, demandeurId: string) => {
    if (demandeurId === user?.id) { alert("Vous ne pouvez pas approuver votre propre demande."); return; }
    try { await api.post(`/achats/demandes/${id}/approuver`); load(); }
    catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
  };

  const rejeter = async (id: string) => {
    const motif = prompt("Motif du rejet :"); if (!motif) return;
    await api.post(`/achats/demandes/${id}/rejeter`, null, { params: { motif } }); load();
  };

  const STATUT_BADGE: Record<string, string> = {
    BROUILLON: "bg-slate-100 text-slate-600", SOUMISE: "bg-amber-100 text-amber-700",
    APPROUVEE: "bg-emerald-100 text-emerald-700", REJETEE: "bg-red-100 text-red-700",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} demandes</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs"><PlusIcon className="h-4 w-4" /> Nouvelle demande</button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          {formError && <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{formError}</div>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Référence *</label>
              <input className="input-field" value={form.reference} onChange={e => setForm({ ...form, reference: e.target.value })} required placeholder="DA-2026-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Objet *</label>
              <input className="input-field" value={form.objet} onChange={e => setForm({ ...form, objet: e.target.value })} required placeholder="Achat ciment, ferraille..." /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant estimé (DA) *</label>
              <input type="number" step="0.01" className="input-field" value={form.montant_estime || ""} onChange={e => setForm({ ...form, montant_estime: +e.target.value })} required /></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Urgence</label>
              <select className="input-field" value={form.urgence} onChange={e => setForm({ ...form, urgence: e.target.value })}>
                <option value="BASSE">Basse</option><option value="NORMALE">Normale</option><option value="ELEVEE">Élevée</option><option value="CRITIQUE">Critique</option>
              </select></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date</label>
              <input type="date" className="input-field" value={form.date_demande} onChange={e => setForm({ ...form, date_demande: e.target.value })} /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Justificatif (devis, spec)</label>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" onChange={e => setJustifFile(e.target.files?.[0] ?? null)} /></div>
          </div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Description / justification *</label>
            <textarea className="input-field w-full" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required placeholder="Pourquoi cet achat est nécessaire..." /></div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Envoi..." : "Soumettre"}</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">Réf.</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Objet</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Montant</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Urgence</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Statut</th>
            <th className="px-3 py-3 w-32"></th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement...</td></tr>
             : items.length === 0 ? <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune demande</td></tr>
             : items.map((d: any) => (
              <tr key={d.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{d.reference}</td>
                <td className="px-3 py-2">{d.objet}</td>
                <td className="px-3 py-2 text-right font-mono">{Math.round(d.montant_estime).toLocaleString("fr-FR")} DA</td>
                <td className="px-3 py-2 text-xs">{d.urgence}</td>
                <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_BADGE[d.statut] || "bg-slate-100"}`}>{d.statut}</span></td>
                <td className="px-3 py-2">
                  {(d.statut === "BROUILLON" || d.statut === "SOUMISE") && (
                    <div className="flex gap-1">
                      <button onClick={() => approuver(d.id, d.demandeur_id)} className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-700">Approuver</button>
                      <button onClick={() => rejeter(d.id)} className="px-1.5 py-0.5 rounded text-[10px] bg-red-100 text-red-700">Rejeter</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   R&eacute;ceptions (EX-ACH-001 step 3)
   ══════════════════════════════════════════════════════ */
function ReceptionsSection() {
  const [items, setItems] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ reference: "", date_reception: new Date().toISOString().slice(0, 10), quantite_commandee: 0, quantite_recue: 0, quantite_conforme: 0, notes: "" });

  const load = useCallback(() => { api.get("/achats/receptions").then(({ data }) => setItems(data || [])).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault(); setSubmitting(true);
    try {
      await api.post("/achats/receptions", form);
      setShowForm(false); setForm({ reference: "", date_reception: new Date().toISOString().slice(0, 10), quantite_commandee: 0, quantite_recue: 0, quantite_conforme: 0, notes: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} réceptions</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs"><PlusIcon className="h-4 w-4" /> Nouvelle réception</button>
      </div>
      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Référence *</label>
              <input className="input-field" value={form.reference} onChange={e => setForm({ ...form, reference: e.target.value })} required placeholder="BR-2026-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date réception</label>
              <input type="date" className="input-field" value={form.date_reception} onChange={e => setForm({ ...form, date_reception: e.target.value })} /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Qté commandée</label>
              <input type="number" className="input-field" value={form.quantite_commandee || ""} onChange={e => setForm({ ...form, quantite_commandee: +e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Qté reçue *</label>
              <input type="number" className="input-field" value={form.quantite_recue || ""} onChange={e => setForm({ ...form, quantite_recue: +e.target.value })} required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Qté conforme</label>
              <input type="number" className="input-field" value={form.quantite_conforme || ""} onChange={e => setForm({ ...form, quantite_conforme: +e.target.value })} /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Notes / justification *</label>
              <input className="input-field" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} required placeholder="Bon de livraison n°..." /></div>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Envoi..." : "Enregistrer"}</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">Réf.</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Date</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Commandé</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Reçu</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">Conforme</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Statut</th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {items.length === 0 ? <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune réception</td></tr>
             : items.map((r: any) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{r.reference}</td>
                <td className="px-3 py-2 text-xs">{r.date_reception}</td>
                <td className="px-3 py-2 text-right">{r.quantite_commandee}</td>
                <td className="px-3 py-2 text-right">{r.quantite_recue}</td>
                <td className="px-3 py-2 text-right">{r.quantite_conforme}</td>
                <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${r.statut === "CONFORME" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{r.statut}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Factures fournisseur (EX-ACH-001 step 4)
   ══════════════════════════════════════════════════════ */
function FacturesSection() {
  const { user } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [factureFile, setFactureFile] = useState<File | null>(null);
  const [form, setForm] = useState({ reference_facture: "", date_facture: new Date().toISOString().slice(0, 10), fournisseur: "", montant_ht: 0, realite_financiere: "RF1", notes: "" });

  const load = useCallback(() => { api.get("/achats/factures-fournisseur").then(({ data }) => setItems(data || [])).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!factureFile) { alert("Le document de la facture est obligatoire."); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", factureFile);
      const body = JSON.stringify({ ...form, montant_ht: Number(form.montant_ht) });
      fd.append("body", new Blob([body], { type: "application/json" }));
      await api.post("/achats/factures-fournisseur", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setShowForm(false); setFactureFile(null);
      setForm({ reference_facture: "", date_facture: new Date().toISOString().slice(0, 10), fournisseur: "", montant_ht: 0, realite_financiere: "RF1", notes: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    finally { setSubmitting(false); }
  };

  const valider = async (id: string, createdBy: string) => {
    if (createdBy === user?.id) { alert("Le créateur ne peut pas valider sa propre facture."); return; }
    const input = document.createElement("input"); input.type = "file"; input.accept = ".pdf,.png,.jpg,.jpeg";
    input.onchange = async () => {
      const f = input.files?.[0]; if (!f) return;
      const fd = new FormData(); fd.append("file", f);
      try { await api.post(`/achats/factures-fournisseur/${id}/valider`, fd, { headers: { "Content-Type": "multipart/form-data" } }); load(); }
      catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
    };
    input.click();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} factures</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs"><PlusIcon className="h-4 w-4" /> Nouvelle facture</button>
      </div>
      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Réf. facture *</label>
              <input className="input-field" value={form.reference_facture} onChange={e => setForm({ ...form, reference_facture: e.target.value })} required placeholder="FF-2026-001" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Fournisseur *</label>
              <input className="input-field" value={form.fournisseur} onChange={e => setForm({ ...form, fournisseur: e.target.value })} required placeholder="Nom du fournisseur" /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Date facture</label>
              <input type="date" className="input-field" value={form.date_facture} onChange={e => setForm({ ...form, date_facture: e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Montant HT (DA) *</label>
              <input type="number" step="0.01" className="input-field" value={form.montant_ht || ""} onChange={e => setForm({ ...form, montant_ht: +e.target.value })} required /></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Réalité financière</label>
              <select className="input-field" value={form.realite_financiere} onChange={e => setForm({ ...form, realite_financiere: e.target.value })}>
                <option value="RF1">RF1 - Réel déclaré</option><option value="RF2">RF2 - Réel non déclaré</option>
              </select></div>
            <div><label className="block text-xs font-medium text-slate-500 mb-1">Document facture *</label>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" onChange={e => setFactureFile(e.target.files?.[0] ?? null)} required /></div>
          </div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Notes / justification *</label>
            <textarea className="input-field w-full" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} required placeholder="Contexte de la facture, commande liée..." /></div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" disabled={submitting} className="btn-primary text-sm">{submitting ? "Envoi..." : "Enregistrer"}</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">Réf.</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Date</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">HT</th>
            <th className="px-3 py-3 text-right font-medium text-slate-600">TTC</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">RF</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Statut</th>
            <th className="px-3 py-3 w-24"></th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {items.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune facture</td></tr>
             : items.map((f: any) => (
              <tr key={f.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{f.reference_facture}</td>
                <td className="px-3 py-2 text-xs">{f.date_facture}</td>
                <td className="px-3 py-2 text-right font-mono">{Math.round(f.montant_ht).toLocaleString("fr-FR")} DA</td>
                <td className="px-3 py-2 text-right font-mono">{Math.round(f.montant_ttc).toLocaleString("fr-FR")} DA</td>
                <td className="px-3 py-2 text-xs">{f.realite_financiere}</td>
                <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${f.statut === "VALIDEE" ? "bg-emerald-100 text-emerald-700" : f.statut === "PAYEE" ? "bg-teal-100 text-teal-700" : "bg-amber-100 text-amber-700"}`}>{f.statut}</span></td>
                <td className="px-3 py-2">
                  {f.statut === "A_VALIDER" && (
                    <button onClick={() => valider(f.id, f.created_by)} className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-700">Valider</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Entrep&ocirc;ts (EX-ACH-002)
   ══════════════════════════════════════════════════════ */
function EntrepotsSection() {
  const [items, setItems] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", designation: "", adresse: "" });

  const load = useCallback(() => { api.get("/achats/entrepots").then(({ data }) => setItems(data || [])).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/achats/entrepots", form);
      setShowForm(false); setForm({ code: "", designation: "", adresse: "" }); load();
    } catch (err: any) { alert(err?.response?.data?.detail || "Erreur"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold">{items.length} entrepôts</span>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs"><PlusIcon className="h-4 w-4" /> Nouvel entrepôt</button>
      </div>
      {showForm && (
        <form onSubmit={handleCreate} className="card p-4 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Code *</label>
            <input className="input-field" value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} required placeholder="ENT-01" /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Désignation *</label>
            <input className="input-field" value={form.designation} onChange={e => setForm({ ...form, designation: e.target.value })} required placeholder="Entrepôt principal" /></div>
          <div><label className="block text-xs font-medium text-slate-500 mb-1">Adresse</label>
            <input className="input-field" value={form.adresse} onChange={e => setForm({ ...form, adresse: e.target.value })} placeholder="Adresse complète" /></div>
          <div className="md:col-span-3 flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Annuler</button>
            <button type="submit" className="btn-primary text-sm">Créer</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-slate-50">
            <th className="px-3 py-3 text-left font-medium text-slate-600">Code</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Désignation</th>
            <th className="px-3 py-3 text-left font-medium text-slate-600">Adresse</th>
          </tr></thead>
          <tbody className="divide-y divide-slate-100">
            {items.length === 0 ? <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Aucun entrepôt</td></tr>
             : items.map((e: any) => (
              <tr key={e.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{e.code}</td>
                <td className="px-3 py-2">{e.designation}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{e.adresse || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════
   Stock Section (existing functionality)
   ══════════════════════════════════════════════════════ */
function StockSection() {
  const { user } = useAuth();
  const isManager = ["SUPER_ADMIN", "PDG_SUPER_ADMIN", "DAF", "CHARGE_MISSION", "MAGASINIER", "ACHATS", "admin"].includes(user?.role ?? "");

  const [items, setItems] = useState<StockItem[]>([]);
  const [stats, setStats] = useState<StockStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [alerteOnly, setAlerteOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Modals
  const [showAI, setShowAI] = useState(false);
  const [showManualForm, setShowManualForm] = useState(false);
  const [barcodeItem, setBarcodeItem] = useState<StockItem | null>(null);
  const [aiPreview, setAiPreview] = useState("");

  // Form state (used by both AI-prefilled and manual)
  const [form, setForm] = useState({
    entreprise_id: "",
    code_article: "",
    designation: "",
    unite: "unite",
    quantite: "",
    valeur_unitaire: "",
    emplacement: "",
    seuil_alerte: "",
  });
  const [aiResult, setAiResult] = useState<AIResult | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | boolean> = {};
      if (alerteOnly) params.alerte_only = true;
      if (search.trim()) params.search = search.trim();
      const { data } = await api.get("/ressources/stock", { params });
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [alerteOnly, search]);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await api.get("/ressources/stats");
      setStats(data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { fetchItems(); }, [fetchItems]);
  useEffect(() => { fetchStats(); }, [fetchStats]);

  const resetForm = () => {
    setForm({ entreprise_id: "", code_article: "", designation: "", unite: "unite", quantite: "", valeur_unitaire: "", emplacement: "", seuil_alerte: "" });
    setAiResult(null);
    setAiPreview("");
  };

  const handleAIIdentified = (ai: AIResult, preview: string) => {
    setAiResult(ai);
    setAiPreview(preview);
    setShowAI(false);
    setForm({
      ...form,
      code_article: ai.code_article_suggestion,
      designation: ai.designation,
      unite: ai.unite_suggestion,
      quantite: "",
      valeur_unitaire: "",
      emplacement: "",
      seuil_alerte: "",
    });
    setShowManualForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const { data } = await api.post("/ressources/stock", {
        ...form,
        quantite: parseFloat(form.quantite || "0"),
        valeur_unitaire: parseFloat(form.valeur_unitaire || "0"),
        seuil_alerte: parseFloat(form.seuil_alerte || "0"),
      });
      setShowManualForm(false);
      resetForm();
      await fetchItems();
      await fetchStats();
      setMessage("Article ajoute avec succes.");
      // Auto-open barcode for the newly created item
      setBarcodeItem(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Erreur lors de la creation.");
    }
  };

  const alertCount = items.filter((i) => i.en_alerte).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Ressources</h1>
          <p className="mt-1 text-sm text-slate-500">
            Gestion du stock materiel avec identification IA et codes-barres.
          </p>
        </div>
        {isManager && (
          <div className="flex gap-2">
            <button onClick={() => { resetForm(); setShowAI(true); }} className="btn-primary">
              <CameraIcon className="h-4 w-4" /> Scanner IA
            </button>
            <button onClick={() => { resetForm(); setShowManualForm(true); }} className="btn-secondary">
              <PlusIcon className="h-4 w-4" /> Ajout manuel
            </button>
          </div>
        )}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-100 p-2"><CubeIcon className="h-5 w-5 text-blue-600" /></div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{stats.total_articles}</p>
                <p className="text-xs text-slate-500">Articles en stock</p>
              </div>
            </div>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className={`rounded-lg p-2 ${stats.articles_en_alerte > 0 ? "bg-red-100" : "bg-emerald-100"}`}>
                <ExclamationTriangleIcon className={`h-5 w-5 ${stats.articles_en_alerte > 0 ? "text-red-600" : "text-emerald-600"}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{stats.articles_en_alerte}</p>
                <p className="text-xs text-slate-500">En alerte stock</p>
              </div>
            </div>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-amber-100 p-2"><CubeIcon className="h-5 w-5 text-amber-600" /></div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{fmtMoney(stats.valeur_totale_stock)}</p>
                <p className="text-xs text-slate-500">Valeur totale</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            className="input-field pl-9"
            placeholder="Rechercher par code ou designation..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          <input type="checkbox" checked={alerteOnly} onChange={(e) => setAlerteOnly(e.target.checked)} className="rounded" />
          Alertes seules
        </label>
        {alertCount > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">
            <ExclamationTriangleIcon className="h-3 w-3" />{alertCount} en alerte
          </span>
        )}
        <button onClick={() => { fetchItems(); fetchStats(); }} className="btn-secondary text-xs ml-auto">
          <ArrowPathIcon className="h-4 w-4" /> Actualiser
        </button>
      </div>

      {/* Messages */}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}

      {/* ── Create Form (AI-prefilled or manual) ── */}
      {showManualForm && isManager && (
        <div className="card p-5 border-l-4 border-violet-500">
          {aiResult && (
            <div className="mb-4 rounded-xl bg-violet-50 border border-violet-200 p-4">
              <div className="flex items-start gap-3">
                {aiPreview && <img src={aiPreview} alt="AI" className="h-20 w-20 rounded-lg object-cover border border-violet-200" />}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <SparklesIcon className="h-4 w-4 text-violet-500" />
                    <span className="text-sm font-semibold text-violet-800">Identification IA</span>
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                      aiResult.confidence >= 0.8 ? "bg-emerald-100 text-emerald-800" :
                      aiResult.confidence >= 0.5 ? "bg-amber-100 text-amber-800" :
                      "bg-red-100 text-red-800"
                    }`}>{Math.round(aiResult.confidence * 100)}% confiance</span>
                  </div>
                  <p className="text-sm font-medium text-slate-800">{aiResult.designation}</p>
                  <p className="text-xs text-slate-500 mt-1">{aiResult.category} | {aiResult.description}</p>
                </div>
              </div>
            </div>
          )}

          <h3 className="text-base font-semibold text-slate-900 mb-3">
            {aiResult ? "Completez les informations" : "Nouvel article"}
          </h3>

          <form onSubmit={handleSubmit} className="grid md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Entreprise ID *</label>
              <input className="input-field" value={form.entreprise_id} onChange={(e) => setForm({ ...form, entreprise_id: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Code article *</label>
              <input className="input-field" value={form.code_article} onChange={(e) => setForm({ ...form, code_article: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Designation *</label>
              <input className="input-field" value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Unite</label>
              <input className="input-field" value={form.unite} onChange={(e) => setForm({ ...form, unite: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Quantite *</label>
              <input type="number" step="any" className="input-field" value={form.quantite} onChange={(e) => setForm({ ...form, quantite: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Valeur unitaire (DA)</label>
              <input type="number" step="any" className="input-field" value={form.valeur_unitaire} onChange={(e) => setForm({ ...form, valeur_unitaire: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Emplacement</label>
              <input className="input-field" value={form.emplacement} onChange={(e) => setForm({ ...form, emplacement: e.target.value })} placeholder="Ex: Magasin A - Etagere 3" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Seuil d'alerte</label>
              <input type="number" step="any" className="input-field" value={form.seuil_alerte} onChange={(e) => setForm({ ...form, seuil_alerte: e.target.value })} />
            </div>
            <div className="flex items-end gap-2">
              <button type="button" onClick={() => { setShowManualForm(false); resetForm(); }} className="btn-secondary">Annuler</button>
              <button type="submit" className="btn-primary">
                <CheckCircleIcon className="h-4 w-4" /> Enregistrer
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Stock Table ── */}
      {loading ? (
        <div className="flex justify-center py-12"><ArrowPathIcon className="h-8 w-8 animate-spin text-slate-400" /></div>
      ) : items.length === 0 ? (
        <div className="card p-12 text-center">
          <CubeIcon className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">{alerteOnly ? "Aucun article en alerte." : search ? "Aucun resultat pour cette recherche." : "Aucun article en stock."}</p>
          {isManager && !search && (
            <p className="text-sm text-slate-400 mt-2">Utilisez "Scanner IA" pour ajouter des articles en photographiant vos materiaux.</p>
          )}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50 text-left text-xs text-slate-500">
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Designation</th>
                <th className="px-4 py-3 text-right">Qte</th>
                <th className="px-4 py-3">Unite</th>
                <th className="px-4 py-3 text-right">Val. unit.</th>
                <th className="px-4 py-3 text-right">Val. totale</th>
                <th className="px-4 py-3">Emplacement</th>
                <th className="px-4 py-3 text-center">Statut</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className={`border-b border-slate-100 ${s.en_alerte ? "bg-red-50" : "hover:bg-slate-50"}`}>
                  <td className="px-4 py-3 font-mono font-medium text-slate-900">{s.code_article}</td>
                  <td className="px-4 py-3 text-slate-800">{s.designation}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${s.en_alerte ? "text-red-600" : ""}`}>{s.quantite}</td>
                  <td className="px-4 py-3 text-slate-600">{s.unite}</td>
                  <td className="px-4 py-3 text-right">{fmtMoney(s.valeur_unitaire)}</td>
                  <td className="px-4 py-3 text-right font-semibold">{fmtMoney(s.valeur_totale)}</td>
                  <td className="px-4 py-3 text-slate-600">{s.emplacement || "\u2014"}</td>
                  <td className="px-4 py-3 text-center">
                    {s.en_alerte
                      ? <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800"><XCircleIcon className="h-3 w-3" />Alerte</span>
                      : <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800"><CheckCircleIcon className="h-3 w-3" />OK</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => setBarcodeItem(s)}
                      className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 transition-colors"
                      title="Generer code-barres"
                    >
                      <PrinterIcon className="h-3.5 w-3.5" /> Barcode
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modals ── */}
      {showAI && <AIIdentifyModal onClose={() => setShowAI(false)} onItemIdentified={handleAIIdentified} />}
      {barcodeItem && <BarcodePrintModal item={barcodeItem} onClose={() => setBarcodeItem(null)} />}
    </div>
  );
}
