import { useStore } from '../../store/useStore';

export function Header() {
  const { user, viewMode, setViewMode } = useStore();

  return (
    <header className="fixed top-0 left-64 right-0 h-16 bg-white border-b border-slate-200 flex items-center px-6 z-50">
      <div className="flex-1">
        <span className="text-sm text-slate-500">{user?.name || 'Tableau de bord'}</span>
        {user?.role && (
          <span className="ml-3 text-xs bg-teal-100 text-teal-800 px-2 py-0.5 rounded-full font-medium">{user.role}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
          <button onClick={() => setViewMode('interne')}
            className={`px-3 py-1.5 transition-colors ${viewMode === 'interne' ? 'bg-teal-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
            Vue Interne
          </button>
          <button onClick={() => setViewMode('officiel')}
            className={`px-3 py-1.5 transition-colors ${viewMode === 'officiel' ? 'bg-teal-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
            Vue Officielle
          </button>
        </div>
      </div>
    </header>
  );
}
