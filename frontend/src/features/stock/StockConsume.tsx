import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function StockConsume() {
  const [barcode, setBarcode] = useState('');
  const [item, setItem] = useState<any>(null);
  const [quantity, setQuantity] = useState('1');
  const [reason, setReason] = useState('Utilisation chantier');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus the barcode input
  useEffect(() => { inputRef.current?.focus(); }, []);

  const lookup = async () => {
    if (!barcode.trim()) return;
    setError('');
    setItem(null);
    setSuccess('');
    try {
      const res = await api.get(`/stock/lookup/${barcode.trim()}`);
      setItem(res.data.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || `Code "${barcode}" introuvable`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') lookup();
  };

  const consume = async () => {
    if (!item || !quantity) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.post('/stock/consume', {
        barcode: item.barcode,
        quantity: parseFloat(quantity),
        reason,
      });
      const d = res.data.data;
      setSuccess(`${d.consumed} ${d.unit} de "${d.item}" retire(s). Stock restant: ${d.new_quantity} ${d.unit}`);
      setHistory(prev => [{
        item: d.item, code: d.code, consumed: d.consumed,
        old: d.old_quantity, new_qty: d.new_quantity,
        unit: d.unit, low: d.low_stock_alert, time: new Date().toLocaleTimeString('fr-DZ'),
      }, ...prev]);
      // Update item display
      setItem((prev: any) => prev ? { ...prev, quantity: d.new_quantity } : null);
      setQuantity('1');
      // Refocus barcode input for next scan
      setBarcode('');
      setTimeout(() => inputRef.current?.focus(), 100);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erreur de sortie stock');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Sortie de stock</h1>
          <p className="text-sm text-storm">Scannez ou entrez le code-barres pour retirer des elements</p>
        </div>
        <Link to="/stock" className="text-sm text-iris hover:underline">Catalogue</Link>
      </div>

      {/* Barcode input */}
      <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-6">
        <label className="text-sm font-medium text-storm block mb-2">Code-barres ou code article</label>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl">&#128270;</span>
            <input
              ref={inputRef}
              type="text"
              value={barcode}
              onChange={e => setBarcode(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full border border-mist rounded-input pl-12 pr-4 py-3 text-lg font-mono focus:border-iris outline-none"
              placeholder="Scanner ou taper le code..."
              autoFocus
            />
          </div>
          <button onClick={lookup}
            className="px-6 py-3 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
            Rechercher
          </button>
        </div>
        <p className="text-xs text-storm mt-2">Scannez le code-barres avec un lecteur ou entrez le code manuellement (ex: STK-000001 ou 3659222438138)</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-4 mb-4 text-sm text-coral">{error}</div>
      )}

      {/* Success */}
      {success && (
        <div className="bg-[rgba(85,239,196,0.1)] border border-mint rounded-lg p-4 mb-4 text-sm text-mint font-medium">{success}</div>
      )}

      {/* Item found — consume form */}
      {item && (
        <div className="bg-white rounded-card border border-mist p-6 shadow-card mb-6">
          <div className="flex items-start gap-4 mb-4">
            <div className="w-16 h-16 bg-[#FAFAFA] rounded-lg flex items-center justify-center text-3xl text-silver">&#128230;</div>
            <div className="flex-1">
              <h2 className="text-lg font-bold">{item.name}</h2>
              <div className="flex items-center gap-3 text-sm text-storm">
                <span className="font-mono">{item.code}</span>
                <Badge variant="neutral">{item.category?.replace(/_/g, ' ')}</Badge>
                {item.zone && <span>{item.zone.code} — {item.zone.label}</span>}
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold font-mono">{item.quantity} <span className="text-sm text-storm">{item.unit}</span></p>
              <p className="text-xs text-storm">{formatDA(item.unit_price)} / {item.unit}</p>
            </div>
          </div>

          {/* Low stock warning */}
          {item.min_stock_alert && parseFloat(item.quantity) <= parseFloat(item.min_stock_alert) && (
            <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-xs text-coral">
              Stock bas — seuil d'alerte: {item.min_stock_alert} {item.unit}
            </div>
          )}

          {/* Consume form */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Quantite a retirer <span className="text-coral">*</span></label>
              <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)}
                min="1" max={item.quantity}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
              <p className="text-xs text-storm mt-1">Max: {item.quantity} {item.unit}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-storm block mb-1">Motif</label>
              <select value={reason} onChange={e => setReason(e.target.value)}
                className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                <option value="Utilisation chantier">Utilisation chantier</option>
                <option value="Consommation projet">Consommation projet</option>
                <option value="Transfert zone">Transfert zone</option>
                <option value="Casse / perte">Casse / perte</option>
                <option value="Retour fournisseur">Retour fournisseur</option>
                <option value="Autre">Autre</option>
              </select>
            </div>
            <div className="flex items-end">
              <button onClick={consume} disabled={!quantity || parseFloat(quantity) <= 0 || submitting}
                className="w-full py-2.5 bg-coral text-white rounded-button text-sm font-semibold hover:bg-[#E04040] disabled:bg-mist disabled:text-silver">
                {submitting ? 'Retrait...' : `Retirer ${quantity} ${item.unit}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Session history */}
      {history.length > 0 && (
        <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
          <div className="p-4 border-b border-mist"><h3 className="font-semibold">Sorties de cette session ({history.length})</h3></div>
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b border-mist">
              <th className="py-2 px-3 text-left text-storm">Heure</th>
              <th className="py-2 px-3 text-left text-storm">Article</th>
              <th className="py-2 px-3 text-left text-storm">Code</th>
              <th className="py-2 px-3 text-right text-storm">Retire</th>
              <th className="py-2 px-3 text-right text-storm">Restant</th>
              <th className="py-2 px-3 text-left text-storm">Alerte</th>
            </tr></thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i} className="border-b border-mist">
                  <td className="py-2 px-3 text-xs font-mono">{h.time}</td>
                  <td className="py-2 px-3 font-medium">{h.item}</td>
                  <td className="py-2 px-3 text-xs font-mono">{h.code}</td>
                  <td className="py-2 px-3 text-right font-mono text-coral">-{h.consumed} {h.unit}</td>
                  <td className="py-2 px-3 text-right font-mono">{h.new_qty} {h.unit}</td>
                  <td className="py-2 px-3">{h.low && <Badge variant="error">Stock bas</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
