"use client";

import { usePortfolio } from "@/lib/portfolio-context";
import { cn } from "@/lib/utils";

export function MainContent({ children }: { children: React.ReactNode }) {
  const { sidebarCollapsed } = usePortfolio();

  return (
    <main
      className={cn(
        "flex-1 p-6 transition-all duration-200 overflow-x-hidden min-w-0",
        sidebarCollapsed ? "ml-16" : "ml-60"
      )}
    >
      {children}
    </main>
  );
}
