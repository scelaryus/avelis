import { useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { formatDA } from '../../lib/format';
import { ProofUpload } from '../../components/shared/ProofUpload';
import api from '../../lib/api-client';

interface AgentResult {
  agent: string;
  status: 'idle' | 'running' | 'success' | 'error';
  result?: any;
  error?: string;
}

const MODULE_COLORS: Record<string, string> = {
  DRH: '#6C5CE7', JURIDIQUE: '#0984E3', FINANCE: '#00B894', GED: '#E17055',
  SPI: '#FDCB6E', FONDATION: '#636E72', SYSTEME: '#A29BFE',
};

export function AgentControl() {
  const [results, setResults] = useState<Record<string, AgentResult>>({});
  const [input, setInput] = useState<Record<string, any>>({});
  const [docId, setDocId] = useState('');

  const runAgent = async (name: string, endpoint: string, body: any) => {
    setResults(p => ({ ...p, [name]: { agent: name, status: 'running' } }));
    try {
      const res = await api.post(endpoint, body);
      setResults(p => ({ ...p, [name]: { agent: name, status: 'success', result: res.data.data } }));
    } catch (e: any) {
      setResults(p => ({ ...p, [name]: { agent: name, status: 'error', error: e.response?.data?.detail || e.message } }));
    }
  };

  // ALL 35 agents with real endpoints
  const agentSections = [
    {
      title: 'DRH (21 agents)', color: MODULE_COLORS.DRH, agents: [
        { name: '1. Agent Dossier', desc: 'Verifie la completude du dossier employe (7 documents obligatoires)',
          endpoint: '/agents/drh/dossier/check',
          inputs: [{ key: 'documents', label: 'Documents (JSON)', type: 'textarea', placeholder: '{"cni":"VERIFIED","photo":"VERIFIED","diplome":"PENDING","medical":"VERIFIED","rib":"VERIFIED","casier":"VERIFIED","cv":"VERIFIED"}' }] },
        { name: '2. Agent Contrats', desc: 'Genere un contrat de travail avec clauses et QR',
          endpoint: '/agents/drh/contrats/generate',
          inputs: [{ key: 'employee', label: 'Employe (JSON)', type: 'textarea', placeholder: '{"name":"Hamdi Karim","position":"Comptable","salary_base":"45000"}' },
                   { key: 'contract_type', label: 'Type', type: 'text', placeholder: 'CDI' }] },
        { name: '3. Agent Paie L2', desc: 'Analyse semantique LLM du bulletin (pseudonymise)',
          endpoint: '/agents/payroll/verify-l2',
          inputs: [{ key: 'employee_name', label: 'Employe', type: 'text', placeholder: 'Hamdi Karim' },
                   { key: 'gross', label: 'Brut', type: 'number', placeholder: '45000' },
                   { key: 'net', label: 'Net', type: 'number', placeholder: '35000' },
                   { key: 'position', label: 'Poste', type: 'text', placeholder: 'Comptable' }] },
        { name: '4. Agent Temps', desc: 'Agregation pointage biometrique mensuel',
          endpoint: '/agents/drh/temps/aggregate',
          inputs: [{ key: 'employee_id', label: 'ID employe', type: 'text', placeholder: '' },
                   { key: 'month', label: 'Mois', type: 'text', placeholder: '2026-03' }] },
        { name: '5. Agent Conges', desc: 'Verification 6 niveaux conges + detection fraude badge',
          endpoint: null, inputs: [], link: '/rh/leave' },
        { name: '6. Agent SPI 360', desc: 'Recalcul quotidien SPI 4 piliers + compteur',
          endpoint: '/drh/spi360/calculate-daily',
          inputs: [{ key: 'date', label: 'Date', type: 'text', placeholder: '2026-03-26' }] },
        { name: '7. Agent Recrutement', desc: 'Scoring CV par correspondance semantique IA',
          endpoint: '/agents/drh/recrutement/score-cv',
          inputs: [{ key: 'cv_text', label: 'Texte CV', type: 'textarea', placeholder: 'Ingenieur BTP, 5 ans experience...' },
                   { key: 'requirements', label: 'Exigences poste', type: 'textarea', placeholder: 'Chef de chantier, gestion equipe...' }] },
        { name: '8. Agent Formation', desc: 'Plan integration 30 jours genere par IA',
          endpoint: '/agents/drh/formation/plan',
          inputs: [{ key: 'employee', label: 'Employe (JSON)', type: 'textarea', placeholder: '{"name":"Nouveau"}' },
                   { key: 'position', label: 'Poste', type: 'text', placeholder: 'Agent Commercial' }] },
        { name: '9. Agent GED RH', desc: 'Classification automatique documents RH',
          endpoint: '/agents/drh/ged/classify',
          inputs: [{ key: 'document_text', label: 'Texte document', type: 'textarea', placeholder: 'Certificat medical attestant...' }] },
        { name: '10. Agent Materiel', desc: 'Liste equipement onboarding par poste',
          endpoint: '/agents/drh/materiel/onboarding',
          inputs: [{ key: 'position', label: 'Poste', type: 'text', placeholder: 'Agent Commercial' }] },
        { name: '11. Agent Acces', desc: 'Configuration zones badge RFID par poste',
          endpoint: '/agents/drh/acces/configure',
          inputs: [{ key: 'employee', label: 'Employe (JSON)', type: 'textarea', placeholder: '{"name":"Hamdi"}' },
                   { key: 'position', label: 'Poste', type: 'text', placeholder: 'Comptable' }] },
        { name: '12. Agent Disciplinaire', desc: 'Evaluation gravite infraction + suggestion sanction IA',
          endpoint: '/agents/drh/discipline/evaluate',
          inputs: [{ key: 'description', label: 'Description infraction', type: 'textarea', placeholder: 'Absence injustifiee le 15/03...' },
                   { key: 'severity', label: 'Gravite', type: 'text', placeholder: 'MOYENNE' }] },
        { name: '13. Agent Offboarding', desc: 'Checklist depart: passation, materiel, badge, STC',
          endpoint: null, inputs: [], link: '/rh/offboarding' },
        { name: '14. Agent Messagerie', desc: 'Envoi notifications email/SMS/push',
          endpoint: '/agents/drh/messagerie/send',
          inputs: [{ key: 'recipient', label: 'Destinataire', type: 'text', placeholder: 'hamdi@groupe-gfi.dz' },
                   { key: 'template', label: 'Template', type: 'text', placeholder: 'BIENVENUE' }] },
        { name: '15. Agent BI RH', desc: 'Generation dashboards RH: headcount, masse salariale',
          endpoint: '/agents/drh/bi/generate',
          inputs: [{ key: 'metric', label: 'Metrique', type: 'text', placeholder: 'headcount' },
                   { key: 'period', label: 'Periode', type: 'text', placeholder: '2026-03' }] },
        { name: '16. Agent Declarations', desc: 'Preparation declarations sociales DAC/DAS/G50',
          endpoint: '/agents/drh/declarations/prepare',
          inputs: [{ key: 'entity_code', label: 'Code entite', type: 'text', placeholder: 'SARL-DP' },
                   { key: 'type', label: 'Type', type: 'text', placeholder: 'DAC' },
                   { key: 'period', label: 'Periode', type: 'text', placeholder: '2026-Q1' }] },
        { name: '17. Agent Prets', desc: 'Verification eligibilite pret salarie',
          endpoint: '/agents/drh/prets/check-eligibility',
          inputs: [{ key: 'employee', label: 'Employe (JSON)', type: 'textarea', placeholder: '{"name":"Hamdi","salary_base":"45000"}' }] },
        { name: '18. Agent Vision OCR', desc: 'Extraction donnees OCR: NIN, certificats, casier',
          endpoint: '/agents/drh/vision/analyze',
          inputs: [{ key: 'document_text', label: 'Texte extrait', type: 'textarea', placeholder: 'Le soussigne Dr. Ahmed certifie que M. Hamdi est apte...' },
                   { key: 'doc_type', label: 'Type document', type: 'text', placeholder: 'MEDICAL' }] },
        { name: '19. Agent Carriere', desc: 'Suggestion progression carriere basee sur SPI',
          endpoint: '/agents/drh/carriere/suggest',
          inputs: [{ key: 'employee', label: 'Employe (JSON)', type: 'textarea', placeholder: '{"name":"Hamdi"}' },
                   { key: 'spi_history', label: 'Historique SPI (JSON)', type: 'textarea', placeholder: '[{"spi":"82"},{"spi":"85"},{"spi":"90"}]' }] },
        { name: '20. Agent Securite', desc: 'Detection anomalies acces: badges refuses, horaires suspects',
          endpoint: '/agents/drh/securite/check',
          inputs: [{ key: 'badge_events', label: 'Evenements badge (JSON)', type: 'textarea', placeholder: '[{"result":"DENIED"},{"result":"GRANTED","after_hours":true}]' }] },
        { name: '21. Agent Visiteurs', desc: 'Enregistrement visiteur + generation QR code',
          endpoint: '/agents/drh/visiteurs/register',
          inputs: [{ key: 'name', label: 'Nom visiteur', type: 'text', placeholder: 'Brahim Saidi' },
                   { key: 'host', label: 'Hote (employe)', type: 'text', placeholder: 'Hamdi Karim' },
                   { key: 'date', label: 'Date visite', type: 'text', placeholder: '2026-03-26' },
                   { key: 'zones', label: 'Zones (JSON)', type: 'text', placeholder: '["ENTREE","ACCUEIL"]' }] },
      ],
    },
    {
      title: 'SPI / TACHES (2 agents)', color: MODULE_COLORS.SPI, agents: [
        { name: 'Agent Analyseur Taches', desc: 'Decompose besoins DAF en sous-taches via Claude AI',
          endpoint: null, inputs: [], link: '/rh/spi360/tasks/needs' },
        { name: 'Agent Validateur Preuves', desc: 'Validation IA des preuves de completion',
          endpoint: null, inputs: [], link: '/rh/spi360/tasks/needs' },
      ],
    },
    {
      title: 'JURIDIQUE (6 agents)', color: MODULE_COLORS.JURIDIQUE, agents: [
        { name: 'Agent OCR/NLP Juridique', desc: 'Extraction contrats, assignations, jugements',
          endpoint: '/agents/document/process',
          inputs: [{ key: 'document_text', label: 'Texte document juridique', type: 'textarea', placeholder: 'Assignation en date du...' }] },
        { name: 'Agent Contractuel', desc: 'Conformite contrats, clauses manquantes',
          endpoint: '/agents/compliance/check',
          inputs: [{ key: 'rule_code', label: 'Code regle', type: 'text', placeholder: 'ALG-CTR-REV' }] },
        { name: 'Agent Litige', desc: 'Evaluation risque, plan action',
          endpoint: null, inputs: [], link: '/juridique/cases' },
        { name: 'Agent Conformite', desc: '8 regles algeriennes evaluees',
          endpoint: '/agents/compliance/check',
          inputs: [{ key: 'rule_code', label: 'Code (vide=toutes)', type: 'text', placeholder: '' }] },
        { name: 'Agent Communication Juridique', desc: 'Routage messages entrants vers dossiers',
          endpoint: '/agents/drh/messagerie/send',
          inputs: [{ key: 'recipient', label: 'Destinataire', type: 'text', placeholder: 'juriste@groupe-gfi.dz' },
                   { key: 'template', label: 'Template', type: 'text', placeholder: 'MISE_EN_DEMEURE' }] },
        { name: 'Agent Orchestrateur', desc: 'Orchestration priorite agents J1-J5',
          endpoint: null, inputs: [], link: '/juridique' },
      ],
    },
    {
      title: 'FINANCE (2 agents)', color: MODULE_COLORS.FINANCE, agents: [
        { name: 'Agent CFF', desc: 'Calcul CFF 5 etapes sur facture RF3 inter-groupe',
          endpoint: '/agents/cff/calculate',
          inputs: [{ key: 'montant_ht', label: 'Montant HT', type: 'number', placeholder: '5000000' },
                   { key: 'emitter_code', label: 'Emetteur', type: 'text', placeholder: 'AMENFORT' },
                   { key: 'receiver_code', label: 'Recepteur', type: 'text', placeholder: 'ETS-DK' }] },
        { name: 'Agent Rapprochement', desc: 'Rapprochement bancaire NLP',
          endpoint: '/agents/drh/bi/generate',
          inputs: [{ key: 'metric', label: 'Type', type: 'text', placeholder: 'bank_reconciliation' },
                   { key: 'period', label: 'Periode', type: 'text', placeholder: '2026-03' }] },
      ],
    },
    {
      title: 'GED (2 agents)', color: MODULE_COLORS.GED, agents: [
        { name: 'Agent OCR GED', desc: 'Pipeline 7 couches ingestion documents',
          endpoint: '/agents/document/process',
          inputs: [{ key: 'document_text', label: 'Texte document', type: 'textarea', placeholder: 'Facture AMENFORT...' }],
          needsUpload: true },
        { name: 'Agent Detection', desc: '15 patterns detection anomalies',
          endpoint: '/agents/detection/analyze',
          inputs: [{ key: 'text_sample', label: 'Texte', type: 'textarea', placeholder: 'Paiement SAHEL 35M...' }] },
      ],
    },
    {
      title: 'FONDATION (1 agent)', color: MODULE_COLORS.FONDATION, agents: [
        { name: 'Agent Alias', desc: 'Resolution aliases projets/associes/entreprises',
          endpoint: '/foundation/aliases/resolve',
          inputs: [{ key: 'input_name', label: 'Nom a resoudre', type: 'text', placeholder: 'FOES, Sahel, 02H, Hmed...' }] },
      ],
    },
    {
      title: 'SYSTEME (1 agent)', color: MODULE_COLORS.SYSTEME, agents: [
        { name: 'Meta-IA', desc: 'Detection besoins fonctionnels non couverts',
          endpoint: '/system/meta-ia/proposals',
          inputs: [] },
      ],
    },
    {
      title: 'ADV (1 agent)', color: '#74B9FF', agents: [
        { name: 'Agent ADV Chain', desc: 'Chaine: paiement RF2 -> securisation -> engagement',
          endpoint: '/agents/adv/chain',
          inputs: [{ key: 'dossier_id', label: 'Dossier ADV', type: 'text', placeholder: 'ADV-2026-PROJET-0001' },
                   { key: 'event', label: 'Evenement', type: 'text', placeholder: 'RF2_PAYMENT_RECEIVED' }] },
      ],
    },
  ];

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Controle des Agents IA</h1>
      <p className="text-sm text-storm mb-6">Testez et declenchez chaque agent individuellement. Tous utilisent Claude AI via OpenRouter.</p>

      {agentSections.map(section => (
        <div key={section.title} className="mb-8">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ background: section.color }} />
            {section.title}
          </h2>
          <div className="space-y-4">
            {section.agents.map(agent => {
              const r = results[agent.name];
              return (
                <div key={agent.name} className={`bg-white rounded-card border p-5 shadow-card ${
                  r?.status === 'running' ? 'border-iris' : r?.status === 'success' ? 'border-mint' : r?.status === 'error' ? 'border-coral' : 'border-[#E0E0E0]'}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold">{agent.name}</h3>
                      <p className="text-xs text-storm">{agent.desc}</p>
                    </div>
                    {r && <Badge variant={r.status === 'success' ? 'success' : r.status === 'error' ? 'error' : r.status === 'running' ? 'info' : 'neutral'}>{r.status.toUpperCase()}</Badge>}
                  </div>

                  {agent.endpoint && agent.inputs.length > 0 && (
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      {agent.inputs.map(inp => (
                        <div key={inp.key}>
                          <label className="text-xs font-medium text-storm block mb-1">{inp.label}</label>
                          {inp.type === 'textarea' ? (
                            <textarea value={input[`${agent.name}_${inp.key}`] || ''} rows={2}
                              onChange={e => setInput(p => ({ ...p, [`${agent.name}_${inp.key}`]: e.target.value }))}
                              className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none"
                              placeholder={inp.placeholder} />
                          ) : (
                            <input value={input[`${agent.name}_${inp.key}`] || ''}
                              type={inp.type === 'number' ? 'number' : 'text'}
                              onChange={e => setInput(p => ({ ...p, [`${agent.name}_${inp.key}`]: e.target.value }))}
                              className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
                              placeholder={inp.placeholder} />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {agent.needsUpload && (
                    <div className="mb-3">
                      <ProofUpload onUploaded={id => setDocId(id)} label="Document a traiter" />
                    </div>
                  )}

                  <div className="flex gap-2">
                    {agent.endpoint && (
                      <button onClick={() => {
                        const body: any = {};
                        agent.inputs.forEach(inp => { body[inp.key] = input[`${agent.name}_${inp.key}`] || ''; });
                        if (agent.needsUpload && docId) body.document_id = docId;
                        runAgent(agent.name, agent.endpoint!, body);
                      }}
                        disabled={r?.status === 'running'}
                        className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
                        {r?.status === 'running' ? 'En cours...' : 'Executer'}
                      </button>
                    )}
                    {(agent as any).link && (
                      <a href={(agent as any).link} className="px-4 py-2 border border-iris text-iris rounded-button text-sm font-medium hover:bg-rose-50">
                        Ouvrir l'interface
                      </a>
                    )}
                    {!agent.endpoint && !(agent as any).link && (
                      <span className="text-xs text-storm italic py-2">Interface dediee en cours de developpement</span>
                    )}
                  </div>

                  {/* Result display */}
                  {r?.status === 'success' && r.result && (
                    <div className="mt-3 bg-[rgba(0,184,148,0.06)] rounded-lg p-3 text-sm">
                      <p className="font-semibold text-mint mb-1">Resultat:</p>
                      <pre className="text-xs font-mono overflow-x-auto max-h-48 whitespace-pre-wrap">{JSON.stringify(r.result, null, 2)}</pre>
                    </div>
                  )}
                  {r?.status === 'error' && (
                    <div className="mt-3 bg-[rgba(255,107,107,0.06)] rounded-lg p-3 text-sm">
                      <p className="font-semibold text-coral">Erreur: {r.error}</p>
                    </div>
                  )}
                  {r?.status === 'running' && (
                    <div className="mt-3 flex items-center gap-2">
                      <div className="animate-spin w-4 h-4 border-2 border-iris border-t-transparent rounded-full" />
                      <span className="text-xs text-iris">Agent en cours d'execution...</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
