import { useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

function buildStructuredText(listing: any): string {
  const lines: string[] = [];
  if (listing.title) lines.push(listing.title, '');
  if (listing.contract_type) lines.push(`${listing.contract_type} — ${listing.location || ''}`);
  lines.push('');
  if (listing.company_intro) { lines.push('A PROPOS DU GROUPE', listing.company_intro, ''); }
  if (listing.mission_intro) { lines.push('LE POSTE', listing.mission_intro, ''); }
  if (listing.responsibilities?.length) {
    lines.push('VOS MISSIONS');
    listing.responsibilities.forEach((r: string) => lines.push(`- ${r}`));
    lines.push('');
  }
  if (listing.requirements?.length) {
    lines.push('PROFIL RECHERCHE');
    listing.requirements.forEach((r: string) => lines.push(`- ${r}`));
    lines.push('');
  }
  if (listing.nice_to_have?.length) {
    lines.push('ATOUTS APPRECIES');
    listing.nice_to_have.forEach((r: string) => lines.push(`+ ${r}`));
    lines.push('');
  }
  if (listing.benefits?.length) {
    lines.push('CE QUE NOUS OFFRONS');
    listing.benefits.forEach((r: string) => lines.push(`* ${r}`));
    lines.push('');
  }
  if (listing.how_to_apply) { lines.push('COMMENT POSTULER', listing.how_to_apply, ''); }
  if (listing.hashtags?.length) { lines.push(listing.hashtags.join(' ')); }
  return lines.join('\n');
}

export function JobListingGenerator() {
  const [jobPosition, setJobPosition] = useState('');
  const [description, setDescription] = useState('');
  const [contractType, setContractType] = useState('CDI');
  const [location, setLocation] = useState('Bab Ezzouar, Alger');
  const [listing, setListing] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    if (!jobPosition.trim()) return;
    setGenerating(true);
    setListing(null);
    try {
      const r = await api.post('/agents/drh/recrutement/generate-listing', {
        job_position: jobPosition, description, contract_type: contractType, location,
      });
      setListing(r.data.data);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setGenerating(false); }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Generateur d'Annonces</h1>
      <p className="text-sm text-storm mb-6">Entrez le poste et une breve description — l'IA genere une annonce LinkedIn prete a publier.</p>

      {/* Input form */}
      <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-xs font-medium text-storm block mb-1">Intitule du poste <span className="text-coral">*</span></label>
            <input value={jobPosition} onChange={e => setJobPosition(e.target.value)}
              className="w-full border border-mist rounded-input px-4 py-2.5 text-sm focus:border-iris outline-none"
              placeholder="Ex: Chef de chantier, Agent commercial, Ingenieur BIM..." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Type de contrat</label>
              <select value={contractType} onChange={e => setContractType(e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none">
                <option>CDI</option><option>CDD</option><option>Stage</option><option>Chantier</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-storm block mb-1">Lieu</label>
              <input value={location} onChange={e => setLocation(e.target.value)}
                className="w-full border border-mist rounded-input px-3 py-2.5 text-sm focus:border-iris outline-none" />
            </div>
          </div>
        </div>
        <div className="mb-4">
          <label className="text-xs font-medium text-storm block mb-1">Description du besoin (optionnel)</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3}
            className="w-full border border-mist rounded-input px-4 py-3 text-sm focus:border-iris outline-none resize-none"
            placeholder="Ex: Nous cherchons un profil senior pour superviser le chantier principal (198 logements). Il devra gerer une equipe de 20 ouvriers et coordonner avec le BET..." />
        </div>
        <button onClick={generate} disabled={!jobPosition.trim() || generating}
          className="w-full py-3 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
          {generating ? 'Generation de l\'annonce en cours...' : 'Generer l\'annonce LinkedIn'}
        </button>
      </div>

      {/* Generated listing */}
      {listing && (
        <div className="space-y-6">
          {/* LinkedIn post — THE main output */}
          <div className="bg-white rounded-card border-2 border-[#0A66C2] p-6 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-[#0A66C2] text-white flex items-center justify-center text-sm font-bold">in</div>
                <div>
                  <h2 className="font-bold">Post LinkedIn — pret a publier</h2>
                  <p className="text-xs text-storm">Copiez ce texte et collez-le directement dans un nouveau post LinkedIn</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => copyToClipboard(buildStructuredText(listing))}
                  className={`px-5 py-2.5 rounded-button text-sm font-semibold transition ${
                    copied ? 'bg-mint text-white' : 'bg-[#0A66C2] text-white hover:bg-[#084d8a]'}`}>
                  {copied ? '✓ Copie dans le presse-papier !' : 'Copier le texte'}
                </button>
                <button onClick={() => {
                  const blob = new Blob([buildStructuredText(listing)], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = `annonce_${jobPosition.replace(/\s/g, '_')}.txt`;
                  a.click(); URL.revokeObjectURL(url);
                }} className="px-4 py-2.5 border border-mist rounded-button text-sm text-storm hover:bg-gray-50">
                  Telecharger .txt
                </button>
              </div>
            </div>
            <div className="bg-[#F3F2EF] rounded-xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-iris text-white flex items-center justify-center font-bold">GD</div>
                <div>
                  <p className="font-semibold text-sm">Groupe GFI</p>
                  <p className="text-xs text-storm">Promotion immobiliere et construction industrielle</p>
                </div>
              </div>
              <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed text-charcoal">{buildStructuredText(listing)}</pre>
            </div>
          </div>

          {/* Detailed breakdown — for HR reference */}
          <details className="bg-white rounded-card border border-[#E0E0E0] shadow-card">
            <summary className="p-6 cursor-pointer font-semibold flex items-center justify-between">
              <span>Voir le detail structure de l'annonce</span>
              <span className="text-xs text-storm font-normal">Cliquez pour deployer</span>
            </summary>
            <div className="px-6 pb-6">
              <h2 className="text-xl font-bold mb-1">{listing.title}</h2>
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="info">{listing.contract_type || contractType}</Badge>
                <span className="text-sm text-storm">{listing.location || location}</span>
              </div>

              {listing.company_intro && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-iris mb-1">A propos du groupe</h3>
                  <p className="text-sm text-charcoal">{listing.company_intro}</p>
                </div>
              )}

              {listing.mission_intro && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-iris mb-1">Le poste</h3>
                  <p className="text-sm text-charcoal">{listing.mission_intro}</p>
                </div>
              )}

              {listing.responsibilities?.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-iris mb-2">Vos missions</h3>
                  <ul className="space-y-1.5">
                    {listing.responsibilities.map((r: string, i: number) => (
                      <li key={i} className="flex gap-2 text-sm"><span className="text-iris">&#8226;</span>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {listing.requirements?.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-iris mb-2">Profil recherche</h3>
                  <ul className="space-y-1.5">
                    {listing.requirements.map((r: string, i: number) => (
                      <li key={i} className="flex gap-2 text-sm"><span className="text-mint">&#10003;</span>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {listing.nice_to_have?.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-storm mb-2">Atouts apprecies</h3>
                  <ul className="space-y-1">
                    {listing.nice_to_have.map((r: string, i: number) => (
                      <li key={i} className="flex gap-2 text-sm text-storm"><span>+</span>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {listing.benefits?.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-mint mb-2">Ce que nous offrons</h3>
                  <ul className="space-y-1.5">
                    {listing.benefits.map((r: string, i: number) => (
                      <li key={i} className="flex gap-2 text-sm"><span className="text-mint">&#9733;</span>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {listing.how_to_apply && (
                <div className="bg-[rgba(108,92,231,0.05)] rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-iris mb-1">Comment postuler</h3>
                  <p className="text-sm">{listing.how_to_apply}</p>
                </div>
              )}

              {listing.hashtags?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {listing.hashtags.map((h: string, i: number) => (
                    <span key={i} className="text-xs text-iris font-medium">{h}</span>
                  ))}
                </div>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
