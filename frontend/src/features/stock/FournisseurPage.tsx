import { useEffect, useState } from 'react';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const SUPPLIER_CATS = ['MATERIAUX', 'SERVICES', 'EQUIPEMENT', 'SOUS_TRAITANCE', 'TRANSPORT', 'AUTRE'];

export function FournisseurPage() {
  const [data, setData] = useState<any>({ suppliers: [], kpis: {} });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<any>(null);
  // Create supplier modal
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', contact_name: '', phone: '', email: '', address: '', nif: '', rc: '', category: 'MATERIAUX' });
  // Contract modal
  const [showContract, setShowContract] = useState(false);
  const [contractForm, setContractForm] = useState({ label: '', montant_ht: '', tva_rate: '19', description: '', stock_items: [] as any[] });
  const [stockLine, setStockLine] = useState({ name: '', quantity: '', unit_price: '', unit: 'UNITE', category: 'MATERIAU_CONSTRUCTION' });
  // Payment modal
  const [showPayment, setShowPayment] = useState(false);
  const [payForm, setPayForm] = useState({ montant: '', mode_reglement: 'CHEQUE', reference: '', contract_id: '' });

  const loadSuppliers = () => {
    api.get('/suppliers').then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { loadSuppliers(); }, []);

  const loadDetail = (id: string) => {
    api.get(`/suppliers/${id}`).then(r => setDetail(r.data.data)).catch(() => {});
  };

  const createSupplier = async () => {
    try {
      const res = await api.post('/suppliers', form);
      setShowCreate(false);
      setForm({ name: '', contact_name: '', phone: '', email: '', address: '', nif: '', rc: '', category: 'MATERIAUX' });
      loadSuppliers();
      loadDetail(res.data.data.id);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const createContract = async () => {
    if (!detail) return;
    try {
      await api.post(`/suppliers/${detail.id}/contracts`, {
        ...contractForm,
        montant_ht: parseFloat(contractForm.montant_ht),
        tva_rate: parseFloat(contractForm.tva_rate),
        stock_items: contractForm.stock_items,
      });
      setShowContract(false);
      setContractForm({ label: '', montant_ht: '', tva_rate: '19', description: '', stock_items: [] });
      loadDetail(detail.id);
      loadSuppliers();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const addStockLine = () => {
    if (!stockLine.name || !stockLine.quantity || !stockLine.unit_price) return;
    setContractForm(prev => ({
      ...prev,
      stock_items: [...prev.stock_items, { ...stockLine, quantity: parseFloat(stockLine.quantity), unit_price: parseFloat(stockLine.unit_price) }],
    }));
    setStockLine({ name: '', quantity: '', unit_price: '', unit: 'UNITE', category: 'MATERIAU_CONSTRUCTION' });
  };

  const recordPayment = async () => {
    if (!detail) return;
    try {
      await api.post(`/suppliers/${detail.id}/payments`, {
        ...payForm,
        montant: parseFloat(payForm.montant),
        contract_id: payForm.contract_id || null,
        date_paiement: new Date().toISOString().split('T')[0],
      });
      setShowPayment(false);
      setPayForm({ montant: '', mode_reglement: 'CHEQUE', reference: '', contract_id: '' });
      loadDetail(detail.id);
      loadSuppliers();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const ht = parseFloat(contractForm.montant_ht || '0');
  const tva = ht * parseFloat(contractForm.tva_rate || '19') / 100;
  const ttc = ht + tva;
  const stockTotal = contractForm.stock_items.reduce((s: number, i: any) => s + i.quantity * i.unit_price, 0);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Fournisseurs</h1>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">+ Nouveau fournisseur</button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <div className="bg-white rounded-card border border-mist p-4 shadow-card"><p className="text-xs text-storm">Fournisseurs</p><p className="text-2xl font-bold">{data.kpis.total_suppliers || 0}</p></div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card"><p className="text-xs text-storm">Contrats TTC</p><p className="text-2xl font-bold font-mono">{formatDA(data.kpis.total_contracts_value || '0')}</p></div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card"><p className="text-xs text-storm">Total paye</p><p className="text-2xl font-bold font-mono text-mint">{formatDA(data.kpis.total_paid || '0')}</p></div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card"><p className="text-xs text-storm">Reste a payer</p><p className="text-2xl font-bold font-mono text-coral">{formatDA(data.kpis.total_remaining || '0')}</p></div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Supplier list */}
        <div className="col-span-1 space-y-2">
          {data.suppliers.length === 0 ? (
            <div className="bg-white rounded-card border border-mist p-6 text-center text-storm text-sm">Aucun fournisseur</div>
          ) : data.suppliers.map((s: any) => (
            <div key={s.id} onClick={() => loadDetail(s.id)}
              className={`bg-white rounded-card border p-4 cursor-pointer hover:shadow-md transition ${detail?.id === s.id ? 'border-iris shadow-md' : 'border-mist'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono text-storm">{s.code}</span>
                <Badge variant={s.status === 'ACTIF' ? 'success' : 'neutral'}>{s.status}</Badge>
              </div>
              <p className="text-sm font-semibold">{s.name}</p>
              <div className="flex justify-between text-xs text-storm mt-2">
                <span>{s.contracts_count} contrat(s)</span>
                <span className="font-mono">{formatDA(s.total_remaining)} restant</span>
              </div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <div className="col-span-2">
          {!detail ? (
            <div className="bg-white rounded-card border border-mist p-12 text-center text-storm">Selectionnez un fournisseur</div>
          ) : (
            <div className="space-y-4">
              {/* Header */}
              <div className="bg-white rounded-card border border-mist p-6 shadow-card">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-xl font-bold">{detail.name}</h2>
                    <p className="text-xs font-mono text-storm">{detail.code} {detail.category && `— ${detail.category}`}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => setShowContract(true)} className="px-3 py-1.5 bg-iris text-white rounded-button text-xs font-medium">+ Contrat</button>
                    <button onClick={() => setShowPayment(true)} className="px-3 py-1.5 bg-mint text-white rounded-button text-xs font-medium">+ Paiement</button>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div><span className="text-storm">Total contrats:</span> <span className="font-mono font-bold">{formatDA(detail.total_contracts)}</span></div>
                  <div><span className="text-storm">Paye:</span> <span className="font-mono font-bold text-mint">{formatDA(detail.total_paid)}</span></div>
                  <div><span className="text-storm">Restant:</span> <span className="font-mono font-bold text-coral">{formatDA(detail.total_remaining)}</span></div>
                </div>
                {(detail.phone || detail.email) && (
                  <div className="text-xs text-storm mt-3">{detail.contact_name && `${detail.contact_name} — `}{detail.phone} {detail.email && `— ${detail.email}`}</div>
                )}
              </div>

              {/* Contracts */}
              <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
                <div className="p-4 border-b border-mist"><h3 className="font-semibold">Contrats ({detail.contracts?.length || 0})</h3></div>
                {(detail.contracts || []).length === 0 ? (
                  <p className="p-4 text-sm text-storm">Aucun contrat</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                      <th className="py-2 px-3 text-left text-storm">N</th>
                      <th className="py-2 px-3 text-left text-storm">Objet</th>
                      <th className="py-2 px-3 text-right text-storm">Montant TTC</th>
                      <th className="py-2 px-3 text-right text-storm">Paye</th>
                      <th className="py-2 px-3 text-right text-storm">Restant</th>
                      <th className="py-2 px-3 text-left text-storm">Stock</th>
                      <th className="py-2 px-3 text-left text-storm">Statut</th>
                    </tr></thead>
                    <tbody>
                      {detail.contracts.map((c: any) => (
                        <tr key={c.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                          <td className="py-2 px-3 font-mono text-xs">{c.number}</td>
                          <td className="py-2 px-3">{c.label}</td>
                          <td className="py-2 px-3 text-right font-mono font-bold">{formatDA(c.montant_ttc)}</td>
                          <td className="py-2 px-3 text-right font-mono text-mint">{formatDA(c.total_paid)}</td>
                          <td className="py-2 px-3 text-right font-mono text-coral">{formatDA(c.remaining)}</td>
                          <td className="py-2 px-3 text-xs">{c.stock_items > 0 ? `${c.stock_items} items (${formatDA(c.stock_value)})` : '-'}</td>
                          <td className="py-2 px-3"><Badge variant={c.status === 'ACTIF' ? 'success' : 'neutral'}>{c.status}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Payments */}
              <div className="bg-white rounded-card border border-mist shadow-card overflow-hidden">
                <div className="p-4 border-b border-mist"><h3 className="font-semibold">Paiements ({detail.payments?.length || 0})</h3></div>
                {(detail.payments || []).length === 0 ? (
                  <p className="p-4 text-sm text-storm">Aucun paiement</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead><tr className="bg-[#FAFAFA] border-b border-mist">
                      <th className="py-2 px-3 text-left text-storm">Date</th>
                      <th className="py-2 px-3 text-right text-storm">Montant</th>
                      <th className="py-2 px-3 text-left text-storm">Mode</th>
                      <th className="py-2 px-3 text-left text-storm">Reference</th>
                      <th className="py-2 px-3 text-left text-storm">Statut</th>
                    </tr></thead>
                    <tbody>
                      {detail.payments.map((p: any) => (
                        <tr key={p.id} className="border-b border-mist">
                          <td className="py-2 px-3 text-xs">{p.date}</td>
                          <td className="py-2 px-3 text-right font-mono font-bold">{formatDA(p.montant)}</td>
                          <td className="py-2 px-3 text-xs">{p.mode}</td>
                          <td className="py-2 px-3 text-xs font-mono">{p.reference || '-'}</td>
                          <td className="py-2 px-3"><Badge variant="success">{p.status}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Create Supplier Modal ──────────────────────────────────────── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setShowCreate(false)} />
          <div className="relative bg-white rounded-2xl p-8 w-[500px] shadow-xl">
            <h3 className="text-lg font-bold mb-4">Nouveau fournisseur</h3>
            <div className="space-y-3">
              <input type="text" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} placeholder="Raison sociale *" className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              <div className="grid grid-cols-2 gap-3">
                <input type="text" value={form.contact_name} onChange={e => setForm(f => ({...f, contact_name: e.target.value}))} placeholder="Contact" className="border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
                <input type="text" value={form.phone} onChange={e => setForm(f => ({...f, phone: e.target.value}))} placeholder="Telephone" className="border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              </div>
              <input type="text" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))} placeholder="Email" className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              <input type="text" value={form.address} onChange={e => setForm(f => ({...f, address: e.target.value}))} placeholder="Adresse" className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              <div className="grid grid-cols-3 gap-3">
                <input type="text" value={form.nif} onChange={e => setForm(f => ({...f, nif: e.target.value}))} placeholder="NIF" className="border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
                <input type="text" value={form.rc} onChange={e => setForm(f => ({...f, rc: e.target.value}))} placeholder="RC" className="border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
                <select value={form.category} onChange={e => setForm(f => ({...f, category: e.target.value}))} className="border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                  {SUPPLIER_CATS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm">Annuler</button>
              <button onClick={createSupplier} disabled={!form.name} className="flex-1 py-2.5 bg-iris text-white rounded-button text-sm font-semibold disabled:bg-mist">Creer</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Create Contract Modal ──────────────────────────────────────── */}
      {showContract && detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setShowContract(false)} />
          <div className="relative bg-white rounded-2xl p-8 w-[600px] shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-1">Nouveau contrat — {detail.name}</h3>
            <p className="text-xs text-storm mb-4">Les articles specifies seront automatiquement ajoutes au stock.</p>
            <div className="space-y-3">
              <input type="text" value={contractForm.label} onChange={e => setContractForm(f => ({...f, label: e.target.value}))} placeholder="Objet du contrat *" className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-storm">Montant HT (DA) *</label>
                  <input type="number" value={contractForm.montant_ht} onChange={e => setContractForm(f => ({...f, montant_ht: e.target.value}))} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
                </div>
                <div>
                  <label className="text-xs text-storm">TVA %</label>
                  <input type="number" value={contractForm.tva_rate} onChange={e => setContractForm(f => ({...f, tva_rate: e.target.value}))} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
                </div>
                <div>
                  <label className="text-xs text-storm">Montant TTC</label>
                  <div className="border border-mist rounded-input px-4 py-2.5 text-sm font-mono font-bold bg-[#FAFAFA]">{formatDA(ttc.toFixed(2))}</div>
                </div>
              </div>
              <textarea value={contractForm.description} onChange={e => setContractForm(f => ({...f, description: e.target.value}))} placeholder="Description" rows={2} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none resize-none" />

              {/* Stock items to deliver */}
              <div className="border border-mist rounded-lg p-4 bg-[#FAFAFA]">
                <p className="text-xs font-medium text-storm mb-2">Articles a livrer (ajoutés au stock automatiquement)</p>
                {contractForm.stock_items.length > 0 && (
                  <div className="space-y-1 mb-3">
                    {contractForm.stock_items.map((si: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-xs bg-white p-2 rounded">
                        <span>{si.name}</span>
                        <span className="font-mono">{si.quantity} {si.unit} x {formatDA(si.unit_price)} = {formatDA((si.quantity * si.unit_price).toFixed(2))}</span>
                        <button onClick={() => setContractForm(f => ({...f, stock_items: f.stock_items.filter((_: any, j: number) => j !== i)}))} className="text-coral">x</button>
                      </div>
                    ))}
                    <div className="text-xs font-bold text-right">Total stock: {formatDA(stockTotal.toFixed(2))}</div>
                  </div>
                )}
                <div className="grid grid-cols-5 gap-2">
                  <input type="text" value={stockLine.name} onChange={e => setStockLine(s => ({...s, name: e.target.value}))} placeholder="Article" className="col-span-2 border border-mist rounded-input px-3 py-2 text-xs focus:border-iris outline-none" />
                  <input type="number" value={stockLine.quantity} onChange={e => setStockLine(s => ({...s, quantity: e.target.value}))} placeholder="Qte" className="border border-mist rounded-input px-3 py-2 text-xs font-mono focus:border-iris outline-none" />
                  <input type="number" value={stockLine.unit_price} onChange={e => setStockLine(s => ({...s, unit_price: e.target.value}))} placeholder="Prix U." className="border border-mist rounded-input px-3 py-2 text-xs font-mono focus:border-iris outline-none" />
                  <button onClick={addStockLine} disabled={!stockLine.name} className="bg-iris text-white rounded-button text-xs font-medium disabled:bg-mist">+ Ajouter</button>
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowContract(false)} className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm">Annuler</button>
              <button onClick={createContract} disabled={!contractForm.label || !contractForm.montant_ht} className="flex-1 py-2.5 bg-iris text-white rounded-button text-sm font-semibold disabled:bg-mist">
                Creer contrat {contractForm.stock_items.length > 0 && `+ ${contractForm.stock_items.length} articles`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Payment Modal ──────────────────────────────────────────────── */}
      {showPayment && detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setShowPayment(false)} />
          <div className="relative bg-white rounded-2xl p-8 w-[480px] shadow-xl">
            <h3 className="text-lg font-bold mb-4">Paiement — {detail.name}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-storm">Contrat (optionnel)</label>
                <select value={payForm.contract_id} onChange={e => setPayForm(f => ({...f, contract_id: e.target.value}))} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                  <option value="">— Paiement general —</option>
                  {(detail.contracts || []).map((c: any) => (
                    <option key={c.id} value={c.id}>{c.number} — {c.label} (reste {formatDA(c.remaining)})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-storm">Montant (DA) *</label>
                <input type="number" value={payForm.montant} onChange={e => setPayForm(f => ({...f, montant: e.target.value}))} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-storm">Mode</label>
                  <select value={payForm.mode_reglement} onChange={e => setPayForm(f => ({...f, mode_reglement: e.target.value}))} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                    <option value="CHEQUE">CHEQUE</option>
                    <option value="VIREMENT">VIREMENT</option>
                    <option value="ESPECES">ESPECES</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-storm">Reference</label>
                  <input type="text" value={payForm.reference} onChange={e => setPayForm(f => ({...f, reference: e.target.value}))} placeholder="N cheque / virement" className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowPayment(false)} className="flex-1 py-2.5 border border-mist rounded-button text-sm text-storm">Annuler</button>
              <button onClick={recordPayment} disabled={!payForm.montant} className="flex-1 py-2.5 bg-mint text-white rounded-button text-sm font-semibold disabled:bg-mist">Enregistrer paiement</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
