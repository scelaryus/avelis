import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowUpRight,
  Banknote,
  Briefcase,
  Building2,
  FileSearch,
  Gauge,
  Gavel,
  HardDrive,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { useStore } from '../../store/useStore';

type ModuleCard = {
  id: string;
  label: string;
  description: string;
  to: string;
  icon: typeof Gauge;
  accent: string;
};

const allModuleCards: ModuleCard[] = [
  { id: 'dashboard', label: 'Tableau de bord', description: 'Vue generale des indicateurs', to: '/dashboard', icon: Gauge, accent: 'from-rose-500/25 to-red-900/20' },
  { id: 'foundation', label: 'Fondation', description: 'Entites et projets', to: '/foundation/entities', icon: Building2, accent: 'from-red-500/25 to-red-900/20' },
  { id: 'finance', label: 'Finance', description: 'CC, CCA et rapprochement', to: '/finance/cc', icon: Banknote, accent: 'from-rose-600/25 to-red-900/20' },
  { id: 'adv', label: 'Administration des Ventes', description: 'Lots, dossiers et paiements', to: '/adv/lots', icon: Briefcase, accent: 'from-red-600/25 to-rose-900/20' },
  { id: 'stock', label: 'Stock & Fournisseurs', description: 'Catalogue, stock et fournisseurs', to: '/stock', icon: HardDrive, accent: 'from-red-700/25 to-red-950/20' },
  { id: 'operations', label: 'Operations', description: 'Engagements et suivi', to: '/operations', icon: FileSearch, accent: 'from-rose-700/25 to-red-950/20' },
  { id: 'rh', label: 'Ressources Humaines', description: 'Employes, paie et performance', to: '/rh/employees', icon: Users, accent: 'from-rose-500/25 to-red-900/20' },
  { id: 'juridique', label: 'Juridique', description: 'Contrats, litiges et conformite', to: '/juridique', icon: Gavel, accent: 'from-red-500/25 to-rose-900/20' },
  { id: 'ged', label: 'Documents', description: 'GED intelligence et recherche', to: '/documents', icon: ShieldCheck, accent: 'from-red-400/20 to-red-900/20' },
  { id: 'system', label: 'Systeme', description: 'Alertes, agents IA et audit', to: '/system/alerts', icon: Gauge, accent: 'from-rose-600/25 to-red-950/20' },
];

export function ModuleLauncher() {
  const nav = useNavigate();
  const userModules = useStore((state) => state.user?.modules || []);

  const visibleModules = useMemo(
    () => (userModules.length > 0 ? allModuleCards.filter((moduleItem) => userModules.includes(moduleItem.id)) : allModuleCards),
    [userModules]
  );

  return (
    <div className="module-launcher relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="module-bg-layer module-bg-layer--one" />
      <div className="module-bg-layer module-bg-layer--two" />
      <div className="module-bg-grid" />
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="mb-10 flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-rose-500/20 ring-1 ring-rose-300/30 module-pulse-icon">
            <Building2 className="h-5 w-5 text-rose-300" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100">Choisir un module</h1>
            <p className="mt-1 text-sm text-slate-300">Selectionnez un espace metier pour continuer.</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visibleModules.map((moduleItem, index) => (
            <button
              key={moduleItem.id}
              onClick={() => nav(moduleItem.to)}
              className={`module-card group relative overflow-hidden rounded-2xl border border-slate-700/70 bg-gradient-to-br ${moduleItem.accent} p-5 text-left shadow-lg shadow-black/10 ring-1 ring-white/5 backdrop-blur-sm transition hover:-translate-y-1 hover:border-rose-400/70 hover:ring-rose-300/20`}
              style={{ animationDelay: `${80 + index * 70}ms` }}
            >
              <span className="module-card-glow" />
              <div className="mb-6 flex items-center justify-between">
                <div className="rounded-xl bg-slate-900/60 p-2.5 ring-1 ring-white/10 transition group-hover:scale-110">
                  <moduleItem.icon className="h-5 w-5 text-slate-100" />
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-rose-200" />
              </div>

              <p className="text-base font-semibold text-slate-100">{moduleItem.label}</p>
              <p className="mt-1 text-sm leading-5 text-slate-300/95">{moduleItem.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
