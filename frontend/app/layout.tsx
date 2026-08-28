import type { Metadata } from "next";
import "./globals.css";
import { AppProvider } from "@/lib/store";
import { DataStatusProvider } from "@/lib/hooks/useDataStatus";
import { TopNav } from "@/components/layout/TopNav";
import { Footer } from "@/components/layout/Footer";
import { DemoBanner } from "@/components/layout/DemoBanner";
import type { DataStatus } from "@/types";

/**
 * Seed data provenance on the server so the very first paint already says
 * whether the numbers are synthetic. Revalidated periodically, and refreshed
 * again on the client, so a prerendered page cannot bake in a stale mode.
 * A backend outage must never break rendering -- we fall back to client fetch.
 */
async function getDataStatus(): Promise<DataStatus | null> {
  try {
    const base = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${base}/api/data/status`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return null;
    return (await response.json()) as DataStatus;
  } catch {
    return null;
  }
}

export const metadata: Metadata = {
  title: "Portfolio Quant — Multi-asset investment plan generator",
  description:
    "Quantitative portfolio analysis and educational decision support. Compare statistically optimised multi-asset portfolios built on Indian market data.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialStatus = await getDataStatus();
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
          <DataStatusProvider initialStatus={initialStatus}>
            <DemoBanner />
            <TopNav />
            <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
              {children}
            </main>
            <Footer />
          </DataStatusProvider>
        </AppProvider>
      </body>
    </html>
  );
}
