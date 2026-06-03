import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const CATEGORIES = [
  'MATERIAU_CONSTRUCTION', 'EQUIPEMENT', 'OUTILLAGE', 'PLOMBERIE',
  'ELECTRICITE', 'MENUISERIE', 'PEINTURE', 'REVETEMENT',
  'QUINCAILLERIE', 'SECURITE', 'MOBILIER', 'INFORMATIQUE',
  'FOURNITURE_BUREAU', 'VEHICULE', 'EPI', 'AUTRE',
];
const UNITS = ['UNITE', 'KG', 'M', 'M2', 'M3', 'LITRE', 'SEAU', 'SAC', 'PALETTE', 'ROULEAU', 'BOITE', 'LOT'];

export function StockCapture() {
  const nav = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Steps: capture -> analyzing -> form -> saving
  const [step, setStep] = useState<'capture' | 'analyzing' | 'form' | 'saving' | 'done'>('capture');
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState('');

  // AI data
  const [aiData, setAiData] = useState<any>(null);
  const [aiError, setAiError] = useState('');

  // Form fields
  const [name, setName] = useState('');
  const [category, setCategory] = useState('AUTRE');
  const [description, setDescription] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [unit, setUnit] = useState('UNITE');
  const [unitPrice, setUnitPrice] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [minAlert, setMinAlert] = useState('');
  const [imageUrl, setImageUrl] = useState('');

  // Zones
  const [zones, setZones] = useState<any[]>([]);
  const [showZoneForm, setShowZoneForm] = useState(false);
  const [newZoneCode, setNewZoneCode] = useState('');
  const [newZoneLabel, setNewZoneLabel] = useState('');
  const [newZoneLoc, setNewZoneLoc] = useState('');

  // Result
  const [createdItem, setCreatedItem] = useState<any>(null);

  useEffect(() => {
    api.get('/stock/zones').then(r => setZones(r.data.data || [])).catch(() => {});
  }, []);

  // ── Camera ──────────────────────────────────────────────────────────────
  const startCamera = async () => {
    setCameraError('');
    // Check if getUserMedia is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Camera non supportee par ce navigateur. Utilisez Chrome ou Edge, ou uploadez une image.');
      return;
    }
    try {
      // Try rear camera first, fallback to any camera
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        });
      } catch {
        // Fallback: any available camera
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      }
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // Must explicitly call play() and wait for it
        await videoRef.current.play();
        setCameraActive(true);
      }
    } catch (e: any) {
      let msg = 'Camera non disponible.';
      if (e.name === 'NotAllowedError') {
        msg = 'Acces camera refuse. Autorisez la camera dans les parametres du navigateur.';
      } else if (e.name === 'NotFoundError') {
        msg = 'Aucune camera detectee sur cet appareil.';
      } else if (e.name === 'NotReadableError') {
        msg = 'Camera deja utilisee par une autre application.';
      } else if (e.name === 'OverconstrainedError') {
        msg = 'Camera ne supporte pas les parametres demandes.';
      } else {
        msg = `Erreur camera: ${e.message || e.name || 'inconnue'}`;
      }
      setCameraError(msg);
    }
  };

  const stopCamera = () => {
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop());
      videoRef.current.srcObject = null;
      setCameraActive(false);
    }
  };

  // Cleanup camera on unmount
  useEffect(() => {
    return () => {
      if (videoRef.current?.srcObject) {
        (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) {
      setCameraError('Elements video/canvas non disponibles.');
      return;
    }
    const video = videoRef.current;
    const canvas = canvasRef.current;
    // Ensure video has actual dimensions
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraError('Video pas encore prete. Attendez un instant et reessayez.');
      return;
    }
    // Draw frame to canvas WHILE video is still active
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      setCameraError('Canvas context non disponible.');
      return;
    }
    ctx.drawImage(video, 0, 0);
    // Extract blob from canvas BEFORE stopping camera
    canvas.toBlob(blob => {
      // Now stop the camera
      stopCamera();
      if (blob && blob.size > 0) {
        analyzeImage(new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' }));
      } else {
        setCameraError('Capture echouee — image vide. Reessayez.');
      }
    }, 'image/jpeg', 0.92);
  };

  // ── File upload ─────────────────────────────────────────────────────────
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) analyzeImage(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) analyzeImage(file);
  };

  // ── AI Analysis ─────────────────────────────────────────────────────────
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const analyzeImage = async (file: File) => {
    // Show preview of captured/uploaded image
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setStep('analyzing');
    setAiError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/stock/identify', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      const d = res.data.data;
      setAiData(d);
      // Pre-fill form
      if (d.name) setName(d.name);
      if (d.category) setCategory(d.category);
      if (d.description) setDescription(d.description);
      if (d.unit) setUnit(d.unit);
      if (d.estimated_unit_price) setUnitPrice(String(d.estimated_unit_price));
      if (d.image_path) setImageUrl(d.image_path);
      if (d.error) setAiError(d.error);
      setStep('form');
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Erreur analyse';
      setAiError(`Erreur: ${detail}`);
      setStep('form');
    }
  };

  // ── Create zone inline ──────────────────────────────────────────────────
  const createZone = async () => {
    if (!newZoneCode.trim() || !newZoneLabel.trim()) return;
    try {
      const res = await api.post('/stock/zones', { code: newZoneCode, label: newZoneLabel, location: newZoneLoc });
      const z = res.data.data;
      setZones(prev => [...prev, z]);
      setZoneId(z.id);
      setShowZoneForm(false);
      setNewZoneCode('');
      setNewZoneLabel('');
      setNewZoneLoc('');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur creation zone');
    }
  };

  // ── Save item ───────────────────────────────────────────────────────────
  const saveItem = async () => {
    if (!name.trim()) return;
    setStep('saving');
    try {
      const res = await api.post('/stock/items', {
        name, category, description, quantity: parseFloat(quantity || '0'),
        unit, unit_price: parseFloat(unitPrice || '0'),
        zone_id: zoneId || null, min_stock_alert: minAlert ? parseFloat(minAlert) : null,
        image_url: imageUrl || aiData?.image_path,
        ai_detected_name: aiData?.name, ai_confidence: aiData?.confidence,
      });
      setCreatedItem(res.data.data);
      setStep('done');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur enregistrement');
      setStep('form');
    }
  };

  const totalValue = (parseFloat(quantity || '0') * parseFloat(unitPrice || '0')).toFixed(2);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-[32px] font-bold mb-2">Ajouter un element au stock</h1>
      <p className="text-sm text-storm mb-6">Prenez une photo ou uploadez une image — l'IA identifie l'element automatiquement.</p>

      {/* Step indicators */}
      <div className="flex gap-1 mb-6">
        {['Capture', 'Analyse AI', 'Formulaire', 'Enregistre'].map((s, i) => {
          const steps = ['capture', 'analyzing', 'form', 'done'];
          const current = steps.indexOf(step);
          return (
            <div key={s} className={`flex-1 h-1.5 rounded-full ${i <= current ? 'bg-iris' : 'bg-mist'}`} />
          );
        })}
      </div>

      {/* Canvas for capture — always in DOM */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Single video element — always in DOM, visibility toggled by CSS */}
      <div style={{ display: cameraActive && step === 'capture' ? 'block' : 'none' }}
        className="relative rounded-xl overflow-hidden bg-black mb-4">
        <video ref={videoRef} playsInline muted autoPlay className="w-full" style={{ minHeight: 300 }} />
        <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-3 z-10">
          <button onClick={capturePhoto}
            className="w-16 h-16 bg-white rounded-full border-4 border-iris shadow-lg hover:scale-105 transition" title="Capturer la photo" />
          <button onClick={stopCamera}
            className="px-4 py-2 bg-black/50 text-white rounded-button text-sm backdrop-blur-sm">Annuler</button>
        </div>
      </div>

      {/* ── Step 1: Capture ───────────────────────────────────────── */}
      {step === 'capture' && (
        <div className="space-y-4">
          {/* Selection buttons (hidden when camera is active) */}
          {!cameraActive && (
            <div className="grid grid-cols-3 gap-4">
              {/* Camera stream button */}
              <button onClick={startCamera}
                className="bg-white rounded-card border-2 border-dashed border-iris p-6 text-center hover:bg-[rgba(108,92,231,0.03)] transition">
                <div className="text-4xl mb-2">&#128247;</div>
                <p className="text-sm font-medium">Camera en direct</p>
                <p className="text-xs text-storm mt-1">Flux video + capture</p>
              </button>

              {/* Native camera capture (mobile: opens camera app, desktop: opens file dialog) */}
              <label className="bg-white rounded-card border-2 border-dashed border-iris p-6 text-center cursor-pointer hover:bg-[rgba(108,92,231,0.03)] transition">
                <div className="text-4xl mb-2">&#128248;</div>
                <p className="text-sm font-medium">Photo directe</p>
                <p className="text-xs text-storm mt-1">Ouvre l'appareil photo</p>
                <input type="file" className="hidden" accept="image/*" capture="environment" onChange={handleFileUpload} />
              </label>

              {/* File upload */}
              <label
                onDragOver={e => e.preventDefault()} onDrop={handleDrop}
                className="bg-white rounded-card border-2 border-dashed border-mist p-6 text-center cursor-pointer hover:border-iris transition"
              >
                <div className="text-4xl mb-2">&#128193;</div>
                <p className="text-sm font-medium">Uploader une image</p>
                <p className="text-xs text-storm mt-1">JPG, PNG — glisser ou cliquer</p>
                <input type="file" className="hidden" accept=".jpg,.jpeg,.png,.webp" onChange={handleFileUpload} />
              </label>
            </div>
          )}

          {cameraError && (
            <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 text-xs text-coral">
              {cameraError}
              <p className="mt-1 text-storm">Utilisez "Photo directe" ou "Uploader une image" comme alternative.</p>
            </div>
          )}

          {/* Skip to manual */}
          {!cameraActive && (
            <button onClick={() => setStep('form')}
              className="text-xs text-storm hover:text-iris underline">Saisie manuelle sans image</button>
          )}
        </div>
      )}

      {/* ── Step 2: Analyzing ─────────────────────────────────────── */}
      {step === 'analyzing' && (
        <div className="bg-white rounded-card border border-mist p-8 text-center">
          {previewUrl && (
            <img src={previewUrl} alt="Captured" className="w-48 h-48 object-cover rounded-lg mx-auto mb-4 border border-mist" />
          )}
          <div className="w-12 h-12 border-3 border-iris border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-medium">Identification en cours...</p>
          <p className="text-xs text-storm mt-1">L'IA analyse l'image pour identifier l'element</p>
        </div>
      )}

      {/* ── Step 3: Form ──────────────────────────────────────────── */}
      {step === 'form' && (
        <div className="space-y-4">
          {/* Image preview + AI result */}
          {previewUrl && (
            <div className="flex gap-4 items-start">
              <img src={previewUrl} alt="Captured" className="w-32 h-32 object-cover rounded-lg border border-mist flex-shrink-0" />
              <div className="flex-1">
                {aiData?.confidence > 0 ? (
                  <div className={`p-3 rounded-lg text-sm ${
                    aiData.confidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] border border-mint' :
                    aiData.confidence >= 50 ? 'bg-[#FFF8E1] border border-honey' :
                    'bg-[rgba(255,107,107,0.08)] border border-coral'
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={aiData.confidence >= 80 ? 'success' : aiData.confidence >= 50 ? 'warning' : 'error'}>
                        {aiData.confidence}%
                      </Badge>
                      <span className="font-medium">{aiData.name}</span>
                    </div>
                    <p className="text-xs text-storm">{aiData.description}</p>
                  </div>
                ) : (
                  <div className="p-3 rounded-lg bg-[rgba(255,107,107,0.08)] border border-coral text-sm">
                    <p className="font-medium text-coral">Element non identifie</p>
                    <p className="text-xs text-storm mt-1">Remplissez les champs manuellement ci-dessous.</p>
                  </div>
                )}
                {aiError && <p className="text-xs text-coral mt-2">{aiError}</p>}
                <button onClick={() => { setStep('capture'); setPreviewUrl(null); setAiData(null); setCameraError(''); }}
                  className="text-xs text-iris hover:underline mt-2">Reprendre une photo</button>
              </div>
            </div>
          )}

          {/* AI confidence (when no preview, e.g. manual entry) */}
          {!previewUrl && aiData?.confidence > 0 && (
            <div className={`flex items-center gap-3 p-3 rounded-lg text-sm ${
              aiData.confidence >= 80 ? 'bg-[rgba(85,239,196,0.1)] border border-mint' :
              aiData.confidence >= 50 ? 'bg-[#FFF8E1] border border-honey' :
              'bg-[rgba(255,107,107,0.08)] border border-coral'
            }`}>
              <Badge variant={aiData.confidence >= 80 ? 'success' : aiData.confidence >= 50 ? 'warning' : 'error'}>
                {aiData.confidence}%
              </Badge>
              <span>
                AI identifie : <strong>{aiData.name}</strong>
                {aiData.confidence < 80 && ' — verifiez et corrigez si necessaire'}
              </span>
            </div>
          )}
          {aiError && <div className="p-2 bg-[rgba(255,107,107,0.08)] rounded-lg text-xs text-coral">{aiError}</div>}

          <div className="bg-white rounded-card border border-mist p-6 shadow-card space-y-4">
            {/* Name */}
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Nom de l'element <span className="text-coral">*</span></label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} autoFocus
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
                placeholder="Ciment, Fer a beton, Carrelage..." />
            </div>

            {/* Category + Unit row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Categorie</label>
                <select value={category} onChange={e => setCategory(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Unite</label>
                <select value={unit} onChange={e => setUnit(e.target.value)}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                  {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Description</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none resize-none"
                placeholder="Details, marque, dimensions..." />
            </div>

            {/* Quantity + Price row */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Quantite <span className="text-coral">*</span></label>
                <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)} min="0"
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Prix unitaire (DA) <span className="text-coral">*</span></label>
                <input type="number" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} min="0"
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
                  placeholder="0.00" />
              </div>
              <div>
                <label className="text-sm font-medium text-storm block mb-1">Valeur totale</label>
                <div className="border border-mist rounded-input px-4 py-2.5 text-sm font-mono font-bold bg-[#FAFAFA]">
                  {formatDA(totalValue)}
                </div>
              </div>
            </div>

            {/* Zone selector + create inline */}
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Zone de stockage</label>
              <div className="flex gap-2">
                <select value={zoneId} onChange={e => setZoneId(e.target.value)}
                  className="flex-1 border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                  <option value="">— Aucune zone —</option>
                  {zones.map((z: any) => <option key={z.id} value={z.id}>{z.code} — {z.label}</option>)}
                </select>
                <button onClick={() => setShowZoneForm(!showZoneForm)} type="button"
                  className="px-3 py-2.5 border border-iris text-iris rounded-button text-sm font-medium hover:bg-[rgba(108,92,231,0.05)]">
                  + Zone
                </button>
              </div>
            </div>

            {/* Inline zone creation */}
            {showZoneForm && (
              <div className="bg-[#FAFAFA] rounded-lg p-4 space-y-3">
                <p className="text-xs font-medium text-storm">Nouvelle zone de stockage</p>
                <div className="grid grid-cols-3 gap-2">
                  <input type="text" value={newZoneCode} onChange={e => setNewZoneCode(e.target.value)}
                    className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
                    placeholder="Code (ex: Z-A1)" />
                  <input type="text" value={newZoneLabel} onChange={e => setNewZoneLabel(e.target.value)}
                    className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
                    placeholder="Nom (ex: Depot principal)" />
                  <input type="text" value={newZoneLoc} onChange={e => setNewZoneLoc(e.target.value)}
                    className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
                    placeholder="Lieu (optionnel)" />
                </div>
                <button onClick={createZone} disabled={!newZoneCode.trim() || !newZoneLabel.trim()}
                  className="px-3 py-1.5 bg-iris text-white rounded-button text-xs font-medium disabled:bg-mist">
                  Creer la zone
                </button>
              </div>
            )}

            {/* Alert threshold */}
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Seuil d'alerte stock bas (optionnel)</label>
              <input type="number" value={minAlert} onChange={e => setMinAlert(e.target.value)} min="0"
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none"
                placeholder="Alerte si quantite tombe en dessous de..." />
            </div>
          </div>

          {/* Submit */}
          <button onClick={saveItem} disabled={!name.trim() || !unitPrice}
            className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
            Enregistrer l'element — {formatDA(totalValue)}
          </button>
        </div>
      )}

      {/* ── Step 4: Saving ────────────────────────────────────────── */}
      {step === 'saving' && (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <div className="w-12 h-12 border-3 border-mint border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-medium">Enregistrement en cours...</p>
        </div>
      )}

      {/* ── Step 5: Done ──────────────────────────────────────────── */}
      {step === 'done' && createdItem && (
        <div className="bg-white rounded-card border border-mint p-8 text-center space-y-4">
          <div className="text-5xl">&#10003;</div>
          <h2 className="text-xl font-bold">{createdItem.name}</h2>
          <p className="text-sm text-storm">Code: <span className="font-mono font-bold">{createdItem.code}</span></p>
          <p className="text-sm text-storm">Code-barres: <span className="font-mono">{createdItem.barcode}</span></p>
          <p className="text-lg font-mono font-bold">{formatDA(createdItem.total_value)}</p>
          <div className="flex gap-3 justify-center mt-4">
            <button onClick={() => window.open(`/api/v1/stock/items/${createdItem.id}/barcode-label`, '_blank')}
              className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">
              Imprimer code-barres
            </button>
            <button onClick={() => nav('/stock')}
              className="px-4 py-2 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">
              Voir le catalogue
            </button>
            <button onClick={() => { setStep('capture'); setName(''); setAiData(null); setQuantity('1'); setUnitPrice(''); setDescription(''); }}
              className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-[rgba(108,92,231,0.05)]">
              + Ajouter un autre
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
