import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadialBarChart, RadialBar, AreaChart, Area,
} from 'recharts';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

const PROJ_COLORS = ['#6C5CE7', '#0984E3', '#00B894', '#E17055', '#FDCB6E', '#A29BFE', '#74B9FF', '#55EFC4'];
const LOT_COLORS: Record<string, string> = { DISPONIBLE: '#00B894', RESERVE: '#0984E3', ENGAGE: '#6C5CE7', VENDU: '#636E72' };

function DashboardHeroIllustration() {
  return (
    <div className="dashboard-hero-illustration">
      <svg viewBox="0 0 520 180" className="h-[170px] w-full" fill="none" aria-hidden="true">
        <rect x="18" y="26" width="148" height="116" rx="16" className="dash-card-surface" />
        <rect x="34" y="46" width="72" height="8" rx="4" className="fill-rose-300/70" />
        <rect x="34" y="64" width="116" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="34" y="79" width="92" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="34" y="100" width="110" height="28" rx="8" className="fill-red-300/70" />

        <rect x="188" y="10" width="148" height="116" rx="16" className="dash-card-surface dash-float-card" />
        <rect x="204" y="32" width="98" height="8" rx="4" className="fill-red-300/70" />
        <circle cx="222" cy="68" r="15" className="fill-red-300/25" />
        <circle cx="222" cy="68" r="7" className="fill-red-300/80" />
        <rect x="246" y="62" width="74" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="246" y="77" width="58" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="204" y="98" width="92" height="18" rx="9" className="fill-rose-300/75" />

        <rect x="354" y="44" width="148" height="116" rx="16" className="dash-card-surface" />
        <rect x="370" y="64" width="76" height="8" rx="4" className="fill-rose-300/70" />
        <rect x="370" y="82" width="112" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="370" y="98" width="96" height="7" rx="3.5" className="fill-slate-400/60" />
        <rect x="370" y="119" width="86" height="26" rx="8" className="fill-red-300/70" />

        <path d="M166 84C182 84 178 64 188 64" className="dash-link-path dash-link-path--one" />
        <path d="M336 76C354 76 346 102 354 102" className="dash-link-path dash-link-path--two" />
        <circle cx="188" cy="64" r="4" className="fill-rose-300 dash-link-node node-one" />
        <circle cx="354" cy="102" r="4" className="fill-red-300 dash-link-node node-two" />
      </svg>
    </div>
  );
}

export function CeoDashboard() {
  const { user } = useStore();
  const modules = user?.modules || [];
  const has = (m: string) => modules.includes(m) || modules.length === 0; // empty = dev mode = show all
  const [dash, setDash] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [eddProjects, setEddProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/system/dashboard'),
      api.get('/system/alerts'),
      api.get('/adv/edd/dashboard'),
    ]).then(([dashR, alertR, eddR]) => {
      setDash(dashR.data.data);
      setAlerts(alertR.data.data || []);
      setEddProjects(eddR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-6">{[1,2,3,4].map(i => <div key={i} className="h-36 bg-mist rounded-card animate-pulse" />)}</div>
      <div className="grid grid-cols-3 gap-6">{[1,2,3].map(i => <div key={i} className="h-64 bg-mist rounded-card animate-pulse" />)}</div>
    </div>
  );
  if (!dash) return <p className="text-storm">Donnees indisponibles</p>;

  const treasury = parseFloat(dash.treasury_global);
  const rf1 = parseFloat(dash.rf1_total || '0');
  const rf2 = parseFloat(dash.rf2_total || '0');
  const rfTotal = rf1 + rf2;
  const lotStats = dash.lot_by_status || {};
  const lotPie = Object.entries(lotStats).filter(([, v]) => (v as number) > 0).map(([k, v]) => ({ name: k, value: v as number }));
  const projStats: any[] = (eddProjects || []).map((p: any) => {
    const totalLots = p.total_lots || 0;
    const available = p.by_status?.DISPONIBLE || 0;
    const soldOrEngaged = Math.max(totalLots - available, 0);
    const pctFromApi = typeof p.taux_commercialisation === 'string'
      ? parseInt(p.taux_commercialisation.replace('%', ''), 10)
      : null;
    const pct = Number.isFinite(pctFromApi as number)
      ? (pctFromApi as number)
      : (totalLots > 0 ? Math.round((soldOrEngaged * 100) / totalLots) : 0);
    return {
      code: p.project,
      name: p.project_name || p.project,
      lots_total: totalLots,
      lots_sold: soldOrEngaged,
      commercialisation_pct: pct,
    };
  });
  const gacebPct = dash.gaceb_residual ? Math.round((1 - parseFloat(dash.gaceb_residual) / 120000000) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="dashboard-hero dashboard-enter relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-slate-800 to-red-950 px-6 py-6 text-white shadow-sm">
        <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-red-400/20 blur-2xl" />
        <div className="grid items-center gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-rose-200">Vue executive</p>
            <h1 className="mt-2 text-3xl font-bold">Dashboard {user?.name || 'DAF'}</h1>
            <p className="mt-2 text-sm text-slate-200">
              Pilotage global des modules, tresorerie, performance commerciale et alertes critiques.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs text-slate-100">Entites: {dash.entities_count}</span>
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs text-slate-100">Projets actifs: {dash.projects_active}</span>
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs text-slate-100">Alertes: {alerts.length}</span>
            </div>
          </div>
          <DashboardHeroIllustration />
        </div>
      </div>

      {/* Row 1 — KPI cards (filtered by module access) */}
      <div className="grid grid-cols-4 gap-6 mb-6">
        {/* Treasury — finance only */}
        {has('finance') && <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition" style={{ animationDelay: '80ms' }}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-storm font-medium">Tresorerie Globale</p>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${treasury < 0 ? 'bg-[rgba(255,107,107,0.1)]' : 'bg-[rgba(0,184,148,0.1)]'}`}>
              {treasury < 0 ? '↓' : '↑'}
            </div>
          </div>
          <p className={`text-[26px] font-bold font-mono ${treasury < 0 ? 'text-coral' : 'text-rose-700'}`}>{formatDA(dash.treasury_global)}</p>
          <p className="text-xs text-storm mt-2">{dash.entities_count} entites consolidees</p>
        </div>}

        {/* Projects — radial gauge — foundation */}
        {has('foundation') && <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition" style={{ animationDelay: '140ms' }}>
          <p className="text-sm text-storm font-medium mb-1">Projets</p>
          <div className="flex items-center gap-4">
            <div className="w-16 h-16">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="100%" barSize={6}
                  data={[{ value: dash.projects_active, fill: '#6C5CE7' }]} startAngle={90} endAngle={-270}>
                  <RadialBar background={{ fill: '#DFE6E9' }} dataKey="value" cornerRadius={6}
                    max={dash.projects_total} />
                </RadialBarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="text-[26px] font-bold">{dash.projects_active}</p>
              <p className="text-xs text-storm">/ {dash.projects_total} total</p>
            </div>
          </div>
        </div>}

        {/* Lots — donut — adv */}
        {has('adv') && <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition" style={{ animationDelay: '200ms' }}>
          <p className="text-sm text-storm font-medium mb-1">Lots ({dash.lots_total})</p>
          <div className="flex items-center gap-3">
            <div className="w-16 h-16">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={lotPie} cx="50%" cy="50%" innerRadius={18} outerRadius={28} paddingAngle={2} dataKey="value" stroke="none">
                    {lotPie.map((d, i) => <Cell key={i} fill={LOT_COLORS[d.name] || '#B2BEC3'} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-0.5">
              {lotPie.map(d => (
                <div key={d.name} className="flex items-center gap-1.5 text-[11px]">
                  <span className="w-2 h-2 rounded-full" style={{ background: LOT_COLORS[d.name] || '#B2BEC3' }} />
                  <span className="text-storm">{d.name}</span>
                  <span className="font-bold">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="text-xs text-iris font-medium mt-2">{dash.taux_commercialisation} commercialise</p>
        </div>}

        {/* Alerts — always visible */}
        <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition" style={{ animationDelay: '260ms' }}>
          <p className="text-sm text-storm font-medium mb-3">Alertes</p>
          <p className="text-[26px] font-bold mb-2">{alerts.length}</p>
          <div className="flex gap-1.5">
            {[['CRITIQUE', 'bg-coral'], ['ALERTE', 'bg-[#E17055]'], ['ATTENTION', 'bg-honey'], ['INFO', 'bg-ocean']].map(([lev, bg]) => {
              const count = alerts.filter(a => a.level === lev).length;
              return count > 0 ? (
                <span key={lev} className={`${bg} text-white text-[10px] font-bold px-2 py-0.5 rounded-full`}>{count} {lev}</span>
              ) : null;
            })}
            {alerts.length === 0 && <Badge variant="success">Tout OK</Badge>}
          </div>
        </div>
      </div>

      {/* Row 2 — Mini KPI strip (filtered by module) */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {[
          has('rh') && { label: 'Employes', value: dash.employees_active, icon: '👥', color: 'text-iris' },
          has('rh') && { label: 'Bulletins en attente', value: dash.payslips_pending, icon: '📋', color: dash.payslips_pending > 0 ? 'text-coral' : 'text-rose-700' },
          has('finance') && { label: 'Fournisseurs', value: dash.suppliers_count || 0, icon: '🏗️', color: 'text-iris', sub: `Reste: ${formatDA(dash.supplier_remaining || '0')}` },
          has('stock') && { label: 'Stock', value: `${dash.stock_items_count || 0} items`, icon: '📦', color: 'text-iris', sub: formatDA(dash.stock_total_value || '0') },
          has('adv') && { label: 'Dossiers ADV', value: dash.dossiers_active, icon: '📂', color: 'text-iris' },
          has('finance') && { label: 'CC Ecritures', value: dash.cc_entries_count || 0, icon: '📊', color: 'text-iris', sub: formatDA(dash.cc_total_entries || '0') },
        ].filter(Boolean).slice(0, 5).map((k: any, i) => (
          <div key={i} className="dashboard-enter dashboard-chip bg-white rounded-xl border border-slate-200 p-3.5 shadow-sm flex items-center gap-3" style={{ animationDelay: `${320 + i * 50}ms` }}>
            <span className="text-xl">{k.icon}</span>
            <div>
              <p className="text-[11px] text-storm">{k.label}</p>
              <p className={`text-base font-bold font-mono ${k.color}`}>{k.value}</p>
              {k.sub && <p className="text-[10px] text-storm">{k.sub}</p>}
            </div>
          </div>
        ))}
      </div>

      {/* Row 3 — Project commercialisation bars + RF split (adv + finance) */}
      {(has('adv') || has('finance')) && <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Project commercialisation horizontal bars */}
        {has('adv') && <div className="dashboard-enter dashboard-card col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm" style={{ animationDelay: '520ms' }}>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Commercialisation par Projet</h2>
            <Link to="/adv/lots" className="text-xs font-medium text-rose-700 hover:underline">
              Ouvrir menu Lots
            </Link>
          </div>
          {projStats.length === 0 ? (
            <p className="text-sm text-storm text-center py-8">Aucun projet avec lots</p>
          ) : (
            <div className="space-y-3">
              {projStats.filter(p => p.lots_total > 0).sort((a, b) => b.commercialisation_pct - a.commercialisation_pct).map((p, i) => (
                <div key={p.code} className="flex items-center gap-3">
                  <div className="w-20 text-right">
                    <Link to="/adv/lots" className="text-xs font-semibold hover:underline" style={{ color: PROJ_COLORS[i % PROJ_COLORS.length] }}>
                      {p.name}
                    </Link>
                  </div>
                  <div className="flex-1">
                    <div className="bg-mist rounded-full h-5 overflow-hidden relative">
                      <div className="h-full rounded-full transition-all duration-700 dashboard-bar"
                        style={{ width: `${p.commercialisation_pct}%`, background: PROJ_COLORS[i % PROJ_COLORS.length] }} />
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mix-blend-difference">
                        {p.lots_sold}/{p.lots_total} lots — {p.commercialisation_pct}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {projStats.filter(p => p.lots_total === 0).map(p => (
                <div key={p.code} className="flex items-center gap-3 opacity-50">
                  <div className="w-20 text-right"><span className="text-xs font-mono">{p.code}</span></div>
                  <div className="flex-1 text-xs text-storm italic">Pas de lots</div>
                </div>
              ))}
            </div>
          )}
        </div>}

        {/* RF distribution donut — finance */}
        {has('finance') && <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm" style={{ animationDelay: '580ms' }}>
          <h2 className="text-base font-semibold mb-4">Distribution RF</h2>
          {rfTotal > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={150}>
                <PieChart>
                  <Pie data={[{ name: 'Reel Declare', value: rf1 || 1 }, ...(rf2 ? [{ name: 'Reel Non Declare', value: rf2 }] : [])]}
                    cx="50%" cy="50%" innerRadius={40} outerRadius={60} paddingAngle={3} dataKey="value" stroke="none">
                    <Cell fill="#0984E3" />{rf2 > 0 && <Cell fill="#6C5CE7" />}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatDA(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-6 mt-2">
                <span className="flex items-center gap-1.5 text-xs"><span className="w-3 h-3 rounded-full bg-ocean" /> Reel Declare {formatDA(rf1)}</span>
                {rf2 > 0 && <span className="flex items-center gap-1.5 text-xs"><span className="w-3 h-3 rounded-full bg-iris" /> Reel Non Declare {formatDA(rf2)}</span>}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="w-16 h-16 rounded-full bg-mist flex items-center justify-center text-2xl mb-3">📊</div>
              <p className="text-sm text-storm">Aucun paiement enregistre</p>
              <p className="text-xs text-silver mt-1">Les paiements ADV alimenteront ce graphique</p>
            </div>
          )}
        </div>}
      </div>}

      {/* Row 4 — CCA Associate cards — finance only */}
      {has('finance') && <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm mb-6" style={{ animationDelay: '640ms' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">CCA Associes Fondateurs</h2>
          <Link to="/finance/cca" className="text-xs text-iris hover:underline font-medium">Voir detail →</Link>
        </div>
        <div className="grid grid-cols-4 gap-4">
          {(dash.associates || []).map((a: any) => {
            const bal = parseFloat(a.cca_balance);
            const maxAbs = Math.max(...(dash.associates || []).map((x: any) => Math.abs(parseFloat(x.cca_balance))));
            const barWidth = maxAbs > 0 ? Math.abs(bal) / maxAbs * 100 : 0;
            return (
              <Link to="/finance/cca" key={a.name} className="p-4 rounded-lg border border-mist hover:border-iris transition group">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-full bg-iris text-white flex items-center justify-center text-xs font-bold group-hover:scale-110 transition">
                    {a.name.split(' ').pop()?.[0]}
                  </div>
                  <span className="font-semibold text-sm">{a.name.replace('ADMIN ', '')}</span>
                </div>
                <p className={`text-xl font-bold font-mono ${bal < 0 ? 'text-coral' : 'text-rose-700'}`}>{formatDA(a.cca_balance)}</p>
                {/* Balance bar */}
                <div className="mt-3 flex items-center gap-1.5">
                  {bal < 0 ? (
                    <>
                      <div className="flex-1 flex justify-end"><div className="bg-coral rounded-l h-2" style={{ width: `${barWidth}%` }} /></div>
                      <div className="w-px h-4 bg-charcoal" />
                      <div className="flex-1" />
                    </>
                  ) : (
                    <>
                      <div className="flex-1" />
                      <div className="w-px h-4 bg-charcoal" />
                      <div className="flex-1"><div className="bg-rose-700 rounded-r h-2" style={{ width: `${barWidth}%` }} /></div>
                    </>
                  )}
                </div>
                {/* Per-entity breakdown */}
                {a.per_entity && (
                  <div className="mt-2 space-y-0.5">
                    {a.per_entity.slice(0, 3).map((e: any) => (
                      <div key={e.entity_code} className="flex justify-between text-[10px]">
                        <span className="text-storm">{e.entity_code}</span>
                        <span className={`font-mono ${parseFloat(e.balance) < 0 ? 'text-coral' : 'text-rose-700'}`}>{formatDA(e.balance)}</span>
                      </div>
                    ))}
                    {a.per_entity.length > 3 && <p className="text-[10px] text-silver">+{a.per_entity.length - 3} entites...</p>}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      </div>}

      {/* Row 5 — Alerts — always visible */}
      <div className="dashboard-enter dashboard-card bg-white rounded-2xl border border-slate-200 p-6 shadow-sm" style={{ animationDelay: '700ms' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">Alertes Actives ({alerts.length})</h2>
          <Link to="/system/alerts" className="text-xs text-iris hover:underline font-medium">Voir toutes →</Link>
        </div>
        {alerts.length === 0 ? (
          <div className="flex items-center gap-3 py-6 justify-center">
            <div className="w-12 h-12 rounded-full bg-[rgba(0,184,148,0.1)] flex items-center justify-center text-xl">✅</div>
            <div>
              <p className="font-semibold text-rose-700">Aucune alerte active</p>
              <p className="text-xs text-storm">Tous les systemes fonctionnent normalement</p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.slice(0, 8).map((a: any, i: number) => (
              <div key={i} className={`flex items-center gap-3 p-3 rounded-lg transition ${
                a.level === 'CRITIQUE' ? 'bg-[rgba(253,121,168,0.06)] border border-coral/20' :
                a.level === 'ALERTE' ? 'bg-[rgba(225,112,85,0.04)]' : 'hover:bg-gray-50'}`}>
                <Badge variant={a.level === 'CRITIQUE' ? 'error' : a.level === 'ALERTE' ? 'warning' : a.level === 'ATTENTION' ? 'warning' : 'info'}>{a.level}</Badge>
                <span className="text-[10px] bg-mist text-storm px-1.5 py-0.5 rounded font-medium">{a.module}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{a.title}</p>
                  <p className="text-xs text-storm truncate">{a.message}</p>
                </div>
              </div>
            ))}
            {alerts.length > 8 && <p className="text-xs text-iris text-center font-medium pt-2">+{alerts.length - 8} alertes supplementaires</p>}
          </div>
        )}
      </div>
    </div>
  );
}
