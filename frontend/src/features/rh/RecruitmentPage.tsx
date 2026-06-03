import { useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

type JobProfile = {
  job_title: string; required_skills: string[]; preferred_skills: string[];
  min_experience_years: number; education_required: string; languages: string[];
  key_responsibilities: string[]; evaluation_criteria: { criterion: string; weight: number; description: string }[];
  salary_range_da: { min: number; max: number }; contract_type_suggested: string;
};

type Candidate = {
  rank: number; candidate_name: string; score: number; recommendation: string;
  strong_points: string[]; weak_points: string[]; experience_years: number | null;
  education_level: string; skills_match: string[]; skills_missing: string[];
  salary_estimate_da: number | null; summary: string; interview_questions: string[];
  cv_preview: string; cv_index: number;
};

const REC_BG: Record<string, string> = { RETENU: '#00B894', RESERVE: '#E17055', REJETE: '#FF6B6B' };

export function RecruitmentPage() {
  // Step 1: Role
  const [jobPosition, setJobPosition] = useState('');
  const [profile, setProfile] = useState<JobProfile | null>(null);
  const [generatingProfile, setGeneratingProfile] = useState(false);

  // Step 2: CVs
  const [cvTexts, setCvTexts] = useState<{ text: string; filename: string }[]>([]);
  const [pasteInput, setPasteInput] = useState('');

  // Step 3: Results
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [batchMeta, setBatchMeta] = useState<any>(null);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState('');

  // Step 1: Generate profile when role is entered
  const generateProfile = async () => {
    if (!jobPosition.trim()) return;
    setGeneratingProfile(true);
    try {
      const r = await api.post('/agents/drh/recrutement/generate-profile', { job_position: jobPosition });
      setProfile(r.data.data);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setGeneratingProfile(false); }
  };

  // Step 2: Handle file uploads (single or multiple)
  const handleFiles = (files: FileList) => {
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string || '';
        setCvTexts(prev => [...prev, { text, filename: file.name }]);
      };
      reader.readAsText(file);
    });
  };

  const addPastedCv = () => {
    if (pasteInput.trim()) {
      setCvTexts(prev => [...prev, { text: pasteInput.trim(), filename: `CV colle #${prev.length + 1}` }]);
      setPasteInput('');
    }
  };

  // Step 3: Analyze all CVs together
  const analyzeAll = async () => {
    if (cvTexts.length === 0 || !jobPosition) return;
    setAnalyzing(true);
    setProgress(`Analyse de ${cvTexts.length} CV(s) par l'IA pour le poste "${jobPosition}"...`);
    try {
      const requirements = profile?.required_skills?.join(', ') || '';
      const r = await api.post('/agents/drh/recrutement/batch', {
        cvs: cvTexts.map(c => ({ text: c.text })),
        job_position: jobPosition,
        job_requirements: requirements,
      });
      const data = r.data.data;
      // Attach filenames
      (data.candidates || []).forEach((c: any) => {
        if (cvTexts[c.cv_index]) c.filename = cvTexts[c.cv_index].filename;
      });
      setCandidates(data.candidates || []);
      setBatchMeta(data);
      setSelected(data.candidates?.[0] || null);
    } catch (e: any) { alert(e.response?.data?.detail || 'Erreur'); }
    finally { setAnalyzing(false); setProgress(''); }
  };

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Recrutement IA</h1>
      <p className="text-sm text-storm mb-6">Specifiez le poste, uploadez les CVs — l'IA genere le profil requis, analyse chaque candidat et les classe du meilleur au moins bon.</p>

      {/* ═══ STEP 1: Role ═══ */}
      <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-6">
        <h2 className="font-semibold mb-3">1. Quel poste recrutez-vous ?</h2>
        <div className="flex gap-3">
          <input value={jobPosition} onChange={e => setJobPosition(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && generateProfile()}
            className="flex-1 border border-mist rounded-input px-4 py-3 text-sm focus:border-iris outline-none"
            placeholder="Ex: Chef de chantier, Agent commercial, Comptable, Gestionnaire ADV..." />
          <button onClick={generateProfile} disabled={!jobPosition.trim() || generatingProfile}
            className="px-6 py-3 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver whitespace-nowrap">
            {generatingProfile ? 'Generation IA...' : 'Generer le profil'}
          </button>
        </div>

        {/* AI-generated profile */}
        {profile && (
          <div className="mt-4 border-t border-mist pt-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-iris px-2 py-0.5 rounded">PROFIL IA</span>
              <h3 className="font-semibold">{profile.job_title}</h3>
              {profile.contract_type_suggested && <Badge variant="info">{profile.contract_type_suggested}</Badge>}
              {profile.salary_range_da && (
                <span className="text-xs text-storm ml-auto">
                  Salaire: {profile.salary_range_da.min?.toLocaleString()} - {profile.salary_range_da.max?.toLocaleString()} DA
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-storm mb-1.5">Competences requises</p>
                <div className="flex flex-wrap gap-1">
                  {profile.required_skills?.map((s, i) => (
                    <span key={i} className="bg-iris text-white text-xs px-2.5 py-1 rounded-lg">{s}</span>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-storm mb-1.5">Competences souhaitees</p>
                <div className="flex flex-wrap gap-1">
                  {profile.preferred_skills?.map((s, i) => (
                    <span key={i} className="bg-lavender text-iris text-xs px-2.5 py-1 rounded-lg">{s}</span>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 mt-3">
              <div className="bg-[#FAFAFA] rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-storm">Experience min.</p>
                <p className="font-bold">{profile.min_experience_years} ans</p>
              </div>
              <div className="bg-[#FAFAFA] rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-storm">Diplome requis</p>
                <p className="font-bold text-sm">{profile.education_required}</p>
              </div>
              <div className="bg-[#FAFAFA] rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-storm">Langues</p>
                <p className="font-bold text-sm">{profile.languages?.join(', ')}</p>
              </div>
            </div>

            {profile.evaluation_criteria && profile.evaluation_criteria.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-storm mb-1.5">Criteres d'evaluation</p>
                <div className="space-y-1">
                  {profile.evaluation_criteria.map((c, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-full bg-mist rounded-full h-2">
                        <div className="bg-iris h-full rounded-full" style={{ width: `${c.weight}%` }} />
                      </div>
                      <span className="text-xs text-storm whitespace-nowrap min-w-[120px]">{c.criterion} ({c.weight}%)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ═══ STEP 2: Upload CVs ═══ */}
      {profile && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-6">
          <h2 className="font-semibold mb-3">2. Uploadez les CVs des candidats pour "{profile.job_title}"</h2>
          <p className="text-xs text-storm mb-3">Tous les CVs seront evalues pour le meme poste. Uploadez-en autant que necessaire.</p>

          {/* Drop zone */}
          <div className="border-2 border-dashed border-mist rounded-lg p-6 mb-4 text-center hover:border-iris transition cursor-pointer"
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
            onClick={() => document.getElementById('cv-files')?.click()}>
            <input id="cv-files" type="file" accept=".txt,.pdf,.doc,.docx" multiple className="hidden"
              onChange={e => e.target.files && handleFiles(e.target.files)} />
            <p className="text-2xl mb-1">📄</p>
            <p className="text-sm font-medium">Glissez les CVs ici ou cliquez pour selectionner</p>
            <p className="text-xs text-storm">Plusieurs fichiers acceptes — TXT, PDF, DOCX</p>
          </div>

          {/* Or paste */}
          <div className="flex gap-2 mb-4">
            <textarea value={pasteInput} onChange={e => setPasteInput(e.target.value)} rows={2}
              className="flex-1 border border-mist rounded-input px-3 py-2 text-sm font-mono focus:border-iris outline-none resize-none"
              placeholder="Ou collez le texte d'un CV ici..." />
            <button onClick={addPastedCv} disabled={!pasteInput.trim()}
              className="px-4 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
              Ajouter
            </button>
          </div>

          {/* CV list */}
          {cvTexts.length > 0 && (
            <div className="mb-4">
              <p className="text-sm font-medium mb-2">{cvTexts.length} CV(s) prets pour analyse:</p>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {cvTexts.map((cv, i) => (
                  <div key={i} className="flex items-center justify-between bg-[#FAFAFA] rounded px-3 py-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-bold text-iris">#{i + 1}</span>
                      <span className="text-xs truncate">{cv.filename}</span>
                      <span className="text-[10px] text-storm">({cv.text.length} car.)</span>
                    </div>
                    <button onClick={() => setCvTexts(prev => prev.filter((_, j) => j !== i))} className="text-coral text-xs hover:underline ml-2">×</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button onClick={analyzeAll} disabled={cvTexts.length === 0 || analyzing}
            className="w-full py-3.5 bg-iris text-white rounded-button font-semibold text-sm hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
            {analyzing ? progress : `Analyser et classer ${cvTexts.length} candidat(s)`}
          </button>
        </div>
      )}

      {/* ═══ STEP 3: Results ═══ */}

      {/* Summary strip */}
      {batchMeta && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
            <p className="text-xs text-storm">Candidats analyses</p>
            <p className="text-2xl font-bold">{batchMeta.total_candidates}</p>
          </div>
          <div className="bg-white rounded-card border border-mint p-4 shadow-card text-center">
            <p className="text-xs text-storm">Retenus</p>
            <p className="text-2xl font-bold text-mint">{batchMeta.retained}</p>
          </div>
          <div className="bg-white rounded-card border border-[#E17055] p-4 shadow-card text-center">
            <p className="text-xs text-storm">En reserve</p>
            <p className="text-2xl font-bold text-[#E17055]">{batchMeta.reserved}</p>
          </div>
          <div className="bg-white rounded-card border border-coral p-4 shadow-card text-center">
            <p className="text-xs text-storm">Rejetes</p>
            <p className="text-2xl font-bold text-coral">{batchMeta.rejected}</p>
          </div>
        </div>
      )}

      {/* Ranked list + detail */}
      {candidates.length > 0 && (
        <div className="grid grid-cols-5 gap-6">
          {/* Left: Ranked list */}
          <div className="col-span-2 bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
            <h2 className="font-semibold mb-3">Classement — du meilleur au moins bon</h2>
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {candidates.map(c => (
                <div key={c.cv_index} onClick={() => setSelected(c)}
                  className={`p-3 rounded-lg border-2 cursor-pointer transition ${
                    selected?.cv_index === c.cv_index ? 'border-iris bg-[rgba(108,92,231,0.04)]' : 'border-mist hover:border-lavender'}`}>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-9 h-9 rounded-full text-white text-xs font-bold flex-shrink-0"
                      style={{ background: REC_BG[c.recommendation] || '#636E72' }}>
                      #{c.rank}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold truncate">{c.candidate_name || (c as any).filename || `Candidat #${c.cv_index + 1}`}</p>
                      <p className="text-[10px] text-storm">{c.education_level || '?'} — {c.experience_years != null ? `${c.experience_years} ans` : '?'}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <span className={`text-lg font-bold font-mono ${c.score >= 70 ? 'text-mint' : c.score >= 50 ? 'text-[#E17055]' : 'text-coral'}`}>{c.score}</span>
                      <p><Badge variant={c.recommendation === 'RETENU' ? 'success' : c.recommendation === 'RESERVE' ? 'warning' : 'error'}>{c.recommendation}</Badge></p>
                    </div>
                  </div>
                  <div className="mt-2 bg-mist rounded-full h-1.5">
                    <div className="h-full rounded-full" style={{ width: `${c.score}%`, background: REC_BG[c.recommendation] || '#636E72' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Detail */}
          <div className="col-span-3">
            {selected ? (
              <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
                {/* Header */}
                <div className="flex items-center gap-4 mb-5">
                  <div className="w-16 h-16 rounded-full flex items-center justify-center text-white text-2xl font-bold flex-shrink-0"
                    style={{ background: REC_BG[selected.recommendation] || '#636E72' }}>
                    {selected.score}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-bold truncate">{selected.candidate_name || `Candidat #${selected.cv_index + 1}`}</h2>
                    <p className="text-sm text-storm">
                      {selected.education_level} — {selected.experience_years != null ? `${selected.experience_years} ans d'experience` : 'Experience non precisee'}
                    </p>
                    <Badge variant={selected.recommendation === 'RETENU' ? 'success' : selected.recommendation === 'RESERVE' ? 'warning' : 'error'}>
                      {selected.recommendation}
                    </Badge>
                  </div>
                  {selected.salary_estimate_da && (
                    <div className="ml-auto text-right flex-shrink-0">
                      <p className="text-xs text-storm">Salaire estime</p>
                      <p className="font-bold font-mono">{selected.salary_estimate_da.toLocaleString()} DA</p>
                    </div>
                  )}
                </div>

                {/* Summary */}
                <div className="bg-[#FAFAFA] rounded-lg p-4 mb-5 text-sm">{selected.summary}</div>

                {/* Strong + Weak side by side */}
                <div className="grid grid-cols-2 gap-5 mb-5">
                  <div>
                    <h3 className="text-sm font-semibold text-mint mb-2 flex items-center gap-1">
                      <span className="w-5 h-5 rounded-full bg-mint text-white text-xs flex items-center justify-center">+</span>
                      Points forts ({selected.strong_points?.length || 0})
                    </h3>
                    <ul className="space-y-1.5">
                      {(selected.strong_points || []).map((p, i) => (
                        <li key={i} className="text-sm pl-3 border-l-2 border-mint">{p}</li>
                      ))}
                      {(!selected.strong_points || selected.strong_points.length === 0) && (
                        <li className="text-xs text-storm italic">Aucun point fort identifie</li>
                      )}
                    </ul>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-coral mb-2 flex items-center gap-1">
                      <span className="w-5 h-5 rounded-full bg-coral text-white text-xs flex items-center justify-center">-</span>
                      Points faibles ({selected.weak_points?.length || 0})
                    </h3>
                    <ul className="space-y-1.5">
                      {(selected.weak_points || []).map((p, i) => (
                        <li key={i} className="text-sm pl-3 border-l-2 border-coral">{p}</li>
                      ))}
                      {(!selected.weak_points || selected.weak_points.length === 0) && (
                        <li className="text-xs text-storm italic">Aucun point faible identifie</li>
                      )}
                    </ul>
                  </div>
                </div>

                {/* Skills */}
                <div className="grid grid-cols-2 gap-5 mb-5">
                  <div>
                    <p className="text-xs font-semibold text-storm mb-1.5">Competences correspondantes</p>
                    <div className="flex flex-wrap gap-1">
                      {(selected.skills_match || []).map((s, i) => (
                        <span key={i} className="bg-[rgba(0,184,148,0.12)] text-mint text-xs px-2 py-1 rounded">{s}</span>
                      ))}
                      {(!selected.skills_match || selected.skills_match.length === 0) && <span className="text-xs text-storm italic">Aucune</span>}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-storm mb-1.5">Competences manquantes</p>
                    <div className="flex flex-wrap gap-1">
                      {(selected.skills_missing || []).map((s, i) => (
                        <span key={i} className="bg-[rgba(255,107,107,0.12)] text-coral text-xs px-2 py-1 rounded">{s}</span>
                      ))}
                      {(!selected.skills_missing || selected.skills_missing.length === 0) && <span className="text-xs text-storm italic">Aucune</span>}
                    </div>
                  </div>
                </div>

                {/* Interview questions */}
                {selected.interview_questions && selected.interview_questions.length > 0 && (
                  <div className="border-t border-mist pt-4">
                    <h3 className="text-sm font-semibold mb-2">Questions suggerees pour l'entretien</h3>
                    <ol className="space-y-2">
                      {selected.interview_questions.map((q, i) => (
                        <li key={i} className="flex gap-2 text-sm bg-[rgba(108,92,231,0.04)] rounded-lg p-2.5">
                          <span className="text-iris font-bold flex-shrink-0">{i + 1}.</span>
                          <span>{q}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-card border border-mist p-12 shadow-card text-center">
                <p className="text-3xl mb-2">👆</p>
                <p className="text-storm">Cliquez sur un candidat pour voir son analyse detaillee</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
