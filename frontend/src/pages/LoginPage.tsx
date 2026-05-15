import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth, EntrepriseInfo } from "../context/AuthContext";

/* ── Status badge colors ── */
function statutColor(statut?: string): string {
  if (!statut) return "bg-slate-100 text-slate-600";
  if (statut === "ACTIF") return "bg-emerald-50 text-emerald-700";
  if (statut.includes("FERMER")) return "bg-amber-50 text-amber-700";
  if (statut.includes("DÉVELOPPER")) return "bg-blue-50 text-blue-700";
  if (statut === "DISSOUTE") return "bg-red-50 text-red-700";
  if (statut === "SATELLITE") return "bg-purple-50 text-purple-700";
  return "bg-slate-100 text-slate-600";
}

export default function LoginPage() {
  const { login, selectEntreprise, isAuthenticated, activeEntreprise, entreprises } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<"credentials" | "entreprise">("credentials");
  const [availableEntreprises, setAvailableEntreprises] = useState<EntrepriseInfo[]>([]);

  // If already authenticated AND has an active entreprise → go to dashboard
  if (isAuthenticated && activeEntreprise) {
    return <Navigate to="/dashboard" replace />;
  }

  // If authenticated but needs to pick entreprise → show step 2
  const showEntreprisePicker = isAuthenticated && !activeEntreprise && entreprises.length > 1;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result.needsSelection) {
        setStep("entreprise");
      }
      // If only 1 entreprise, login auto-selects and isAuthenticated+activeEntreprise triggers redirect
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Identifiants invalides");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectEntreprise = async (ent: EntrepriseInfo) => {
    setError("");
    setLoading(true);
    try {
      await selectEntreprise(ent.id);
      // activeEntreprise will be set, triggering redirect
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Erreur de sélection");
    } finally {
      setLoading(false);
    }
  };

  const currentStep = showEntreprisePicker ? "entreprise" : step;
  const entsToShow = showEntreprisePicker ? entreprises : availableEntreprises;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="w-full max-w-md">
        <div className="card p-8">
          {/* Logo */}
          <div className="mb-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600 text-xl font-bold text-white shadow-lg">
              GD
            </div>
            <h1 className="mt-4 text-2xl font-bold text-slate-900">
              Groupe Dendani
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              GFI v7.0 — Plateforme Financi&egrave;re & Op&eacute;rationnelle
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
              {error}
            </div>
          )}

          {currentStep === "credentials" ? (
            /* ── Step 1: Email + Password ── */
            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Adresse e-mail
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field"
                  placeholder="utilisateur@gfi.dz"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Mot de passe
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;"
                />
              </div>

              <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Connexion&hellip;
                  </span>
                ) : (
                  "Se connecter"
                )}
              </button>
            </form>
          ) : (
            /* ── Step 2: Pick Entreprise ── */
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-1">
                Choisissez votre entit&eacute;
              </h2>
              <p className="text-sm text-slate-500 mb-4">
                Vous avez acc&egrave;s &agrave; {entsToShow.length} entit&eacute;(s) juridique(s)
              </p>

              <div className="space-y-2 max-h-96 overflow-y-auto">
                {entsToShow.map((ent) => (
                  <button
                    key={ent.id}
                    onClick={() => handleSelectEntreprise(ent)}
                    disabled={loading}
                    className="w-full flex items-center gap-3 rounded-xl border-2 border-slate-200 bg-white p-4 text-left transition-all hover:border-teal-500 hover:shadow-md disabled:opacity-50"
                  >
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-600 text-xs font-bold text-white shrink-0 leading-tight">
                      {ent.code?.replace("SARL-", "").replace("EURL-", "").substring(0, 3) || "?"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-900 text-sm truncate">
                        {ent.raison_sociale}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-slate-400 font-mono">{ent.code}</span>
                        {ent.forme_juridique && (
                          <span className="text-xs text-slate-400">{ent.forme_juridique}</span>
                        )}
                        {ent.statut && (
                          <span className={`text-xs px-1.5 py-0.5 rounded ${statutColor(ent.statut)}`}>
                            {ent.statut}
                          </span>
                        )}
                      </div>
                    </div>
                    <svg className="h-5 w-5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </button>
                ))}
              </div>

              {loading && (
                <div className="flex justify-center mt-4">
                  <div className="h-6 w-6 animate-spin rounded-full border-3 border-teal-600 border-t-transparent" />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
