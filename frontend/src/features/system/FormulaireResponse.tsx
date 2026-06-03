import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function FormulaireResponse() {
  const { code } = useParams();
  const nav = useNavigate();
  const [form, setForm] = useState<any>(null);
  const [responses, setResponses] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/formulaires/${code}`).then(r => { setForm(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [code]);

  if (loading) return <div className="max-w-2xl mx-auto"><div className="h-64 bg-mist rounded-card animate-pulse" /></div>;
  if (!form) return <p className="text-storm">Formulaire introuvable</p>;

  const allFilled = (form.fields || []).filter((f: any) => f.required).every((f: any) => responses[f.key]);

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post(`/formulaires/${code}/respond`, { field_responses: responses });
      nav('/system/formulaires');
    } catch {} finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-card border border-[#E0E0E0] p-8 shadow-card">
        <div className="flex items-center gap-3 mb-2">
          <Badge variant={form.priority === 'CRITIQUE' ? 'error' : form.priority === 'ÉLEVÉE' ? 'warning' : 'info'}>{form.priority}</Badge>
          <span className="font-mono text-xs text-storm">{code}</span>
        </div>
        <h1 className="text-2xl font-bold mb-2">Action requise — {form.title}</h1>

        <div className="bg-[#FAFAFA] rounded-lg p-4 mb-6 text-sm text-storm">{form.context || form.question}</div>

        {form.blocked_module && (
          <div className="bg-[rgba(255,107,107,0.06)] border border-coral/30 rounded-lg p-3 mb-6 text-sm">
            <span className="text-coral font-semibold">Module bloqué :</span> {form.blocked_module}
          </div>
        )}

        <div className="space-y-5 mb-8">
          {(form.fields || []).map((f: any) => (
            <div key={f.key}>
              <label className="text-sm font-medium text-storm block mb-1.5">
                {f.label} {f.required && <span className="text-coral">*</span>}
              </label>
              {f.ai_suggestion && (
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs bg-lavender/20 text-iris px-2 py-0.5 rounded font-medium">
                    Suggestion IA (confiance {f.ai_confidence || 82}%)
                  </span>
                  <button onClick={() => setResponses(p => ({ ...p, [f.key]: f.ai_suggestion }))} className="text-xs text-iris hover:underline">Accepter</button>
                </div>
              )}
              {f.type === 'SELECT' ? (
                <select value={responses[f.key] || ''} onChange={e => setResponses(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
                  <option value="">Sélectionnez</option>
                  {(f.options || []).map((o: string) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : f.type === 'NUMBER' ? (
                <input type="number" value={responses[f.key] || ''} onChange={e => setResponses(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm font-mono focus:border-iris outline-none" />
              ) : f.type === 'DATE' ? (
                <input type="date" value={responses[f.key] || ''} onChange={e => setResponses(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              ) : f.type === 'FILE_UPLOAD' ? (
                <input type="file" onChange={e => setResponses(p => ({ ...p, [f.key]: e.target.files?.[0]?.name || '' }))}
                  className="w-full text-sm" />
              ) : (
                <input type="text" value={responses[f.key] || ''} onChange={e => setResponses(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.ai_suggestion || f.placeholder || ''}
                  className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none" />
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button onClick={submit} disabled={!allFilled || submitting}
            className="flex-1 py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
            {submitting ? 'Envoi en cours...' : 'Soumettre la réponse'}
          </button>
          <button onClick={() => { /* Decline generates new formulaire */ }}
            className="px-6 py-3 rounded-button border border-mist text-storm text-sm font-medium hover:bg-gray-50">
            Décliner
          </button>
        </div>
        {/* NO close button — formulaire is mandatory */}
      </div>
    </div>
  );
}
