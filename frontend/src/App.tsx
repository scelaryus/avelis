import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import DashboardLayout from "./layouts/DashboardLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import AccountingPage from "./pages/AccountingPage";
import HRPage from "./pages/HRPage";
import ADVPage from "./pages/ADVPage";
import AdminPage from "./pages/AdminPage";
import CostCenterPage from "./pages/CostCenterPage";
import LegalPage from "./pages/LegalPage";
import SPIPage from "./pages/SPIPage";
import CFFPage from "./pages/CFFPage";
import TransactionsPage from "./pages/TransactionsPage";
import KillTestsPage from "./pages/KillTestsPage";
import RessourcesPage from "./pages/RessourcesPage";
import ChantiersPage from "./pages/ChantiersPage";
import WorkflowsDendaniPage from "./pages/WorkflowsDendaniPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
      </div>
    );
  }
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="workflows" element={<Navigate to="/documents" replace />} />
        <Route path="accounting" element={<AccountingPage />} />
        <Route path="hr" element={<HRPage />} />
        <Route path="my-tasks" element={<Navigate to="/dashboard" replace />} />
        <Route path="adv" element={<ADVPage />} />
        <Route path="bim-edd" element={<Navigate to="/adv" replace />} />
        <Route path="legal" element={<LegalPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="cost-center" element={<CostCenterPage />} />
        <Route path="spi" element={<SPIPage />} />
        <Route path="chantiers" element={<ChantiersPage />} />
        <Route path="workflows-dendani" element={<WorkflowsDendaniPage />} />
        <Route path="cff" element={<CFFPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="kill-tests" element={<KillTestsPage />} />
        <Route path="ressources" element={<RessourcesPage />} />
        {/* Redirects for removed pages */}
        <Route path="organization" element={<Navigate to="/dashboard" replace />} />
        <Route path="entites-juridiques" element={<Navigate to="/dashboard" replace />} />
        <Route path="company-registry" element={<Navigate to="/dashboard" replace />} />
        <Route path="real-estate" element={<Navigate to="/adv" replace />} />
        <Route path="finance-associes" element={<Navigate to="/adv" replace />} />
        <Route path="import" element={<Navigate to="/documents" replace />} />
      </Route>
    </Routes>
  );
}
