import { useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function EmployeeList() {
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterEntity, setFilterEntity] = useState('');
  const [search, setSearch] = useState('');

  const loadEmps = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    if (filterEntity) params.set('entity_id', filterEntity);
    api.get(`/drh/employees?${params}`).then(r => { setEmployees(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { loadEmps(); }, [filterStatus, filterEntity]);

  const filtered = search ? employees.filter(e =>
    (e.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (e.matricule || '').toLowerCase().includes(search.toLowerCase()) ||
    (e.department || '').toLowerCase().includes(search.toLowerCase())
  ) : employees;

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-4">Employes</h1>
      <div className="flex gap-3 mb-4">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Rechercher nom, matricule, departement..."
          className="flex-1 border border-mist rounded-input px-4 py-2 text-sm focus:border-iris outline-none" />
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
          <option value="">Tous statuts</option>
          <option value="ACTIVE">Actif</option>
          <option value="ONBOARDING">Onboarding</option>
          <option value="SUSPENDED">Suspendu</option>
          <option value="OFFBOARDING">Depart</option>
        </select>
        <select value={filterEntity} onChange={e => setFilterEntity(e.target.value)}
          className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
          <option value="">Toutes entites</option>
          <option value="ETS-DK">ETS-DK</option>
          <option value="SARL-DP">SARL-DP</option>
          <option value="SARL-DBPI">SARL-DBPI</option>
          <option value="SARL-OC">SARL-OC</option>
        </select>
      </div>
      <p className="text-xs text-storm mb-3">{filtered.length} employe(s)</p>
      {filtered.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center text-storm">Aucun employé trouvé</div>
      ) : (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-3 px-4 text-left font-medium text-storm">Matricule</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Nom</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Département</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Poste</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Entité</th>
              <th className="py-3 px-4 text-left font-medium text-storm">Statut</th>
            </tr></thead>
            <tbody>
              {filtered.map(e => (
                <tr key={e.matricule} className="border-b border-mist hover:bg-[#FAFAFA] transition cursor-pointer">
                  <td className="py-3 px-4 font-mono text-xs text-iris font-semibold">{e.matricule}</td>
                  <td className="py-3 px-4 font-medium">{e.name}</td>
                  <td className="py-3 px-4 text-storm">{e.department}</td>
                  <td className="py-3 px-4 text-storm">{e.position}</td>
                  <td className="py-3 px-4 text-storm">{e.entity}</td>
                  <td className="py-3 px-4">
                    <Badge variant={e.status === 'ACTIVE' ? 'success' : e.status === 'ONBOARDING' ? 'warning' : 'neutral'}>{e.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
