"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useDataStatus } from "@/lib/hooks/useDataStatus";
import { DataStatusIndicator } from "./DataStatusIndicator";

const LINKS = [
  { href: "/dashboard", label: "Plans" },
  { href: "/analytics", label: "Analytics" },
  { href: "/optimizer", label: "Optimizer" },
  { href: "/backtest", label: "Backtest" },
  { href: "/stress-test", label: "Scenarios" },
  { href: "/monte-carlo", label: "Simulation" },
];

export function TopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const status = useDataStatus();
  const isDemo = status?.isDemo ?? false;

  useEffect(() => setOpen(false), [pathname]);

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded-md bg-accent-700 text-[0.7rem] font-bold text-white"
          >
            QP
          </span>
          <span className="hidden text-sm font-semibold tracking-tight text-ink sm:block">
            Portfolio<span className="text-ink-subtle"> Quant</span>
          </span>
        </Link>

        <nav aria-label="Main" className="hidden flex-1 items-center gap-1 lg:flex">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-sm transition-colors",
                  active ? "bg-stone-100 font-medium text-ink" : "text-ink-muted hover:text-ink",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <DataStatusIndicator />
          <Link
            href="/settings"
            className="hidden rounded-md px-2.5 py-1.5 text-sm text-ink-muted transition-colors hover:text-ink sm:block"
          >
            Settings
          </Link>
          <button
            className="grid h-8 w-8 place-items-center rounded-md border border-line bg-surface text-ink-muted lg:hidden"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-label="Toggle navigation"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              {open ? (
                <path d="M4.3 3.3 8 7l3.7-3.7 1 1L9 8l3.7 3.7-1 1L8 9l-3.7 3.7-1-1L7 8 3.3 4.3z" />
              ) : (
                <path d="M2 4h12v1.5H2zm0 4h12v1.5H2zm0 4h12v1.5H2z" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {open ? (
        <nav aria-label="Mobile" className="border-t border-line bg-surface px-4 py-3 lg:hidden">
          <ul className="grid gap-1">
            {[...LINKS, { href: "/assets", label: "Asset Universe" }, { href: "/onboarding", label: "Build a Plan" }, { href: "/settings", label: "Settings" }, { href: "/methodology", label: "Methodology" }].map(
              (link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className={cn(
                      "block rounded-md px-3 py-2 text-sm",
                      pathname === link.href ? "bg-stone-100 font-medium text-ink" : "text-ink-muted",
                    )}
                  >
                    {link.label}
                  </Link>
                </li>
              ),
            )}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
