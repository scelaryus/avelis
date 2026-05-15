import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import api from "../api/client";

/* ── Types ─────────────────────────────────────────── */
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  employee_id?: string;
}

export interface Company {
  id: string;
  name: string;
  code?: string;
  logo_url?: string;
  description?: string;
}

export interface EntrepriseInfo {
  id: string;
  code: string;
  raison_sociale: string;
  forme_juridique?: string;
  statut?: string;
  role_principal?: string;
}

export interface MenuItem {
  key: string;
  label: string;
  path: string;
  icon?: string;
}

interface AuthState {
  user: User | null;
  company: Company | null;
  entreprises: EntrepriseInfo[];
  activeEntreprise: EntrepriseInfo | null;
  menuItems: MenuItem[];
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ needsSelection: boolean }>;
  selectEntreprise: (entrepriseId: string) => Promise<void>;
  switchEntreprise: () => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

const ROLE_ALIASES: Record<string, string> = {
  admin: "SUPER_ADMIN",
  accountant: "DAF",
  hr_manager: "RH",
  sales: "COMMERCIAL",
  employee: "EMPLOYE",
  viewer: "VIEWER",
  pdg_super_admin: "PDG_SUPER_ADMIN",
  charge_mission: "CHARGE_MISSION",
  daf: "DAF",
  charge_finance: "CHARGE_FINANCE",
  marketing: "MARKETING",
  project_manager: "PROJECT_MANAGER",
  teleconseillere: "TELECONSEILLERE",
  rh: "RH",
  archiviste: "ARCHIVISTE",
  securite: "SECURITE",
  magasinier: "MAGASINIER",
  achats: "ACHATS",
  operations_tech: "OPERATIONS_TECH",
  architecte: "ARCHITECTE",
  chef_projet_ext: "CHEF_PROJET_EXT",
};

function normalizeRole(role: string | undefined): string {
  if (!role) return "VIEWER";
  return ROLE_ALIASES[role] ?? role;
}

/* ── Provider ──────────────────────────────────────── */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [company, setCompany] = useState<Company | null>(() => {
    const stored = localStorage.getItem("company");
    return stored ? JSON.parse(stored) : null;
  });
  const [entreprises, setEntreprises] = useState<EntrepriseInfo[]>([]);
  const [activeEntreprise, setActiveEntreprise] = useState<EntrepriseInfo | null>(() => {
    const stored = localStorage.getItem("active_entreprise");
    return stored ? JSON.parse(stored) : null;
  });
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [token, setToken] = useState<string | null>(localStorage.getItem("access_token"));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setUser(null);
    setCompany(null);
    setEntreprises([]);
    setActiveEntreprise(null);
    setMenuItems([]);
    setToken(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("company");
    localStorage.removeItem("active_entreprise");
    localStorage.removeItem("entreprises");
  }, []);

  // Fetch current user + menu on mount / token change
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    Promise.all([
      api.get<User>("/auth/me"),
      api.get<MenuItem[]>("/auth/me/menu"),
      api.get("/auth/me/company"),
    ])
      .then(([userRes, menuRes, companyRes]) => {
        setUser({ ...userRes.data, role: normalizeRole(userRes.data.role) });
        setMenuItems(menuRes.data);
        setCompany(companyRes.data);
        localStorage.setItem("company", JSON.stringify(companyRes.data));
        // Restore entreprises from localStorage
        const storedEnts = localStorage.getItem("entreprises");
        if (storedEnts) setEntreprises(JSON.parse(storedEnts));
      })
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [token, logout]);

  const login = async (email: string, password: string): Promise<{ needsSelection: boolean }> => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    if (data.company) {
      localStorage.setItem("company", JSON.stringify(data.company));
      setCompany(data.company);
    }

    const ents: EntrepriseInfo[] = data.entreprises || [];
    setEntreprises(ents);
    localStorage.setItem("entreprises", JSON.stringify(ents));

    if (data.active_entreprise) {
      setActiveEntreprise(data.active_entreprise);
      localStorage.setItem("active_entreprise", JSON.stringify(data.active_entreprise));
    }

    setToken(data.access_token);
    setUser({ ...data.user, role: normalizeRole(data.user?.role) });

    // If only 1 entreprise, it's auto-selected → no selection needed
    return { needsSelection: ents.length > 1 && !data.active_entreprise };
  };

  const selectEntreprise = async (entrepriseId: string) => {
    const { data } = await api.post("/auth/select-entreprise", {
      entreprise_id: entrepriseId,
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    setToken(data.access_token);

    if (data.active_entreprise) {
      setActiveEntreprise(data.active_entreprise);
      localStorage.setItem("active_entreprise", JSON.stringify(data.active_entreprise));
    }
    if (data.user) {
      setUser({ ...data.user, role: normalizeRole(data.user.role) });
    }
  };

  const switchEntreprise = useCallback(() => {
    // Clear active entreprise so the login page shows the chooser
    setActiveEntreprise(null);
    localStorage.removeItem("active_entreprise");
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user, company, entreprises, activeEntreprise, menuItems,
        token, loading, login, selectEntreprise, switchEntreprise,
        logout, isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

/* ── Hook ──────────────────────────────────────────── */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
