"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  TrendingUp,
  Bell,
  FileCheck,
  Calendar,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  ScanLine,
  Zap,
  PieChart,
  BarChart3,
  Leaf,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PortfolioSwitcher } from "./portfolio-switcher";
import { usePortfolio } from "@/lib/portfolio-context";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/projection", label: "Projection", icon: TrendingUp },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/proposals", label: "Proposals", icon: FileCheck },
  { href: "/scanner",           label: "Scanner",             icon: ScanLine },
  { href: "/stress-test",       label: "Stress Test",         icon: Zap },
  { href: "/income-projection", label: "Income Projection",   icon: PieChart },
  { href: "/vulnerability",     label: "Vulnerability",       icon: BarChart3 },
  { href: "/tax",               label: "Tax Optimizer",       icon: Leaf },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = usePortfolio();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border bg-sidebar transition-all duration-200",
        sidebarCollapsed ? "w-16" : "w-60"
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center border-b border-border px-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-sapphire">
          <span className="text-xs font-bold text-white">IF</span>
        </div>
        {!sidebarCollapsed && (
          <span className="ml-2 text-sm font-semibold tracking-tight">Income Fortress</span>
        )}
        <button
          onClick={toggleSidebar}
          className={cn(
            "ml-auto flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors",
            sidebarCollapsed && "ml-0 mt-0"
          )}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Portfolio Switcher */}
      {!sidebarCollapsed && (
        <div className="px-3 py-3">
          <PortfolioSwitcher />
        </div>
      )}

      {/* Nav */}
      <nav className={cn("flex-1 space-y-0.5", sidebarCollapsed ? "px-2 pt-3" : "px-3")}>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              title={sidebarCollapsed ? label : undefined}
              className={cn(
                "flex items-center rounded-md transition-colors",
                sidebarCollapsed
                  ? "justify-center px-0 py-2.5"
                  : "gap-3 px-3 py-2 text-sm",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {!sidebarCollapsed && (
        <div className="border-t border-border px-5 py-3">
          <p className="text-[11px] text-muted-foreground">Income Fortress v1.0</p>
        </div>
      )}
    </aside>
  );
}
