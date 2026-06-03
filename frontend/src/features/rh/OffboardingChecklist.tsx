import { useEffect, useState } from 'react';
import api from '../../lib/api-client';

export function OffboardingChecklist() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/drh/offboarding/emp-001/checklist').then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-20 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Aucun processus de départ actif</p>;

  const blocks = [
    { key: 'handover_pv', label: 'PV de Passation', desc: 'Passation de consignes signée' },
    { key: 'equipment_quitus', label: 'Quitus Matériel', desc: 'Tous les équipements restitués' },
    { key: 'badge_deactivated', label: 'Badge Désactivé', desc: 'Badge RFID révoqué sur tous les contrôleurs' },
    { key: 'digital_access', label: 'Accès Numériques', desc: 'Tous les comptes désactivés' },
    { key: 'stc_verified', label: 'STC Vérifié L1-L6', desc: 'Solde de tout compte vérifié par le pipeline' },
    { key: 'stc_approved', label: 'STC Approuvé', desc: 'Triple approbation DRH/DG/PDG' },
  ];

  const allDone = blocks.every(b => data.blocks[b.key]);

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-6">Checklist Départ</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        {blocks.map(b => {
          const done = data.blocks[b.key];
          return (
            <div key={b.key} className={`bg-white rounded-card border-2 p-5 transition ${done ? 'border-mint' : 'border-coral'}`}>
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${done ? 'bg-mint' : 'bg-coral'}`}>
                  {done ? '✓' : '✗'}
                </div>
                <h3 className="font-semibold">{b.label}</h3>
              </div>
              <p className="text-sm text-storm">{b.desc}</p>
            </div>
          );
        })}
      </div>

      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Paiement STC</h2>
            {!allDone && (
              <div className="mt-2">
                <p className="text-sm text-coral font-medium">Bloqué — prérequis manquants :</p>
                <ul className="text-sm text-storm mt-1 list-disc list-inside">
                  {data.stc_blockers?.map((b: string, i: number) => <li key={i}>{b}</li>)}
                </ul>
              </div>
            )}
          </div>
          <button disabled={!allDone}
            className={`px-6 py-3 rounded-lg font-semibold transition ${
              allDone ? 'bg-mint text-white hover:bg-[#00A884]' : 'bg-mist text-silver cursor-not-allowed'}`}
            title={!allDone ? 'Tous les blocs doivent être validés' : ''}>
            Procéder au paiement STC
          </button>
        </div>
      </div>
    </div>
  );
}
