import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

const STAGE_COLORS: Record<string, string> = {
  ouvert: '#0984E3', mise_en_demeure: '#FDCB6E', negociation: '#6C5CE7',
  audience_programmee: '#FF6B6B', en_delibere: '#FD79A8', jugement: '#00B894',
  appel: '#E17055', cloture: '#636E72',
};
const PRIO_V: Record<string, 'error'|'warning'|'info'|'neutral'> = { critique: 'error', important: 'warning', normal: 'info', mineur: 'neutral' };
const EVT_ICONS: Record<string, string> = {
  CREATION: '📋', STAGE_CHANGE: '🔄', NOTE: '📝', DOCUMENT: '📎', COST: '💰', AUDIENCE: '⚖️', JUGEMENT: '🔨', CLOTURE: '✅',
};

export function CaseDetail() {
  const { caseId } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  // Stage change
  const [showStageForm, setShowStageForm] = useState(false);
  const [newStage, setNewStage] = useState('');
  const [stageComment, setStageComment] = useState('');
  // Add event
  const [showEventForm, setShowEventForm] = useState(false);
  const [eventType, setEventType] = useState('NOTE');
  const [eventTitle, setEventTitle] = useState('');
  const [eventDesc, setEventDesc] = useState('');
  const [eventAmount, setEventAmount] = useState('');
  const [proofId, setProofId] = useState('');

  const reload = () => {
    if (!caseId) return;
    setLoading(true);
    api.get(`/juridique/cases/${caseId}`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { reload(); }, [caseId]);

  const changeStage = async () => {
    try {
      await api.patch(`/juridique/cases/${caseId}/stage`, { new_stage: newStage, title: stageComment, description: stageComment });
      setShowStageForm(false); setStageComment(''); reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  const addEvent = async () => {
    try {
      await api.post(`/juridique/cases/${caseId}/event`, {
        event_type: eventType, title: eventTitle, description: eventDesc,
        amount: eventAmount ? parseFloat(eventAmount) : null,
        cost_type: eventType === 'COST' ? 'honoraires' : undefined,
        document_id: proofId || undefined,
      });
      setShowEventForm(false); setEventTitle(''); setEventDesc(''); setEventAmount(''); reload();
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Dossier introuvable</p>;

  const riskColor = data.ai_risk_score >= 60 ? '#FF6B6B' : data.ai_risk_score >= 40 ? '#FDCB6E' : '#00B894';

  return (
    <div>
      <Link to="/juridique/cases" className="text-sm text-iris hover:underline">&larr; Dossiers Litiges</Link>

      {/* Header */}
      <div className="flex items-start justify-between mt-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-mono text-storm">{data.name}</span>
            <Badge variant={PRIO_V[data.priority] || 'neutral'}>{data.priority}</Badge>
            <span className="text-xs font-bold text-white px-2 py-0.5 rounded" style={{ background: STAGE_COLORS[data.stage] || '#636E72' }}>
              {data.stage.replace(/_/g, ' ').toUpperCase()}
            </span>
            {data.is_confidential && <Badge variant="error">CONFIDENTIEL</Badge>}
          </div>
          <h1 className="text-2xl font-bold">{data.title}</h1>
          <p className="text-sm text-storm mt-1">Ouvert le {data.date_open} — {data.days_open} jours</p>
        </div>
        {data.ai_risk_score !== null && (
          <div className="text-center">
            <div className="w-16 h-16 rounded-full border-4 flex items-center justify-center text-lg font-bold" style={{ borderColor: riskColor, color: riskColor }}>
              {data.ai_risk_score}%
            </div>
            <p className="text-[10px] text-storm mt-1">Risque IA</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Info card */}
        <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card space-y-4">
          <p className="text-sm">{data.description}</p>
          {data.ai_summary && (
            <div className="bg-[rgba(108,92,231,0.06)] rounded-lg p-3">
              <span className="text-xs font-bold text-white bg-iris px-2 py-0.5 rounded">ANALYSE IA</span>
              <p className="text-sm mt-2">{data.ai_summary}</p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-storm">Partie adverse:</span> <strong>{data.partner_name}</strong></div>
            <div><span className="text-storm">Avocat adverse:</span> {data.partner_lawyer || '—'}</div>
            <div><span className="text-storm">Notre avocat:</span> {data.company_lawyer || '—'}</div>
            <div><span className="text-storm">Juriste:</span> {data.assigned_juriste || '—'}</div>
            {data.project_code && <div><span className="text-storm">Projet:</span> <strong>{data.project_code}</strong></div>}
            {data.employee_name && <div><span className="text-storm">Employe:</span> {data.employee_name}</div>}
            {data.contract_ref && <div><span className="text-storm">Contrat:</span> {data.contract_ref}</div>}
            {data.date_deadline && <div><span className="text-storm">Prochaine echeance:</span> <strong className="text-coral">{data.date_deadline}</strong></div>}
          </div>
        </div>

        {/* Financial card */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h3 className="font-semibold mb-3">Enjeux financiers</h3>
          <div className="space-y-3">
            <div><p className="text-xs text-storm">Montant reclame</p><p className="text-xl font-bold font-mono">{formatDA(data.amount_claimed)}</p></div>
            <div><p className="text-xs text-storm">Montant recupere</p><p className="text-lg font-bold font-mono text-mint">{formatDA(data.amount_recovered)}</p></div>
            <div className="border-t border-mist pt-3">
              <p className="text-xs text-storm">Couts du dossier</p>
              <div className="space-y-1 mt-1 text-sm">
                <div className="flex justify-between"><span className="text-storm">Honoraires</span><span className="font-mono">{formatDA(data.cost_honoraires)}</span></div>
                <div className="flex justify-between"><span className="text-storm">Frais justice</span><span className="font-mono">{formatDA(data.cost_frais_justice)}</span></div>
                <div className="flex justify-between"><span className="text-storm">Expertise</span><span className="font-mono">{formatDA(data.cost_expertise)}</span></div>
                <div className="flex justify-between border-t border-mist pt-1 font-bold"><span>Total couts</span><span className="font-mono text-coral">{formatDA(data.cost_total)}</span></div>
              </div>
            </div>
            {data.result !== 'en_cours' && (
              <div className="border-t border-mist pt-3">
                <p className="text-xs text-storm">Resultat</p>
                <Badge variant={data.result === 'gagne' ? 'success' : data.result === 'perdu' ? 'error' : 'warning'}>{data.result}</Badge>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-6">
        <button onClick={() => setShowStageForm(true)} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800">
          Changer le stade
        </button>
        <button onClick={() => { setShowEventForm(true); setEventType('NOTE'); }} className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-[rgba(108,92,231,0.05)]">
          Ajouter une note
        </button>
        <button onClick={() => { setShowEventForm(true); setEventType('DOCUMENT'); }} className="px-4 py-2 border border-mist text-storm rounded-button text-sm font-medium hover:bg-gray-50">
          Joindre un document
        </button>
        <button onClick={() => { setShowEventForm(true); setEventType('COST'); }} className="px-4 py-2 border border-mist text-storm rounded-button text-sm font-medium hover:bg-gray-50">
          Enregistrer un cout
        </button>
      </div>

      {/* Stage change form */}
      {showStageForm && (
        <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-6 space-y-3">
          <h3 className="font-semibold">Changer le stade du dossier</h3>
          <p className="text-xs text-storm">Stade actuel: <strong>{data.stage}</strong></p>
          <div className="flex flex-wrap gap-2">
            {(data.available_stages || []).map((s: string) => (
              <button key={s} onClick={() => setNewStage(s)}
                className={`px-3 py-2 rounded-lg border-2 text-sm font-medium transition ${newStage === s ? 'border-iris bg-[rgba(108,92,231,0.06)]' : 'border-mist hover:border-lavender'}`}>
                {s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          <textarea value={stageComment} onChange={e => setStageComment(e.target.value)} rows={2}
            className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none" placeholder="Commentaire sur le changement..." />
          <div className="flex gap-2">
            <button onClick={changeStage} disabled={!newStage} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium disabled:bg-mist disabled:text-silver">Confirmer</button>
            <button onClick={() => setShowStageForm(false)} className="px-4 py-2 border border-mist rounded-button text-sm text-storm">Annuler</button>
          </div>
        </div>
      )}

      {/* Add event form */}
      {showEventForm && (
        <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-6 space-y-3">
          <h3 className="font-semibold">Ajouter: {eventType === 'NOTE' ? 'Note' : eventType === 'DOCUMENT' ? 'Document' : eventType === 'COST' ? 'Cout' : 'Evenement'}</h3>
          <input value={eventTitle} onChange={e => setEventTitle(e.target.value)}
            className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" placeholder="Titre" />
          <textarea value={eventDesc} onChange={e => setEventDesc(e.target.value)} rows={2}
            className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none" placeholder="Description..." />
          {eventType === 'COST' && (
            <input type="number" value={eventAmount} onChange={e => setEventAmount(e.target.value)}
              className="w-full border border-mist rounded-input px-3 py-2 text-sm font-mono focus:border-iris outline-none" placeholder="Montant DA" />
          )}
          {eventType === 'DOCUMENT' && <ProofUpload onUploaded={id => setProofId(id)} label="Document a joindre" />}
          <div className="flex gap-2">
            <button onClick={addEvent} disabled={!eventTitle} className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium disabled:bg-mist disabled:text-silver">Enregistrer</button>
            <button onClick={() => setShowEventForm(false)} className="px-4 py-2 border border-mist rounded-button text-sm text-storm">Annuler</button>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h3 className="font-semibold mb-4">Historique du dossier ({data.events?.length || 0} evenements)</h3>
        {(data.events || []).length === 0 ? (
          <p className="text-sm text-storm text-center py-4">Aucun evenement</p>
        ) : (
          <div className="space-y-3">
            {data.events.map((ev: any) => (
              <div key={ev.id} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-8 h-8 rounded-full bg-[#FAFAFA] border border-mist flex items-center justify-center text-sm">
                    {EVT_ICONS[ev.type] || '📌'}
                  </div>
                  <div className="w-px flex-1 bg-mist" />
                </div>
                <div className="flex-1 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={ev.type === 'STAGE_CHANGE' ? 'info' : ev.type === 'COST' ? 'warning' : ev.type === 'DOCUMENT' ? 'success' : 'neutral'}>{ev.type}</Badge>
                    <span className="text-sm font-semibold">{ev.title}</span>
                    <span className="text-[10px] text-storm ml-auto">{ev.date?.slice(0, 10)}</span>
                  </div>
                  {ev.description && <p className="text-sm text-storm">{ev.description}</p>}
                  {ev.old_stage && ev.new_stage && (
                    <p className="text-xs mt-1">
                      <span className="px-1.5 py-0.5 rounded text-white text-[9px]" style={{ background: STAGE_COLORS[ev.old_stage] || '#636E72' }}>{ev.old_stage}</span>
                      <span className="mx-1">&rarr;</span>
                      <span className="px-1.5 py-0.5 rounded text-white text-[9px]" style={{ background: STAGE_COLORS[ev.new_stage] || '#636E72' }}>{ev.new_stage}</span>
                    </p>
                  )}
                  {ev.amount && <p className="text-xs font-mono text-coral mt-1">{formatDA(ev.amount)}</p>}
                  {ev.document_id && <p className="text-xs text-iris mt-1">📎 {ev.document_id}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
