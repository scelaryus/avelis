import { useStore } from '../../store/useStore';

export function DoubleViewToggle() {
  const { viewMode, setViewMode } = useStore();
  return (
    <div className="flex bg-mist rounded-lg p-0.5">
      <button onClick={() => setViewMode('officiel')}
        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${viewMode === 'officiel' ? 'bg-iris text-white shadow-sm' : 'text-storm hover:text-charcoal'}`}>
        Officiel
      </button>
      <button onClick={() => setViewMode('interne')}
        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${viewMode === 'interne' ? 'bg-iris text-white shadow-sm' : 'text-storm hover:text-charcoal'}`}>
        Interne
      </button>
    </div>
  );
}
