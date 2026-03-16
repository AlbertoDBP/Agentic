"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import type { Portfolio } from "./types";

const MOCK_PORTFOLIOS: Portfolio[] = [
  { id: "p1", name: "Income Fortress", account_type: "Taxable", broker: "Schwab", position_count: 70, total_value: 612000, cash_balance: 18450 },
  { id: "p2", name: "Roth IRA", account_type: "Roth IRA", broker: "Fidelity", position_count: 15, total_value: 85000, cash_balance: 3200 },
  { id: "p3", name: "401(k)", account_type: "401(k)", broker: "Vanguard", position_count: 8, total_value: 142000, cash_balance: 5800 },
];

type Theme = "dark" | "light";

interface PortfolioContextValue {
  portfolios: Portfolio[];
  activePortfolio: Portfolio | null;
  setActiveId: (id: string) => void;
  addPortfolio: (p: Omit<Portfolio, "id">) => void;
  updatePortfolio: (id: string, updates: Partial<Portfolio>) => void;
  deletePortfolio: (id: string) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
}

const PortfolioContext = createContext<PortfolioContextValue>({
  portfolios: [],
  activePortfolio: null,
  setActiveId: () => {},
  addPortfolio: () => {},
  updatePortfolio: () => {},
  deletePortfolio: () => {},
  sidebarCollapsed: false,
  toggleSidebar: () => {},
  theme: "dark",
  setTheme: () => {},
});

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>(MOCK_PORTFOLIOS);
  const [activeId, setActiveIdState] = useState<string>("p1");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const savedId = localStorage.getItem("activePortfolioId");
    if (savedId) setActiveIdState(savedId);
    const savedCollapsed = localStorage.getItem("sidebarCollapsed");
    if (savedCollapsed === "true") setSidebarCollapsed(true);
    const savedTheme = localStorage.getItem("theme") as Theme | null;
    if (savedTheme) {
      setThemeState(savedTheme);
      document.documentElement.className = savedTheme;
    }
    const savedPortfolios = localStorage.getItem("portfolios");
    if (savedPortfolios) {
      try { setPortfolios(JSON.parse(savedPortfolios)); } catch { /* ignore */ }
    }
  }, []);

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

  const persistPortfolios = (next: Portfolio[]) => {
    setPortfolios(next);
    localStorage.setItem("portfolios", JSON.stringify(next));
  };

  const addPortfolio = (p: Omit<Portfolio, "id">) => {
    const newP: Portfolio = { ...p, id: `p${Date.now()}` };
    persistPortfolios([...portfolios, newP]);
  };

  const updatePortfolio = (id: string, updates: Partial<Portfolio>) => {
    persistPortfolios(portfolios.map((p) => (p.id === id ? { ...p, ...updates } : p)));
  };

  const deletePortfolio = (id: string) => {
    const next = portfolios.filter((p) => p.id !== id);
    persistPortfolios(next);
    if (activeId === id && next.length > 0) setActiveId(next[0].id);
  };

  const activePortfolio = portfolios.find((p) => p.id === activeId) || portfolios[0] || null;

  return (
    <PortfolioContext.Provider value={{
      portfolios, activePortfolio, setActiveId,
      addPortfolio, updatePortfolio, deletePortfolio,
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
