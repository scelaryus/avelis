import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const CATEGORIES = [
  '', 'MATERIAU_CONSTRUCTION', 'EQUIPEMENT', 'OUTILLAGE', 'PLOMBERIE',
  'ELECTRICITE', 'MENUISERIE', 'PEINTURE', 'REVETEMENT',
  'QUINCAILLERIE', 'SECURITE', 'MOBILIER', 'INFORMATIQUE',
  'FOURNITURE_BUREAU', 'VEHICULE', 'EPI', 'AUTRE',
];

export function StockCatalogue() {
  const [items, setItems] = useState<any[]>([]);
  const [kpis, setKpis] = useState<any>({});
  const [zones, setZones] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  // Filters
  const [search, setSearch] = useState('');
  const [filterZone, setFilterZone] = useState('');
  const [filterCat, setFilterCat] = useState('');
  const [filterLowStock, setFilterLowStock] = useState(false);
  // Detail modal
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // Zone management
  const [showZones, setShowZones] = useState(false);

  const loadItems = () => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (filterZone) params.set('zone_id', filterZone);
    if (filterCat) params.set('category', filterCat);
    if (filterLowStock) params.set('low_stock', 'true');
    api.get(`/stock/items?${params}`).then(r => {
      const d = r.data.data || {};
      setItems(d.items || []);
      setKpis(d.kpis || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { loadItems(); }, [search, filterZone, filterCat, filterLowStock]);
  useEffect(() => {
    api.get('/stock/zones').then(r => setZones(r.data.data || [])).catch(() => {});
  }, []);

  const openDetail = async (itemId: string) => {
    setDetailLoading(true);
    try {
      const r = await api.get(`/stock/items/${itemId}`);
      setDetail(r.data.data);
    } catch { }
    finally { setDetailLoading(false); }
  };

  const printBarcode = (itemId: string) => {
    window.open(`/api/v1/stock/items/${itemId}/barcode-label`, '_blank');
  };

  const printAllBarcodes = () => {
    // Open a page that prints all visible items
    const ids = items.map(i => i.id);
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><title>Etiquettes Stock</title>
      <style>
        body { font-family: Arial; padding: 10px; }
        .grid { display: flex; flex-wrap: wrap; gap: 10px; }
        .label { border: 1px solid #ccc; padding: 10px; width: 220px; text-align: center; page-break-inside: avoid; }
        .label h4 { margin: 0; font-size: 12px; }
        .label .code { font-family: monospace; font-size: 10px; color: #666; }
        .label .barcode { font-family: monospace; font-size: 11px; letter-spacing: 2px; margin: 5px 0; }
        .label .info { font-size: 9px; color: #888; }
        @media print { button { display: none; } }
      </style></head><body>
      <button onclick="window.print()" style="padding:8px 20px;margin:10px;font-size:14px;">Imprimer toutes les etiquettes</button>
      <div class="grid">`);
    items.forEach(item => {
      w.document.write(`<div class="label">
        <h4>${item.name.substring(0, 40)}</h4>
        <div class="code">${item.code}</div>
        <div class="barcode">${item.barcode}</div>
        <div class="info">${item.category || ''} | ${item.unit} | Qty: ${item.quantity}</div>
      </div>`);
    });
    w.document.write('</div></body></html>');
    w.document.close();
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Stock & Inventaire</h1>
          <p className="text-sm text-storm">Catalogue des elements avec codes-barres</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowZones(!showZones)}
            className="px-4 py-2 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]">
            Zones ({zones.length})
          </button>
          <button onClick={printAllBarcodes} disabled={items.length === 0}
            className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-[rgba(108,92,231,0.05)] disabled:opacity-50">
            Imprimer codes-barres ({items.length})
          </button>
          <Link to="/stock/new"
            className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
            + Ajouter un element
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Elements en stock</p>
          <p className="text-2xl font-bold">{kpis.total_items || 0}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Valeur totale</p>
          <p className="text-2xl font-bold font-mono">{formatDA(kpis.total_value || '0')}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Alertes stock bas</p>
          <p className={`text-2xl font-bold ${parseInt(kpis.low_stock_count || '0') > 0 ? 'text-coral' : 'text-mint'}`}>
            {kpis.low_stock_count || 0}
          </p>
        </div>
      </div>

      {/* Zone management panel */}
      {showZones && (
        <div className="bg-white rounded-card border border-mist p-4 mb-4 shadow-card">
          <h3 className="font-semibold mb-3">Zones de stockage</h3>
          <div className="grid grid-cols-4 gap-2">
            {zones.map((z: any) => (
              <div key={z.id} className="border border-mist rounded-lg p-3">
                <p className="text-sm font-bold">{z.code}</p>
                <p className="text-xs text-storm">{z.label}</p>
                {z.location && <p className="text-xs text-silver">{z.location}</p>}
                <p className="text-xs text-storm mt-1">{z.item_count || 0} elements</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          className="flex-1 border border-mist rounded-input px-4 py-2 text-sm focus:border-iris outline-none"
          placeholder="Rechercher par nom ou code..." />
        <select value={filterZone} onChange={e => setFilterZone(e.target.value)}
          className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
          <option value="">Toutes zones</option>
          {zones.map((z: any) => <option key={z.id} value={z.id}>{z.code} — {z.label}</option>)}
        </select>
        <select value={filterCat} onChange={e => setFilterCat(e.target.value)}
          className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
          <option value="">Toutes categories</option>
          {CATEGORIES.filter(Boolean).map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-storm cursor-pointer">
          <input type="checkbox" checked={filterLowStock} onChange={e => setFilterLowStock(e.target.checked)} />
          Stock bas
        </label>
      </div>

      {/* Items grid */}
      {items.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <p className="text-storm">Aucun element en stock.</p>
          <Link to="/stock/new" className="text-iris hover:underline text-sm mt-2 inline-block">Ajouter le premier element</Link>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {items.map((item: any) => (
            <div key={item.id} className={`bg-white rounded-card border shadow-card overflow-hidden hover:shadow-lg transition cursor-pointer ${item.low_stock ? 'border-coral' : 'border-mist'}`}
              onClick={() => openDetail(item.id)}>
              {/* Image placeholder */}
              <div className="h-32 bg-[#FAFAFA] flex items-center justify-center text-4xl text-silver">
                {item.image_url ? (
                  <img src={`/api/v1/stock/items/${item.id}/image`} alt="" className="w-full h-full object-cover"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                ) : null}
                <span>&#128230;</span>
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-storm">{item.code}</span>
                  {item.low_stock && <Badge variant="error">Stock bas</Badge>}
                </div>
                <h3 className="text-sm font-semibold mb-1 truncate">{item.name}</h3>
                <div className="flex items-center justify-between text-xs text-storm">
                  <span>{item.quantity} {item.unit}</span>
                  <span className="font-mono font-bold">{formatDA(item.unit_price)}/{item.unit}</span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <Badge variant="neutral">{(item.category || 'AUTRE').replace(/_/g, ' ')}</Badge>
                  <span className="text-xs font-mono font-bold">{formatDA(item.total_value)}</span>
                </div>
                {/* Mini barcode */}
                <div className="mt-2 pt-2 border-t border-mist text-center">
                  <span className="text-[10px] font-mono text-silver tracking-widest">{item.barcode}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setDetail(null)} />
          <div className="relative bg-white rounded-2xl p-8 w-[560px] shadow-xl max-h-[85vh] overflow-y-auto">
            {detailLoading ? (
              <div className="p-8 text-center"><div className="w-8 h-8 border-2 border-iris border-t-transparent rounded-full animate-spin mx-auto" /></div>
            ) : detail ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold">{detail.name}</h2>
                    <p className="text-sm font-mono text-storm">{detail.code}</p>
                  </div>
                  <button onClick={() => printBarcode(detail.id)}
                    className="px-3 py-1.5 bg-iris text-white rounded-button text-xs font-medium">Imprimer code-barres</button>
                </div>

                {detail.ai_detected_name && (
                  <div className="text-xs p-2 bg-[#FAFAFA] rounded-lg">
                    AI: <strong>{detail.ai_detected_name}</strong> ({detail.ai_confidence}% confiance)
                  </div>
                )}

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-[#FAFAFA] rounded-lg p-3"><p className="text-xs text-storm">Quantite</p><p className="text-lg font-bold">{detail.quantity} {detail.unit}</p></div>
                  <div className="bg-[#FAFAFA] rounded-lg p-3"><p className="text-xs text-storm">Prix unitaire</p><p className="text-lg font-bold font-mono">{formatDA(detail.unit_price)}</p></div>
                  <div className="bg-[#FAFAFA] rounded-lg p-3"><p className="text-xs text-storm">Valeur totale</p><p className="text-lg font-bold font-mono">{formatDA(detail.total_value)}</p></div>
                </div>

                {detail.zone && (
                  <div className="text-sm"><span className="text-storm">Zone:</span> <strong>{detail.zone.code}</strong> — {detail.zone.label}</div>
                )}

                {detail.description && <p className="text-sm text-storm">{detail.description}</p>}

                {/* Barcode */}
                <div className="text-center p-4 bg-[#FAFAFA] rounded-lg">
                  <p className="font-mono text-lg tracking-[4px] mb-1">{detail.barcode}</p>
                  <p className="text-xs text-storm">Code-barres EAN-13</p>
                </div>

                {/* Movement history */}
                {detail.movements?.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Mouvements ({detail.movements.length})</h3>
                    <div className="space-y-1">
                      {detail.movements.map((m: any) => (
                        <div key={m.id} className="flex items-center justify-between text-xs p-2 border-b border-mist">
                          <Badge variant={m.type === 'ENTREE' ? 'success' : m.type === 'SORTIE' ? 'error' : 'warning'}>{m.type}</Badge>
                          <span className="font-mono">{m.type === 'SORTIE' ? '-' : '+'}{m.quantity}</span>
                          <span className="text-storm">{m.reason}</span>
                          <span className="text-storm">{new Date(m.date).toLocaleDateString('fr-DZ')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button onClick={() => setDetail(null)} className="w-full py-2 border border-mist rounded-button text-sm text-storm">Fermer</button>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
