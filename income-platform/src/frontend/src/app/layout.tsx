import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryProvider } from "@/lib/query-provider";
import { PortfolioProvider } from "@/lib/portfolio-context";
import { Sidebar } from "@/components/sidebar";
import { MainContent } from "@/components/main-content";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Income Fortress",
  description: "Investment income monitoring dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrains.variable} antialiased`}>
        <QueryProvider>
          <PortfolioProvider>
            <TooltipProvider>
              <div className="flex min-h-screen">
                <Sidebar />
                <MainContent>{children}</MainContent>
              </div>
            </TooltipProvider>
          </PortfolioProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
