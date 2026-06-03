import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { TopSubnav } from './components/layout/TopSubnav';
// Header removed — CRM-style layout has no top bar
import { LoginPage } from './features/auth/LoginPage';
import { useStore } from './store/useStore';
// Dashboard
import { CeoDashboard } from './features/dashboard/CeoDashboard';
import { ModuleLauncher } from './features/dashboard/ModuleLauncher';
// Foundation
import { EntitiesList } from './features/foundation/EntitiesList';
import { EntityDetail } from './features/foundation/EntityDetail';
import { ProjectsList } from './features/foundation/ProjectsList';
import { ProjectDetail } from './features/foundation/ProjectDetail';
// Finance
import { CcDashboard } from './features/finance/CcDashboard';
import { CcDrillDown } from './features/finance/CcDrillDown';
import { CcaDashboard } from './features/finance/CcaDashboard';
import { CcaWithdraw } from './features/finance/CcaWithdraw';
import { CffList } from './features/finance/CffList';
import { CffCreate } from './features/finance/CffCreate';
import { GacebRap } from './features/finance/GacebRap';
import { JournalUpload } from './features/finance/JournalUpload';
import { Rapprochement } from './features/finance/Rapprochement';
// ADV
import { AdvPipeline } from './features/adv/AdvPipeline';
import { DossierPipeline } from './features/adv/DossierPipeline';
import { LotCreate } from './features/adv/LotCreate';
import { DossierCreate } from './features/adv/DossierCreate';
import { DossierDetail } from './features/adv/DossierDetail';
import { PaymentForm } from './features/adv/PaymentForm';
import { PaymentsList } from './features/adv/PaymentsList';
import { EddImport } from './features/adv/EddImport';
// Stock & Fournisseurs
import { StockCatalogue } from './features/stock/StockCatalogue';
import { StockCapture } from './features/stock/StockCapture';
import { StockConsume } from './features/stock/StockConsume';
import { FournisseurPage } from './features/stock/FournisseurPage';
// Operations
import { OperationsList } from './features/operations/OperationsList';
import { OperationDetail } from './features/operations/OperationDetail';
import { OperationCreate } from './features/operations/OperationCreate';
// DRH
import { EmployeeList } from './features/rh/EmployeeList';
import { EmployeeCreate } from './features/rh/EmployeeCreate';
import { PayrollBatch } from './features/rh/PayrollBatch';
import { PayslipVerify } from './features/rh/PayslipVerify';
import { LeaveManagement } from './features/rh/LeaveManagement';
import { OffboardingChecklist } from './features/rh/OffboardingChecklist';
import { SpiDashboard } from './features/rh/SpiDashboard';
import { SpiDetail } from './features/rh/SpiDetail';
import { Spi360Dashboard } from './features/rh/Spi360Dashboard';
import { Spi360Detail } from './features/rh/Spi360Detail';
import { TaskNeeds } from './features/rh/TaskNeeds';
import { CommissionTracker } from './features/rh/CommissionTracker';
import { RecruitmentPage } from './features/rh/RecruitmentPage';
import { DisciplinePage } from './features/rh/DisciplinePage';
import { VisitorPage } from './features/rh/VisitorPage';
import { JobListingGenerator } from './features/rh/JobListingGenerator';
// Juridique
import { JuridiqueDashboard } from './features/juridique/JuridiqueDashboard';
import { ContractsList } from './features/juridique/ContractsList';
import { CasesList } from './features/juridique/CasesList';
import { CaseDetail } from './features/juridique/CaseDetail';
import { CompliancePage } from './features/juridique/CompliancePage';
import { ContractCreate } from './features/juridique/ContractCreate';
// System
import { AlertCenter } from './features/system/AlertCenter';
import { AgentStatus } from './features/system/AgentStatus';
import { AuditTrail } from './features/system/AuditTrail';
import { FormulaireResponse } from './features/system/FormulaireResponse';
import { FormulairesList } from './features/system/FormulairesList';
import { AgentControl } from './features/system/AgentControl';
// GED
import { DocumentSearch } from './features/ged/DocumentSearch';
import { DocumentLibrary } from './features/ged/DocumentLibrary';

export function App() {
  const { isAuthenticated } = useStore();
  const location = useLocation();

  // Login page — no sidebar/header
  if (location.pathname === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );
  }

  // Not authenticated → redirect to login
  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  const isModuleLauncher = location.pathname === '/';

  return (
    <div className="flex h-screen overflow-hidden">
      {!isModuleLauncher && <Sidebar />}
      <div className={`flex flex-1 flex-col overflow-hidden ${isModuleLauncher ? 'bg-slate-950' : 'bg-slate-50'}`}>
        {!isModuleLauncher && <TopSubnav />}
        <main className="flex-1 overflow-y-auto">
        <div className={isModuleLauncher ? '' : 'mx-auto max-w-7xl px-6 py-8'}>
        <Routes>
          <Route path="/" element={<ModuleLauncher />} />
          <Route path="/dashboard" element={<CeoDashboard />} />

          {/* Foundation */}
          <Route path="/foundation/entities" element={<EntitiesList />} />
          <Route path="/foundation/entities/:entityId" element={<EntityDetail />} />
          <Route path="/foundation/projects" element={<ProjectsList />} />
          <Route path="/foundation/projects/:projectCode" element={<ProjectDetail />} />

          {/* Finance */}
          <Route path="/finance/cc" element={<CcDashboard />} />
          <Route path="/finance/cc/:nodeCode" element={<CcDrillDown />} />
          <Route path="/finance/cca" element={<CcaDashboard />} />
          <Route path="/finance/cca/:associateId" element={<CcaDashboard />} />
          <Route path="/finance/cca/:associateId/withdraw" element={<CcaWithdraw />} />
          <Route path="/finance/cff" element={<CffList />} />
          <Route path="/finance/cff/new" element={<CffCreate />} />
          <Route path="/finance/gaceb" element={<GacebRap />} />
          <Route path="/finance/journal" element={<JournalUpload />} />
          <Route path="/finance/rapprochement" element={<Rapprochement />} />

          {/* ADV */}
          <Route path="/adv/lots" element={<AdvPipeline />} />
          <Route path="/adv/lots/new" element={<LotCreate />} />
          <Route path="/adv/pipeline" element={<DossierPipeline />} />
          <Route path="/adv/dossiers/new" element={<DossierCreate />} />
          <Route path="/adv/dossiers/:id" element={<DossierDetail />} />
          <Route path="/adv/payments" element={<PaymentsList />} />
          <Route path="/adv/dossiers/:id/payment" element={<PaymentForm />} />
          <Route path="/adv/pricing" element={<AdvPipeline />} />
          <Route path="/adv/edd/import" element={<EddImport />} />

          {/* Stock */}
          <Route path="/stock" element={<StockCatalogue />} />
          <Route path="/stock/new" element={<StockCapture />} />
          <Route path="/stock/consume" element={<StockConsume />} />
          <Route path="/fournisseurs" element={<FournisseurPage />} />

          {/* Operations */}
          <Route path="/operations" element={<OperationsList />} />
          <Route path="/operations/new" element={<OperationCreate />} />
          <Route path="/operations/:id" element={<OperationDetail />} />

          {/* DRH */}
          <Route path="/rh/employees" element={<EmployeeList />} />
          <Route path="/rh/employees/new" element={<EmployeeCreate />} />
          <Route path="/rh/payroll" element={<PayrollBatch />} />
          <Route path="/rh/payroll/payslips/:id/verify" element={<PayslipVerify />} />
          <Route path="/rh/leave" element={<LeaveManagement />} />
          <Route path="/rh/onboarding" element={<EmployeeList />} />
          <Route path="/rh/offboarding" element={<OffboardingChecklist />} />
          <Route path="/rh/spi" element={<Navigate to="/rh/spi360" replace />} />
          <Route path="/rh/spi360" element={<Spi360Dashboard />} />
          <Route path="/rh/spi360/:employeeId" element={<Spi360Detail />} />
          <Route path="/rh/spi360/tasks/needs" element={<TaskNeeds />} />
          <Route path="/rh/spi360/config" element={<Spi360Dashboard />} />
          <Route path="/rh/commissions" element={<CommissionTracker />} />
          <Route path="/rh/recruitment" element={<RecruitmentPage />} />
          <Route path="/rh/recruitment/listing" element={<JobListingGenerator />} />
          <Route path="/rh/discipline" element={<DisciplinePage />} />
          <Route path="/rh/visitors" element={<VisitorPage />} />

          {/* Juridique */}
          <Route path="/juridique" element={<JuridiqueDashboard />} />
          <Route path="/juridique/contracts" element={<ContractsList />} />
          <Route path="/juridique/contracts/new" element={<ContractCreate />} />
          <Route path="/juridique/cases" element={<CasesList />} />
          <Route path="/juridique/cases/:caseId" element={<CaseDetail />} />
          <Route path="/juridique/compliance" element={<CompliancePage />} />

          {/* GED */}
          <Route path="/documents" element={<DocumentLibrary />} />
          <Route path="/documents/search" element={<DocumentSearch />} />

          {/* System */}
          <Route path="/system/alerts" element={<AlertCenter />} />
          <Route path="/system/agents" element={<AgentStatus />} />
          <Route path="/system/agents/control" element={<AgentControl />} />
          <Route path="/system/audit" element={<AuditTrail />} />
          <Route path="/system/formulaires" element={<FormulairesList />} />
          <Route path="/system/formulaires/:code" element={<FormulaireResponse />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </div>
      </main>
      </div>
    </div>
  );
}
