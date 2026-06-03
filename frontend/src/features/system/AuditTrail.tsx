import { useCallback, useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const ACTION_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  CREATE: 'success',
  UPDATE: 'warning',
  WRITE: 'warning',
  DELETE: 'error',
  APPROVE: 'success',
  REJECT: 'error',
  LOGIN: 'info',
  LOGOUT: 'info',
  UPLOAD: 'info',
  READ: 'neutral',
};

const ACTION_OPTIONS = [
  'CREATE', 'UPDATE', 'WRITE', 'DELETE', 'APPROVE', 'REJECT', 'LOGIN', 'LOGOUT', 'UPLOAD', 'READ',
];

const MODULE_OPTIONS = [
  'FINANCE', 'ADV', 'DRH', 'JURIDIQUE', 'GED', 'FONDATION', 'SYSTEM', 'STOCK', 'OPERATIONS',
];

export function AuditTrail() {
  const [entries, setEntries] = useState<any[]>([]);
  const [filters, setFilters] = useState({ user: '', action: '', module: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((active = filters) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (active.user.trim()) params.set('user_filter', active.user.trim());
    if (active.action) params.set('action', active.action);
    if (active.module) params.set('module', active.module);

    api
      .get(`/system/audit-trail?${params.toString()}`)
      .then((r) => {
        setEntries(r.data.data || []);
        setLoading(false);
      })
      .catch((e) => {
        setLoading(false);
        setError(e.response?.data?.detail || 'Impossible de charger le journal');
      });
  }, [filters]);

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    load();
  }, [filters.action, filters.module]);

  const clearFilters = () => {
    const empty = { user: '', action: '', module: '' };
    setFilters(empty);
    load(empty);
  };

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Audit Trail</h1>
      <p className="text-sm text-storm mb-6">Journal immutable — lecture seule, aucune modification possible</p>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div>
          <label className="block text-xs text-storm mb-1">Utilisateur</label>
          <input
            value={filters.user}
            onChange={(e) => setFilters((p) => ({ ...p, user: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && load(filters)}
            placeholder="Email ou nom..."
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none min-w-[200px]"
          />
        </div>
        <div>
          <label className="block text-xs text-storm mb-1">Action</label>
          <select
            value={filters.action}
            onChange={(e) => setFilters((p) => ({ ...p, action: e.target.value }))}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
          >
            <option value="">Toutes actions</option>
            {ACTION_OPTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-storm mb-1">Module</label>
          <select
            value={filters.module}
            onChange={(e) => setFilters((p) => ({ ...p, module: e.target.value }))}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none"
          >
            <option value="">Tous modules</option>
            {MODULE_OPTIONS.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => load(filters)}
          className="px-4 py-2 bg-iris text-white rounded-button text-sm font-medium hover:bg-rose-800"
        >
          Filtrer
        </button>
        <button
          type="button"
          onClick={clearFilters}
          className="px-4 py-2 border border-mist rounded-button text-sm text-storm hover:bg-[#FAFAFA]"
        >
          Reinitialiser
        </button>
      </div>

      {error && (
        <p className="text-sm text-coral mb-4">{error}</p>
      )}

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-12 bg-mist rounded-lg animate-pulse" />)}</div>
      ) : (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#FAFAFA] border-b-2 border-mist">
                <th className="py-2 px-3 text-left text-storm font-medium">Date</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Utilisateur</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Action</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Module</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Ressource</th>
                <th className="py-2 px-3 text-left text-storm font-medium">Detail</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-storm">
                    Aucune entree pour ces filtres
                  </td>
                </tr>
              ) : (
                entries.map((e) => (
                  <tr key={e.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                    <td className="py-2 px-3 font-mono text-xs">{e.date?.slice(0, 19)}</td>
                    <td className="py-2 px-3 text-xs">{e.user}</td>
                    <td className="py-2 px-3">
                      <Badge variant={ACTION_VARIANT[e.action] || 'neutral'}>{e.action}</Badge>
                    </td>
                    <td className="py-2 px-3 text-xs">{e.module || '—'}</td>
                    <td className="py-2 px-3 text-xs font-mono">
                      {e.resource_type} {e.resource_id || ''}
                    </td>
                    <td className="py-2 px-3 text-xs text-storm">
                      {e.data_after ? JSON.stringify(e.data_after).slice(0, 60) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
