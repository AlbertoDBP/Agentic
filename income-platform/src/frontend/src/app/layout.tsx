import type { Metadata } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryProvider } from "@/lib/query-provider";
import { PortfolioProvider } from "@/lib/portfolio-context";
import { Sidebar } from "@/components/sidebar";
import { MainContent } from "@/components/main-content";
import { ChatWidget } from "@/components/chat/ChatWidget";
import "./globals.css";

// HK Grotesk — IMC brand font (published on Google Fonts as Hanken Grotesk)
const hankenGrotesk = Hanken_Grotesk({
  variable: "--font-hk-grotesk",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
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
      <body className={`${hankenGrotesk.variable} ${jetbrains.variable} antialiased`}>
        <QueryProvider>
          <PortfolioProvider>
            <TooltipProvider>
              <div className="flex min-h-screen">
                <Sidebar />
                <MainContent>{children}</MainContent>
              </div>
              <ChatWidget />
            </TooltipProvider>
          </PortfolioProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
