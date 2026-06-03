import { useState, useEffect } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function VisitorPage() {
  const [form, setForm] = useState({ name: '', company: '', host: '', purpose: '', date: new Date().toISOString().slice(0, 10), zones: '["ENTREE","ACCUEIL"]' });
  const [result, setResult] = useState<any>(null);
  const [registering, setRegistering] = useState(false);
  const [visitors, setVisitors] = useState<any[]>([]);

  useEffect(() => {
    // Load today's visitors
    api.get('/drh/visitors').then(r => setVisitors(r.data?.data || [])).catch(() => {});
  }, []);

  const register = async () => {
    setRegistering(true);
    try {
      let zones: string[];
      try { zones = JSON.parse(form.zones); } catch { zones = ['ENTREE', 'ACCUEIL']; }
      const r = await api.post('/agents/drh/visiteurs/register', { ...form, zones });
      setResult(r.data.data);
      setVisitors(v => [r.data.data, ...v]);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setRegistering(false); }
  };

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Gestion Visiteurs</h1>
      <p className="text-sm text-storm mb-6">Enregistrez les visiteurs et generez des QR codes d'acces temporaire.</p>

      <div className="grid grid-cols-3 gap-6">
        {/* Registration form */}
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <h2 className="font-semibold">Enregistrer un visiteur</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Nom du visiteur <span className="text-coral">*</span></label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" placeholder="Brahim Saidi" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Societe</label>
              <input value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" placeholder="Nom entreprise" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Hote (employe) <span className="text-coral">*</span></label>
              <input value={form.host} onChange={e => setForm(f => ({ ...f, host: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" placeholder="Hamdi Karim" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Objet de visite</label>
              <input value={form.purpose} onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" placeholder="Reunion commerciale" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Date</label>
              <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Zones autorisees (JSON)</label>
              <input value={form.zones} onChange={e => setForm(f => ({ ...f, zones: e.target.value }))}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm font-mono focus:border-iris outline-none" />
            </div>
          </div>
          <button onClick={register} disabled={!form.name || !form.host || registering}
            className="px-6 py-2.5 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
            {registering ? 'Generation QR...' : 'Enregistrer et generer QR'}
          </button>
        </div>

        {/* QR Result */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-3">QR Code</h2>
          {result ? (
            <div className="text-center space-y-3">
              <div className="w-40 h-40 mx-auto bg-charcoal rounded-xl flex items-center justify-center">
                <span className="text-white text-xs font-mono break-all p-2">{result.qr_code}</span>
              </div>
              <p className="font-bold text-iris">{result.visitor}</p>
              <p className="text-sm text-storm">Hote: {result.host}</p>
              <div className="flex flex-wrap gap-1 justify-center">
                {result.zones?.map((z: string) => (
                  <Badge key={z} variant="info">{z}</Badge>
                ))}
              </div>
              <p className="text-xs text-storm">Valide: {result.valid_from}</p>
              <Badge variant="success">ACTIF</Badge>
            </div>
          ) : (
            <div className="text-center py-8 text-storm">
              <p className="text-3xl mb-2">📱</p>
              <p className="text-sm">Le QR code apparaitra ici apres enregistrement</p>
            </div>
          )}
        </div>
      </div>

      {/* Today's visitors */}
      {visitors.length > 0 && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mt-6">
          <h2 className="font-semibold mb-4">Visiteurs du jour ({visitors.length})</h2>
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Visiteur</th>
              <th className="py-2 text-left text-storm font-medium">Hote</th>
              <th className="py-2 text-left text-storm font-medium">QR Code</th>
              <th className="py-2 text-left text-storm font-medium">Zones</th>
              <th className="py-2 text-center text-storm font-medium">Statut</th>
            </tr></thead>
            <tbody>
              {visitors.map((v: any, i: number) => (
                <tr key={i} className="border-b border-mist">
                  <td className="py-2 font-medium">{v.visitor || v.name}</td>
                  <td className="py-2 text-storm">{v.host}</td>
                  <td className="py-2 font-mono text-xs text-iris">{v.qr_code}</td>
                  <td className="py-2">{(v.zones || []).map((z: string) => <Badge key={z} variant="info">{z}</Badge>)}</td>
                  <td className="py-2 text-center"><Badge variant="success">{v.status || 'ACTIF'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
