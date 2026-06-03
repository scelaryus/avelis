import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../../store/useStore';
import { getActiveModuleByPath, getVisibleModules } from './navigationConfig';

function BrandMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="sidebarBrandGradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ef4444" />
          <stop offset="1" stopColor="#7f1d1d" />
        </linearGradient>
      </defs>
      <rect x="8" y="8" width="48" height="48" rx="14" fill="#0B1220" stroke="url(#sidebarBrandGradient)" strokeWidth="2" />
      <path d="M20 42L30 24L36 35L44 22" stroke="url(#sidebarBrandGradient)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="44" cy="22" r="3" fill="#67E8F9" />
    </svg>
  );
}

export function Sidebar() {
  const { user, logout } = useStore();
  const location = useLocation();
  const nav = useNavigate();

  const userModules = user?.modules || [];
  const visibleModules = useMemo(() => getVisibleModules(userModules), [userModules]);
  const activeModule = useMemo(
    () => getActiveModuleByPath(location.pathname, visibleModules),
    [location.pathname, visibleModules]
  );

  const handleLogout = () => { logout(); nav('/login'); };

  return (
    <aside className="relative flex w-72 shrink-0 flex-col overflow-hidden border-r border-slate-800 bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(153,27,27,0.22),transparent_34%)]" />
      {/* Header */}
      <div className="relative h-20 flex items-center gap-3 px-4 border-b border-slate-800">
        <div className="h-10 w-10 rounded-xl bg-rose-500/20 ring-1 ring-rose-300/30 flex items-center justify-center">
          <BrandMark />
        </div>
        <div>
          <p className="font-display text-sm font-semibold tracking-wide text-slate-100">Avelis</p>
          <p className="text-xs text-slate-400">Navigation modules</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative flex-1 overflow-y-auto px-3 py-4">
        <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          Modules
        </p>
        <div className="grid grid-cols-2 gap-2">
          {visibleModules.map((moduleItem) => (
            <button
              key={moduleItem.id}
              onClick={() => nav(moduleItem.items[0]?.to || '/')}
              className={`group rounded-xl border p-2.5 text-left transition ${
                moduleItem.id === activeModule?.id
                  ? 'border-rose-300/40 bg-rose-500/15 text-rose-100 ring-1 ring-rose-300/25'
                  : 'border-slate-700/70 bg-slate-900/65 text-slate-300 hover:border-slate-500 hover:bg-slate-800/70 hover:text-white'
              }`}
            >
              <div className="mb-1.5 inline-flex rounded-lg bg-slate-900/80 p-1.5 ring-1 ring-white/10">
                <moduleItem.icon className="h-3.5 w-3.5 shrink-0" />
              </div>
              <p className="line-clamp-2 text-xs leading-4">{moduleItem.label}</p>
            </button>
          ))}
        </div>
      </nav>

      {/* User footer */}
      <div className="relative p-3 border-t border-slate-800 bg-slate-950/80">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-slate-800 ring-1 ring-slate-600/60 flex items-center justify-center text-white text-xs font-bold">
            {user?.name?.charAt(0)?.toUpperCase() || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-100 truncate">{user?.name || 'Non connecte'}</p>
            <p className="text-xs text-slate-400 truncate">{user?.role || ''}</p>
          </div>
          <button onClick={handleLogout} title="Deconnexion"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors">
            &#10005;
          </button>
        </div>
      </div>
    </aside>
  );
}
