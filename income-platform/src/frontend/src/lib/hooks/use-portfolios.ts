"use client";
import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/lib/config";
import type { PortfolioListItem, PortfolioSummary } from "@/lib/types";

const authHeader = () => ({
  Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : ""}`,
});

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeader() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/** All portfolios with aggregate KPIs. */
export function usePortfolios() {
  return useQuery<PortfolioListItem[]>({
    queryKey: ["portfolios"],
    queryFn: () => apiFetch("/broker/portfolios"),
    staleTime: 30_000,
  });
}

/** Full summary for a single portfolio. */
export function usePortfolioSummary(portfolioId: string | undefined) {
  return useQuery<PortfolioSummary>({
    queryKey: ["portfolio-summary", portfolioId],
    queryFn: () => apiFetch(`/broker/portfolios/${portfolioId}/summary`),
    enabled: !!portfolioId,
    staleTime: 30_000,
  });
}
