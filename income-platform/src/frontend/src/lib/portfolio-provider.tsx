"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import type { Portfolio } from "./types";
import { API_BASE_URL } from "./config";

type Theme = "dark" | "light";

interface PortfolioContextValue {
  portfolios: Portfolio[];
  activePortfolio: Portfolio | null;
  setActiveId: (id: string) => void;
  addPortfolio: (p: Omit<Portfolio, "id">) => Promise<void>;
  updatePortfolio: (id: string, updates: Partial<Portfolio>) => Promise<void>;
  deletePortfolio: (id: string) => Promise<void>;
  reloadPortfolios: () => Promise<void>;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
}

const PortfolioContext = createContext<PortfolioContextValue>({
  portfolios: [],
  activePortfolio: null,
  setActiveId: () => {},
  addPortfolio: async () => {},
  updatePortfolio: async () => {},
  deletePortfolio: async () => {},
  reloadPortfolios: async () => {},
  sidebarCollapsed: false,
  toggleSidebar: () => {},
  theme: "dark",
  setTheme: () => {},
});

async function fetchPortfoliosFromAPI(): Promise<Portfolio[]> {
  const res = await fetch(`${API_BASE_URL}/api/portfolios`, { credentials: "include" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json() as Portfolio[];
  return data;
}

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activeId, setActiveIdState] = useState<string>("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [theme, setThemeState] = useState<Theme>("dark");

  const reloadPortfolios = async () => {
    try {
      const remote = await fetchPortfoliosFromAPI();
      // API success — always authoritative, even if empty
      setPortfolios(remote);
      if (remote.length > 0) {
        setActiveIdState((prev) => {
          if (prev && remote.find((p) => p.id === prev)) return prev;
          const savedId = typeof window !== "undefined" ? localStorage.getItem("activePortfolioId") : null;
          if (savedId && remote.find((p) => p.id === savedId)) return savedId;
          return remote[0].id;
        });
      } else {
        setActiveIdState("");
      }
      return;
    } catch { /* fall through to localStorage */ }

    // Fallback: localStorage
    try {
      const saved = typeof window !== "undefined" ? localStorage.getItem("portfolios") : null;
      if (saved) {
        const parsed = JSON.parse(saved) as Portfolio[];
        if (parsed.length > 0) {
          setPortfolios(parsed);
          return;
        }
      }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    // Restore UI preferences
    const savedId        = localStorage.getItem("activePortfolioId");
    const savedCollapsed = localStorage.getItem("sidebarCollapsed");
    const savedTheme     = localStorage.getItem("theme") as Theme | null;

    if (savedId)              setActiveIdState(savedId);
    if (savedCollapsed === "true") setSidebarCollapsed(true);
    if (savedTheme) {
      setThemeState(savedTheme);
      document.documentElement.className = savedTheme;
    }

    reloadPortfolios();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setActiveId = (id: string) => {
    setActiveIdState(id);
    localStorage.setItem("activePortfolioId", id);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      localStorage.setItem("sidebarCollapsed", String(!prev));
      return !prev;
    });
  };

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem("theme", t);
    document.documentElement.className = t;
  };

  const addPortfolio = async (p: Omit<Portfolio, "id">) => {
    await fetch(`${API_BASE_URL}/api/portfolios`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: p.name, account_type: p.account_type, broker: p.broker }),
    });
    await reloadPortfolios();
  };

  const updatePortfolio = async (id: string, updates: Partial<Portfolio>) => {
    // Optimistic local update
    setPortfolios((prev) => prev.map((p) => (p.id === id ? { ...p, ...updates } : p)));
    await fetch(`${API_BASE_URL}/api/portfolios/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: updates.name, account_type: updates.account_type, broker: updates.broker }),
    });
  };

  const deletePortfolio = async (id: string) => {
    await fetch(`${API_BASE_URL}/api/portfolios/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    await reloadPortfolios();
  };

  const activePortfolio = portfolios.find((p) => p.id === activeId) || portfolios[0] || null;

  return (
    <PortfolioContext.Provider value={{
      portfolios, activePortfolio, setActiveId,
      addPortfolio, updatePortfolio, deletePortfolio,
      reloadPortfolios,
      sidebarCollapsed, toggleSidebar,
      theme, setTheme,
    }}>
      {children}
    </PortfolioContext.Provider>
  );
}

export function usePortfolio() {
  return useContext(PortfolioContext);
}
