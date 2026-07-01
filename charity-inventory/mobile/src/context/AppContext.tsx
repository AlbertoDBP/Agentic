import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api, setToken } from '../api/client';
import type { AuthUser, Center, ScanContext } from '../types';

interface AppState {
  user: AuthUser | null;
  centers: Center[];
  selectedCenter: Center | null;
  sessionId: number | null;
  scanContext: ScanContext | null;
  loading: boolean;
  setSelectedCenter: (center: Center | null) => void;
  setSessionId: (sessionId: number | null) => void;
  setScanContext: (context: ScanContext | null) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshCenters: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [centers, setCenters] = useState<Center[]>([]);
  const [selectedCenter, setSelectedCenter] = useState<Center | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [scanContext, setScanContext] = useState<ScanContext | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshCenters = async () => {
    const result = await api.centers();
    setCenters(result.centers);
  };

  const bootstrap = async () => {
    setLoading(true);
    try {
      const result = await api.me();
      setUser(result.user);
      await refreshCenters();
    } catch {
      setUser(null);
      await setToken(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    bootstrap();
  }, []);

  const login = async (email: string, password: string) => {
    const result = await api.login(email, password);
    await setToken(result.token);
    setUser(result.user);
    await refreshCenters();
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Token may already be invalid; still clear local state.
    }
    await setToken(null);
    setUser(null);
    setCenters([]);
    setSelectedCenter(null);
    setSessionId(null);
    setScanContext(null);
  };

  const value = useMemo(
    () => ({
      user,
      centers,
      selectedCenter,
      sessionId,
      scanContext,
      loading,
      setSelectedCenter,
      setSessionId,
      setScanContext,
      login,
      logout,
      refreshCenters,
      bootstrap,
    }),
    [user, centers, selectedCenter, sessionId, scanContext, loading]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
