import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

function GfiLogo({ small = false }: { small?: boolean }) {
  const size = small ? 40 : 48;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="gfiGradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ef4444" />
          <stop offset="1" stopColor="#7f1d1d" />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="52" height="52" rx="16" fill="#0B1220" stroke="url(#gfiGradient)" strokeWidth="2" />
      <path d="M19 35C19 27 24.5 21 33 21C39 21 43 23.8 45 28" stroke="url(#gfiGradient)" strokeWidth="4" strokeLinecap="round" />
      <path d="M18 40H34" stroke="#fca5a5" strokeWidth="4" strokeLinecap="round" />
      <circle cx="45" cy="36" r="4" fill="#ef4444" />
    </svg>
  );
}

export function LoginPage() {
  const nav = useNavigate();
  const { login } = useStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/auth/login', { username: email, password });
      const d = res.data.data;
      login(d.access_token, {
        user_id: d.user_id,
        email: d.email,
        name: d.name,
        role: d.role,
        modules: d.modules,
        has_rf2: d.has_rf2,
      });
      nav('/');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else setError('Email ou mot de passe incorrect');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#030712] text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl">
        <aside className="relative hidden w-[44%] overflow-hidden border-r border-slate-800 bg-[#020617] p-8 lg:block">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(220,38,38,0.2),transparent_45%)]" />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(120deg,transparent_0%,rgba(153,27,27,0.12)_40%,transparent_80%)] animate-[sheen_7s_linear_infinite]" />
          <div className="pointer-events-none absolute -left-24 top-20 h-64 w-64 rounded-full bg-rose-400/10 blur-3xl" />
          <div className="pointer-events-none absolute bottom-6 right-0 h-56 w-56 rounded-full bg-red-500/10 blur-3xl" />
          <div className="relative z-10">
            <div className="mb-8 flex items-center gap-3">
              <div className="h-12 w-12 rounded-2xl bg-rose-500/15 ring-1 ring-rose-300/35 flex items-center justify-center shadow-[0_0_30px_rgba(220,38,38,0.2)]">
                <GfiLogo />
              </div>
              <div>
                <p className="font-display text-xl font-bold tracking-[0.08em] text-white">Avelis</p>
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rose-200/90">Plateforme de gestion integree</p>
              </div>
            </div>

            <div className="mt-1">
              <p className="font-display text-2xl font-semibold text-white">Votre espace de pilotage</p>
              <p className="font-display mt-1.5 text-3xl font-bold leading-tight text-white">
                clair et rapide
              </p>
              <div className="mt-3 h-1 w-32 overflow-hidden rounded-full bg-slate-700/80">
                <div className="h-full w-14 rounded-full bg-gradient-to-r from-rose-300 to-red-400 animate-[pulse_2.4s_ease-in-out_infinite]" />
              </div>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-6 text-slate-200">
              Suivez vos operations Finance, ADV, RH, Juridique et Operations avec une interface fluide.
            </p>

            <div className="login-illustration mt-7">
              <div className="login-illustration__orb login-illustration__orb--one" />
              <div className="login-illustration__orb login-illustration__orb--two" />
              <svg viewBox="0 0 520 220" className="h-[220px] w-full" fill="none" aria-hidden="true">
                <rect x="20" y="36" width="150" height="128" rx="16" className="login-card-surface" />
                <rect x="34" y="58" width="78" height="8" rx="4" className="fill-rose-300/70" />
                <rect x="34" y="78" width="122" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="34" y="98" width="106" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="34" y="122" width="64" height="22" rx="11" className="fill-red-300/85" />

                <rect x="194" y="16" width="150" height="128" rx="16" className="login-card-surface login-card-float" />
                <rect x="208" y="38" width="96" height="8" rx="4" className="fill-rose-300/70" />
                <circle cx="224" cy="76" r="17" className="fill-red-300/25" />
                <circle cx="224" cy="76" r="8" className="fill-red-200/80" />
                <rect x="248" y="68" width="78" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="248" y="86" width="62" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="208" y="112" width="90" height="20" rx="10" className="fill-red-300/75" />

                <rect x="362" y="56" width="138" height="116" rx="16" className="login-card-surface" />
                <rect x="376" y="78" width="70" height="8" rx="4" className="fill-rose-300/70" />
                <rect x="376" y="98" width="96" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="376" y="118" width="82" height="8" rx="4" className="fill-slate-500/70" />
                <rect x="376" y="140" width="54" height="18" rx="9" className="fill-red-300/80" />

                <path d="M170 100C194 100 182 80 204 80" className="login-path login-path--a" />
                <path d="M344 82C370 82 348 114 362 114" className="login-path login-path--b" />
                <circle cx="204" cy="80" r="4" className="fill-rose-300 login-node node-a" />
                <circle cx="362" cy="114" r="4" className="fill-red-300 login-node node-b" />
              </svg>
            </div>

            <div className="mt-10 space-y-3">
              {['Analyse en temps reel', 'Alertes prioritaires', 'Navigation multi-modules'].map((item, index) => (
                <div
                  key={item}
                  className="flex items-center gap-3 rounded-xl border border-slate-600/70 bg-slate-900/70 px-3 py-2.5 text-sm text-slate-100 backdrop-blur-sm"
                  style={{ animation: `slideFadeIn 520ms ease ${index * 120}ms both` }}
                >
                  <span className="h-2 w-2 rounded-full bg-rose-300 shadow-[0_0_12px_rgba(220,38,38,0.8)]" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </aside>

        <div className="flex flex-1 items-center justify-center px-4 py-10">
          <div className="-mt-16 w-full max-w-[420px]">
            <div className="text-center mb-8 lg:hidden">
              <div className="h-16 w-16 rounded-2xl bg-rose-700/80 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-rose-700/25">
                <GfiLogo small />
              </div>
              <h1 className="font-display text-3xl font-bold tracking-[0.08em] text-white">Avelis</h1>
              <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.14em] text-rose-200/90">Plateforme de gestion integree</p>
            </div>

            {/* Login card */}
            <form onSubmit={handleLogin}
              className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-8 shadow-[0_24px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl">
              <p className="text-xs uppercase tracking-[0.22em] text-rose-200">Bienvenue</p>
              <h2 className="font-display mt-2 text-3xl font-semibold text-white">Connexion</h2>

              {error && (
                <div className="mt-4 rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">
                  {error}
                </div>
              )}

              <div className="mt-6 space-y-5">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-200">Email</label>
                  <input
                    type="email" value={email} onChange={e => setEmail(e.target.value)}
                    className="w-full rounded-xl border border-slate-600 bg-slate-950/85 px-3 py-2.5 text-sm text-white placeholder:text-slate-400 outline-none transition focus:border-rose-300 focus:ring-1 focus:ring-rose-300"
                    placeholder="email@exemple.dz" autoFocus
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-200">Mot de passe</label>
                  <input
                    type="password" value={password} onChange={e => setPassword(e.target.value)}
                    className="w-full rounded-xl border border-slate-600 bg-slate-950/85 px-3 py-2.5 text-sm text-white placeholder:text-slate-400 outline-none transition focus:border-rose-300 focus:ring-1 focus:ring-rose-300"
                    placeholder="Mot de passe"
                  />
                </div>
              </div>

              <button type="submit" disabled={!email || !password || loading}
                className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-red-800 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_10px_30px_rgba(127,29,29,0.35)] transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-rose-300 disabled:cursor-not-allowed disabled:opacity-50">
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Connexion...
                  </>
                ) : 'Se connecter'}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-slate-500">Avelis — Systeme de Gestion</p>
          </div>
        </div>
      </div>
    </div>
  );
}
