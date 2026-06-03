import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatDate } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import api from '../../lib/api-client';

export function JuridiqueDashboard() {
  const [dash, setDash] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get('/juridique/compliance/dashboard').then(r => { setDash(r.data.data); setLoading(false); }).catch(() => setLoading(false)); }, []);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!dash) return <p className="text-storm">Données indisponibles</p>;

  const kpis = dash.kpis || {};
  const resolved = Math.round(kpis.open_litigations * parseFloat(kpis.resolution_rate || '67') / 100);
  const caseData = [{ name: 'Ouverts', value: kpis.open_litigations }, { name: 'Resolus', value: resolved }];

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-6">Juridique</h1>

      {/* KPI cards */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Litiges ouverts</p>
          <p className="text-2xl font-bold text-coral">{kpis.open_litigations}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Taux résolution</p>
          <p className="text-2xl font-bold text-mint">{kpis.resolution_rate}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Durée moyenne</p>
          <p className="text-2xl font-bold">{kpis.avg_duration_days}j</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Montants en jeu</p>
          <p className="text-2xl font-bold font-mono">{formatDA(kpis.amounts_at_stake)}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Alertes conformité</p>
          <p className="text-2xl font-bold text-coral">{kpis.compliance_alerts_open}</p>
        </div>
      </div>

      {/* Conformité par thème */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <h2 className="font-semibold mb-4">Conformité par thème</h2>
        <div className="grid grid-cols-5 gap-4">
          {Object.entries(dash.themes || {}).map(([name, t]: [string, any]) => (
            <div key={name} className={`p-4 rounded-lg border-2 ${t.status === 'ok' ? 'border-mint' : t.status === 'warning' ? 'border-honey' : 'border-coral'}`}>
              <p className="font-semibold text-sm">{name}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`w-3 h-3 rounded-full ${t.status === 'ok' ? 'bg-mint' : t.status === 'warning' ? 'bg-honey' : 'bg-coral'}`} />
                <span className="text-xs text-storm">{t.conforme}/{t.total} conforme</span>
              </div>
              {t.non_conforme > 0 && <p className="text-xs text-coral mt-1">{t.non_conforme} non conforme</p>}
            </div>
          ))}
        </div>
      </div>

      {/* Deadlines */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <h2 className="font-semibold mb-4">Échéances à venir (7 jours)</h2>
        {(dash.upcoming_deadlines || []).length === 0 ? <p className="text-sm text-storm">Aucune échéance proche</p> : (
          <div className="space-y-2">
            {dash.upcoming_deadlines.map((d: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-mist hover:border-iris transition">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-storm">{formatDate(d.date)}</span>
                  <Badge variant={d.type === 'Audience' ? 'error' : 'warning'}>{d.type}</Badge>
                  <span className="text-sm font-medium">{d.case || d.contract}</span>
                </div>
                <span className="text-xs text-storm">{d.detail}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-3 gap-4">
        <Link to="/juridique/contracts" className="bg-white rounded-card border border-mist p-6 shadow-card hover:shadow-card-hover hover:border-iris transition text-center">
          <p className="text-2xl mb-2">📋</p><p className="font-semibold">Contrats</p><p className="text-xs text-storm mt-1">Gérer les contrats juridiques</p>
        </Link>
        <Link to="/juridique/cases" className="bg-white rounded-card border border-mist p-6 shadow-card hover:shadow-card-hover hover:border-iris transition text-center">
          <p className="text-2xl mb-2">⚖️</p><p className="font-semibold">Dossiers Litiges</p><p className="text-xs text-storm mt-1">Pipeline contentieux</p>
        </Link>
        <Link to="/juridique/compliance" className="bg-white rounded-card border border-mist p-6 shadow-card hover:shadow-card-hover hover:border-iris transition text-center">
          <p className="text-2xl mb-2">✅</p><p className="font-semibold">Conformité</p><p className="text-xs text-storm mt-1">Alertes et règles</p>
        </Link>
      </div>
    </div>
  );
}
