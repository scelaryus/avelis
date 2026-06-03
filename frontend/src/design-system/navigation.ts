/**
 * GFI v7.0 — Navigation Structure + 30 Screen Route Definitions.
 *
 * Sidebar sections with RBAC filtering.
 * Each screen defines: route, title, required permissions, data sources.
 */

// ── Sidebar Navigation ──────────────────────────────────────────────────────
export const sidebarSections = [
  {
    id: "accueil",
    label: "Accueil",
    icon: "Home",
    items: [
      { route: "/dashboard", label: "Dashboard", screen: "S01" },
    ],
  },
  {
    id: "finance",
    label: "Finance",
    icon: "Wallet",
    badgeSource: "alerts.finance",
    items: [
      { route: "/finance/cc", label: "Centre de Coûts", screen: "S02" },
      { route: "/finance/cca", label: "CCA Associés", screen: "S03", permissions: ["cc.read"] },
      { route: "/finance/tresorerie", label: "Trésorerie", screen: "S11" },
      { route: "/finance/cloture", label: "Clôture Mensuelle", screen: "S11" },
      { route: "/finance/cff", label: "CFF", screen: "S12", permissions: ["cff.read"] },
      { route: "/finance/inter-projets", label: "Flux Inter-Projets", screen: "S13" },
      { route: "/finance/gaceb", label: "GACEB RAP", screen: "S09" },
    ],
  },
  {
    id: "adv",
    label: "ADV",
    icon: "Building2",
    badgeSource: "lots.blocked",
    items: [
      { route: "/adv/edd", label: "Lots EDD", screen: "S05" },
      { route: "/adv/pipeline", label: "Pipeline Dossiers", screen: "S04" },
      { route: "/adv/paiements", label: "Paiements", screen: "S04" },
      { route: "/adv/deblocages", label: "Déblocages Crédit", screen: "S04" },
      { route: "/adv/formulaires", label: "Formulaires", screen: "S06" },
    ],
  },
  {
    id: "operations",
    label: "Opérations",
    icon: "ClipboardList",
    badgeSource: "operations.retard",
    items: [
      { route: "/operations/engagements", label: "Engagements", screen: "S24" },
      { route: "/operations/gantt", label: "Planning Gantt", screen: "S26" },
      { route: "/operations/budget", label: "Budget Agrégé", screen: "S25" },
      { route: "/operations/s-curve", label: "Courbe en S", screen: "S27" },
    ],
  },
  {
    id: "rh",
    label: "RH",
    icon: "Users",
    badgeSource: "payslips.pending",
    items: [
      { route: "/rh/employes", label: "Employés", screen: "S14" },
      { route: "/rh/paie", label: "Paie", screen: "S10" },
      { route: "/rh/conges", label: "Congés", screen: "S16" },
      { route: "/rh/recrutement", label: "Recrutement", screen: "S14" },
      { route: "/rh/pointage", label: "Pointage", screen: "S15" },
      { route: "/rh/offboarding", label: "Départs", screen: "S17" },
    ],
  },
  {
    id: "juridique",
    label: "Juridique",
    icon: "Scale",
    badgeSource: "compliance.alerts",
    items: [
      { route: "/juridique/contrats", label: "Contrats", screen: "S22" },
      { route: "/juridique/litiges", label: "Dossiers Litiges", screen: "S21" },
      { route: "/juridique/conformite", label: "Conformité", screen: "S23" },
      { route: "/juridique/dashboard", label: "Dashboard Juridique", screen: "S20" },
    ],
  },
  {
    id: "documents",
    label: "Documents",
    icon: "FileText",
    badgeSource: "docs.pending",
    items: [
      { route: "/documents/ged", label: "GED Recherche", screen: "S07" },
      { route: "/documents/upload", label: "Upload", screen: "S07" },
      { route: "/documents/verification", label: "Vérification", screen: "S08" },
    ],
  },
  {
    id: "systeme",
    label: "Système",
    icon: "Settings",
    badgeSource: "system.incidents",
    permissions: ["system.config"],
    items: [
      { route: "/systeme/meta-ia", label: "Méta-IA", screen: "S30" },
      { route: "/systeme/audit", label: "Audit Trail", screen: "S29" },
      { route: "/systeme/alertes", label: "Centre d'Alertes", screen: "S29" },
      { route: "/systeme/config", label: "Configuration", screen: "S28" },
    ],
  },
] as const;

// ── 30 Screen Definitions ───────────────────────────────────────────────────
export const screens = {
  S01: {
    route: "/dashboard",
    title: "Dashboard CEO",
    description: "KPIs, CA mensuel, RF distribution, alertes",
    dataSources: ["cost_center", "financial_transaction", "alert", "project"],
    refreshInterval: 60000, // 1 min
  },
  S02: {
    route: "/finance/cc",
    title: "Centre de Coûts",
    description: "6-level hierarchy, double view Officiel|Interne",
    dataSources: ["cost_center_node", "cost_center_entry", "margin_calculation"],
    features: ["tree_view", "table_view", "chart_view", "double_view_toggle"],
  },
  S03: {
    route: "/finance/cca",
    title: "CCA Associés",
    description: "4 founder cards + movement detail",
    dataSources: ["cca_account", "cca_movement"],
  },
  S04: {
    route: "/adv/pipeline",
    title: "Pipeline ADV (Kanban)",
    description: "Lot states as columns, NO drag-and-drop",
    dataSources: ["dossier_adv", "lot", "payment"],
    dragDropDisabled: true,
  },
  S05: {
    route: "/adv/edd",
    title: "EDD Pricing Grid",
    description: "Per project per typology pricing",
    dataSources: ["lot", "project"],
  },
  S06: {
    route: "/adv/formulaires",
    title: "Formulaire Dynamique",
    description: "Blocking workflow — NO close if action required",
    dataSources: ["formulaire", "formulaire_catalogue"],
    forceResponse: true,
  },
  S07: {
    route: "/documents/ged",
    title: "GED Recherche",
    description: "Semantic search with debounce 300ms",
    dataSources: ["document"],
    searchDebounce: 300,
  },
  S08: {
    route: "/documents/verification",
    title: "Pipeline Vérification",
    description: "L1-L6 / V1-V10 status with approve/reject",
    dataSources: ["payslip_verification", "verification_run"],
  },
  S09: {
    route: "/finance/gaceb",
    title: "GACEB RAP Dashboard",
    description: "Waterfall chart + situations table + vehicle 5-step",
    dataSources: ["gaceb_advance", "work_situation", "vehicle"],
  },
  S10: {
    route: "/rh/paie",
    title: "Validation Bulletins (L1-L6)",
    description: "PDF preview + 6-level pipeline + department stats",
    dataSources: ["payslip", "payslip_verification"],
  },
  S11: {
    route: "/finance/cloture",
    title: "Clôture Mensuelle",
    description: "7-step wizard with MFA signature",
    dataSources: ["treasury_closing", "bank_movement"],
  },
  S12: {
    route: "/finance/cff",
    title: "CFF Détection & Imputation",
    description: "RF3 invoices + per-associate imputation",
    dataSources: ["cff_calculation", "cff_imputation", "financial_transaction"],
  },
  S13: {
    route: "/finance/inter-projets",
    title: "Flux Inter-Projets",
    description: "Sankey diagram of inter-project flows",
    dataSources: ["inter_project_flow"],
  },
  S14: {
    route: "/rh/employes",
    title: "Onboarding Wizard",
    description: "Multi-step: Demande → Activation",
    dataSources: ["employee", "recruitment_request", "onboarding_checklist"],
  },
  S15: {
    route: "/rh/pointage",
    title: "Calendrier Pointage",
    description: "Monthly grid color-coded by presence status",
    dataSources: ["badge_event", "leave_request"],
  },
  S16: {
    route: "/rh/conges",
    title: "Gestion Congés",
    description: "Team calendar + leave form + balance",
    dataSources: ["leave_request", "leave_balance"],
  },
  S17: {
    route: "/rh/offboarding",
    title: "Checklist Départ",
    description: "6 blocks — STC blocked until ALL green",
    dataSources: ["offboarding_process", "stc_calculation"],
  },
  S18: {
    route: "/bim/viewer",
    title: "BIM 3D Viewer",
    description: "IFC Three.js with validation colors",
    dataSources: ["bim_model"],
  },
  S19: {
    route: "/bim/validation",
    title: "Matrice Validation BIM",
    description: "Design/Budget/Montage scores per element",
    dataSources: ["bim_validation"],
  },
  S20: {
    route: "/juridique/dashboard",
    title: "Dashboard Juridique",
    description: "KPIs + litigation charts + compliance status",
    dataSources: ["legal_case", "legal_compliance_alert"],
  },
  S21: {
    route: "/juridique/litiges",
    title: "Litiges Kanban",
    description: "Stage columns, NO drag-and-drop",
    dataSources: ["legal_case"],
    dragDropDisabled: true,
  },
  S22: {
    route: "/juridique/contrats",
    title: "Gestion Contrats",
    description: "List + expiry alerts + pipeline",
    dataSources: ["legal_contract", "contract_lifecycle"],
  },
  S23: {
    route: "/juridique/conformite",
    title: "Dashboard Conformité",
    description: "Status by theme with color codes",
    dataSources: ["legal_compliance_rule", "legal_compliance_alert"],
  },
  S24: {
    route: "/operations/engagements",
    title: "Liste Engagements",
    description: "Operations with budget + planning progress bars",
    dataSources: ["operation", "operation_budget_agrege"],
  },
  S25: {
    route: "/operations/budget",
    title: "Budget Agrégé (11 sources)",
    description: "Per-source breakdown with variance coloring",
    dataSources: ["operation_budget_agrege"],
  },
  S26: {
    route: "/operations/gantt",
    title: "Gantt Planning",
    description: "WBS + bars + dependencies + critical path + baseline",
    dataSources: ["operation_planning_task", "operation_dependency", "operation_snapshot"],
  },
  S27: {
    route: "/operations/s-curve",
    title: "Courbe en S",
    description: "Physical vs financial advancement",
    dataSources: ["operation", "operation_planning_task"],
  },
  S28: {
    route: "/systeme/config",
    title: "Configuration Pricing",
    description: "Per project tier pricing grid",
    dataSources: ["lot", "project"],
  },
  S29: {
    route: "/systeme/alertes",
    title: "Centre d'Alertes",
    description: "Unified alerts across ALL modules",
    dataSources: ["alert", "legal_compliance_alert", "verification_run"],
  },
  S30: {
    route: "/systeme/meta-ia",
    title: "Système & Méta-IA",
    description: "Agent status, task queue, LLM latency, proposals",
    dataSources: ["meta_ia_proposal", "meta_ia_sandbox", "legal_ai_task"],
  },
} as const;
