import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { validateNIN, validateRIB, validateAge, validateSalary } from '../../lib/business-rules';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

function AgentMaterielPreview({ position }: { position: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    if (position) api.post('/agents/drh/materiel/onboarding', { position }).then(r => setData(r.data.data)).catch(() => {});
  }, [position]);
  if (!data) return null;
  return (
    <div className="bg-white rounded-card border border-mint p-6 shadow-card">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-white bg-mint px-2 py-0.5 rounded">AGENT MATERIEL</span>
        <h2 className="font-semibold">Equipement a attribuer</h2>
      </div>
      <p className="text-xs text-storm mb-3">Auto-genere pour le poste: {data.position}</p>
      <div className="flex flex-wrap gap-2">
        {data.equipment?.map((e: any) => (
          <span key={e.item} className="bg-[rgba(0,184,148,0.08)] text-mint text-xs font-medium px-3 py-1.5 rounded-lg border border-mint/20">{e.item}</span>
        ))}
      </div>
    </div>
  );
}

function AgentAccesPreview({ position }: { position: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    if (position) api.post('/agents/drh/acces/configure', { employee: {}, position }).then(r => setData(r.data.data)).catch(() => {});
  }, [position]);
  if (!data) return null;
  return (
    <div className="bg-white rounded-card border border-ocean p-6 shadow-card">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-white bg-ocean px-2 py-0.5 rounded">AGENT ACCES</span>
        <h2 className="font-semibold">Zones badge RFID</h2>
      </div>
      <p className="text-xs text-storm mb-3">Zones auto-configurees pour: {position}</p>
      <div className="flex flex-wrap gap-2">
        {data.badge_zones?.map((z: string) => (
          <span key={z} className="bg-[rgba(9,132,227,0.08)] text-ocean text-xs font-medium px-3 py-1.5 rounded-lg border border-ocean/20">{z}</span>
        ))}
      </div>
    </div>
  );
}

const WILAYAS = ['01-Adrar','02-Chlef','03-Laghouat','04-OEB','05-Batna','06-Béjaïa','07-Biskra','08-Béchar','09-Blida','10-Bouira','11-Tamanrasset','12-Tébessa','13-Tlemcen','14-Tiaret','15-Tizi Ouzou','16-Alger','17-Djelfa','18-Jijel','19-Sétif','20-Saïda','21-Skikda','22-SBA','23-Annaba','24-Guelma','25-Constantine','26-Médéa','27-Mostaganem','28-M\'Sila','29-Mascara','30-Ouargla','31-Oran','32-El Bayadh','33-Illizi','34-BBA','35-Boumerdès','36-El Tarf','37-Tindouf','38-Tissemsilt','39-El Oued','40-Khenchela','41-Souk Ahras','42-Tipaza','43-Mila','44-Aïn Defla','45-Naâma','46-Aïn Témouchent','47-Ghardaïa','48-Relizane','49-El M\'Ghair','50-El Meniaa','51-Ouled Djellal','52-Bordj Badji Mokhtar','53-Béni Abbès','54-Timimoun','55-Touggourt','56-Djanet','57-In Salah','58-In Guezzam'];

export function EmployeeCreate() {
  const nav = useNavigate();
  const [entities, setEntities] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ gender: 'M', nationality: 'Algérienne', marital_status: 'celibataire', children: 0 });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get('/foundation/entities').then(r => setEntities(r.data.data || [])).catch(() => {});
  }, []);

  const set = (k: string, v: any) => {
    setForm((p: any) => ({ ...p, [k]: v }));
    const errs = { ...errors };
    delete errs[k];
    if (k === 'nin' && v && !validateNIN(v)) errs.nin = 'NIN doit contenir 18 chiffres';
    if (k === 'rib' && v && !validateRIB(v)) errs.rib = 'RIB doit contenir 20 chiffres';
    if (k === 'birth_date' && v) { const r = validateAge(v); if (!r.valid) errs.birth_date = r.errors[0]; }
    if (k === 'salary_base' && v) { const r = validateSalary(parseFloat(v)); if (!r.valid) errs.salary_base = r.errors[0]; }
    setErrors(errs);
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      const res = await api.post('/drh/employees', form);
      nav(`/drh/employees/${res.data.data?.id || ''}`);
    } catch (e: any) {
      setErrors({ _server: e.response?.data?.detail || 'Erreur serveur' });
    } finally { setSubmitting(false); }
  };

  const field = (label: string, key: string, type = 'text', required = true, extra?: any) => (
    <div>
      <label className="text-sm font-medium text-storm block mb-1.5">{label} {required && <span className="text-coral">*</span>}</label>
      {type === 'select' ? (
        <select value={form[key] || ''} onChange={e => set(key, e.target.value)} className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none">
          <option value="">Sélectionnez</option>
          {(extra?.options || []).map((o: any) => <option key={typeof o === 'string' ? o : o.value} value={typeof o === 'string' ? o : o.value}>{typeof o === 'string' ? o : o.label}</option>)}
        </select>
      ) : (
        <input type={type} value={form[key] || ''} onChange={e => set(key, e.target.value)}
          className={`w-full border rounded-input px-4 py-2.5 text-sm focus:ring-2 outline-none ${errors[key] ? 'border-coral focus:ring-coral/20' : 'border-mist focus:border-iris focus:ring-lavender'}`}
          placeholder={extra?.placeholder} />
      )}
      {errors[key] && <p className="text-xs text-coral mt-1">{errors[key]}</p>}
    </div>
  );

  return (
    <div className="max-w-3xl">
      <Link to="/rh/employees" className="text-sm text-iris hover:underline">← Employés</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Nouvel Employé</h1>
      {errors._server && <div className="bg-[rgba(255,107,107,0.08)] border border-coral rounded-lg p-3 mb-4 text-sm text-coral">{errors._server}</div>}

      <div className="space-y-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-4">Identité</h2>
          <div className="grid grid-cols-2 gap-4">
            {field('Nom', 'last_name')}
            {field('Prénom', 'first_name')}
            {field('Nom (arabe)', 'last_name_ar', 'text', false)}
            {field('Prénom (arabe)', 'first_name_ar', 'text', false)}
            {field('Date de naissance', 'birth_date', 'date')}
            {field('Lieu de naissance', 'birth_place')}
            {field('Genre', 'gender', 'select', true, { options: [{ value: 'M', label: 'Masculin' }, { value: 'F', label: 'Féminin' }] })}
            {field('Situation familiale', 'marital_status', 'select', true, { options: ['celibataire', 'marie', 'divorce', 'veuf'] })}
            {field('Nombre d\'enfants', 'children', 'number', false)}
            {field('NIN (18 chiffres)', 'nin', 'text', true, { placeholder: '000000000000000000' })}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-4">Contact</h2>
          <div className="grid grid-cols-2 gap-4">
            {field('Adresse', 'address')}
            {field('Wilaya', 'wilaya', 'select', true, { options: WILAYAS })}
            {field('Téléphone personnel', 'phone_personal', 'tel', true, { placeholder: '+213...' })}
            {field('Email personnel', 'email_personal', 'email', false)}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-4">Professionnel</h2>
          <div className="grid grid-cols-2 gap-4">
            {field('Entité', 'entity_id', 'select', true, { options: entities.map(e => ({ value: e.code, label: e.name })) })}
            {field('Département', 'department')}
            {field('Poste', 'position')}
            {field('Date d\'embauche', 'hire_date', 'date')}
            {field('Salaire de base (DA)', 'salary_base', 'number', true, { placeholder: '≥ 20 000 DA' })}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-4">Bancaire</h2>
          <div className="grid grid-cols-2 gap-4">
            {field('Banque', 'bank_name')}
            {field('RIB (20 chiffres)', 'rib', 'text', true, { placeholder: '00000000000000000000' })}
          </div>
        </div>

        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="font-semibold mb-4">Photo (obligatoire pour badge)</h2>
          <ProofUpload onUploaded={(id) => set('photo_id', id)} label="Photo d'identite" />
        </div>

        {/* Agent Materiel: auto-show equipment based on position */}
        {form.position && (
          <AgentMaterielPreview position={form.position} />
        )}

        {/* Agent Acces: auto-show badge zones based on position */}
        {form.position && (
          <AgentAccesPreview position={form.position} />
        )}

        <button onClick={submit}
          disabled={submitting || Object.keys(errors).filter(k => k !== '_server').length > 0 || !form.last_name || !form.first_name || !form.entity_id}
          className="w-full py-3 rounded-button bg-iris text-white font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver transition">
          {submitting ? 'Création en cours...' : 'Créer l\'employé et démarrer l\'onboarding'}
        </button>
      </div>
    </div>
  );
}
