import {
  Banknote,
  Blocks,
  Briefcase,
  FileText,
  Gavel,
  Gauge,
  HardDrive,
  Settings2,
  Users,
  Workflow,
  type LucideIcon,
} from 'lucide-react';

export type ModuleDefinition = {
  id: string;
  label: string;
  icon: LucideIcon;
  items: Array<{ to: string; label: string }>;
};

export const modules: ModuleDefinition[] = [
  { id: 'dashboard', label: 'Tableau de bord', icon: Gauge, items: [{ to: '/dashboard', label: 'Dashboard' }] },
  { id: 'foundation', label: 'Fondation', icon: Blocks, items: [{ to: '/foundation/entities', label: 'Entites' }, { to: '/foundation/projects', label: 'Projets' }] },
  { id: 'finance', label: 'Finance', icon: Banknote, items: [{ to: '/finance/cc', label: 'Centre de Couts' }, { to: '/finance/cca', label: 'CCA Associes' }, { to: '/finance/journal', label: 'Journal Comptable' }, { to: '/finance/rapprochement', label: 'Rapprochement' }] },
  { id: 'adv', label: 'Administration des Ventes', icon: Briefcase, items: [{ to: '/adv/lots', label: 'Lots EDD' }, { to: '/adv/lots/new', label: 'Nouveau lot' }, { to: '/adv/edd/import', label: 'Importer EDD (AI)' }, { to: '/adv/pipeline', label: 'Pipeline Dossiers' }, { to: '/adv/payments', label: 'Paiements' }, { to: '/adv/dossiers/new', label: 'Nouveau dossier' }] },
  { id: 'stock', label: 'Stock & Fournisseurs', icon: HardDrive, items: [{ to: '/stock', label: 'Catalogue' }, { to: '/stock/new', label: 'Ajouter element' }, { to: '/stock/consume', label: 'Sortie stock' }, { to: '/fournisseurs', label: 'Fournisseurs' }] },
  { id: 'operations', label: 'Operations', icon: Workflow, items: [{ to: '/operations', label: 'Engagements' }, { to: '/operations/new', label: 'Nouvel engagement' }] },
  { id: 'rh', label: 'Ressources Humaines', icon: Users, items: [{ to: '/rh/employees', label: 'Employes' }, { to: '/rh/employees/new', label: 'Nouvel employe' }, { to: '/rh/payroll', label: 'Paie Mensuelle' }, { to: '/rh/leave', label: 'Conges' }, { to: '/rh/spi360', label: 'SPI Performance' }, { to: '/rh/commissions', label: 'Commissions' }, { to: '/rh/visitors', label: 'Visiteurs' }] },
  { id: 'juridique', label: 'Juridique', icon: Gavel, items: [{ to: '/juridique', label: 'Dashboard' }, { to: '/juridique/contracts', label: 'Contrats' }, { to: '/juridique/cases', label: 'Dossiers Litiges' }, { to: '/juridique/compliance', label: 'Conformite' }] },
  { id: 'ged', label: 'Documents', icon: FileText, items: [{ to: '/documents', label: 'GED Intelligence' }] },
  { id: 'system', label: 'Systeme', icon: Settings2, items: [{ to: '/system/alerts', label: 'Alertes' }, { to: '/system/agents', label: 'Agents IA' }, { to: '/system/audit', label: 'Audit Trail' }] },
];

export function getVisibleModules(userModules: string[]) {
  return userModules.length > 0 ? modules.filter((moduleItem) => userModules.includes(moduleItem.id)) : modules;
}

export function getActiveModuleByPath(pathname: string, visibleModules: ModuleDefinition[]) {
  let winner: ModuleDefinition | null = null;
  let longestMatch = -1;

  for (const moduleItem of visibleModules) {
    for (const item of moduleItem.items) {
      if (pathname.startsWith(item.to) && item.to.length > longestMatch) {
        longestMatch = item.to.length;
        winner = moduleItem;
      }
    }
  }

  return winner || visibleModules[0] || null;
}
