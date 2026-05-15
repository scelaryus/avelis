import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  HomeIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  ChartBarIcon,
  UserGroupIcon,
  BanknotesIcon,
  CalculatorIcon,
  ScaleIcon,
  PresentationChartBarIcon,
  BuildingOffice2Icon,
  ShareIcon,
  ClipboardDocumentListIcon,
  CurrencyDollarIcon,
  HomeModernIcon,
  ArrowUpTrayIcon,
  BeakerIcon,
  ArrowsRightLeftIcon,
  ShieldCheckIcon,
  CubeIcon,
  ArrowsUpDownIcon,
} from "@heroicons/react/24/outline";

/* Map icon names from backend to actual components */
const iconMap: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  HomeIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ChartBarIcon,
  UserGroupIcon,
  BanknotesIcon,
  CalculatorIcon,
  ScaleIcon,
  PresentationChartBarIcon,
  BuildingOffice2Icon,
  ShareIcon,
  ClipboardDocumentListIcon,
  CurrencyDollarIcon,
  HomeModernIcon,
  ArrowUpTrayIcon,
  BeakerIcon,
  ArrowsRightLeftIcon,
  ShieldCheckIcon,
  CubeIcon,
};

export default function DashboardLayout() {
  const { user, menuItems, activeEntreprise, entreprises, switchEntreprise, logout } = useAuth();

  // If no active entreprise and multiple available → redirect to login for selection
  if (!activeEntreprise && entreprises.length > 1) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ──────────────────────────── */}
      <aside className="flex w-64 flex-col bg-slate-900 text-white">
        {/* Active entreprise header */}
        <div className="border-b border-slate-700">
          <div className="flex h-16 items-center gap-3 px-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-xs font-bold shrink-0 leading-tight">
              {activeEntreprise?.code
                ?.replace("SARL-", "")
                .replace("EURL-", "")
                .replace("ETS-", "")
                .substring(0, 3) || "GD"}
            </div>
            <div className="flex-1 min-w-0">
              <span className="block text-sm font-semibold tracking-tight truncate">
                {activeEntreprise?.raison_sociale || "Groupe Dendani"}
              </span>
              <span className="block text-xs text-slate-400 truncate">
                {activeEntreprise?.code || ""}{" "}
                {activeEntreprise?.forme_juridique ? `\u00B7 ${activeEntreprise.forme_juridique}` : ""}
              </span>
            </div>
          </div>
          {/* Switch entreprise button (only if user has access to multiple) */}
          {entreprises.length > 1 && (
            <button
              onClick={switchEntreprise}
              className="flex w-full items-center gap-2 px-5 py-2 text-xs text-slate-400 hover:bg-slate-800 hover:text-teal-300 transition-colors border-t border-slate-800"
            >
              <ArrowsUpDownIcon className="h-3.5 w-3.5" />
              Changer d'entit&eacute; ({entreprises.length})
            </button>
          )}
        </div>

        {/* Nav — driven by server menu */}
        <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
          {menuItems.map((item) => {
            const Icon = iconMap[item.icon || ""] || HomeIcon;
            return (
              <NavLink
                key={item.key}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-teal-600/20 text-teal-300"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`
                }
              >
                <Icon className="h-5 w-5 shrink-0" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="border-t border-slate-700 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold uppercase">
              {user?.full_name?.charAt(0) ?? "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{user?.full_name}</p>
              <p className="truncate text-xs text-slate-400">{user?.role}</p>
            </div>
            <button
              onClick={logout}
              className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
              title="D&eacute;connexion"
            >
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
