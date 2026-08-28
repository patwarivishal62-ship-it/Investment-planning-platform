import type { Metadata } from "next";
import "./globals.css";
import { AppProvider } from "@/lib/store";
import { TopNav } from "@/components/layout/TopNav";
import { Footer } from "@/components/layout/Footer";
import { DemoBanner } from "@/components/layout/DemoBanner";

export const metadata: Metadata = {
  title: "Portfolio Quant — Multi-asset investment plan generator",
  description:
    "Quantitative portfolio analysis and educational decision support. Compare statistically optimised multi-asset portfolios built on Indian market data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN">
      <body className="min-h-screen">
        <AppProvider>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:shadow-raised"
          >
            Skip to content
          </a>
          <DemoBanner />
          <TopNav />
          <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
            {children}
          </main>
          <Footer />
        </AppProvider>
      </body>
    </html>
  );
}
