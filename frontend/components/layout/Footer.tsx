import Link from "next/link";
import { SHORT_DISCLAIMER } from "@/components/ui/Disclaimer";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:justify-between">
          <div className="max-w-xl">
            <p className="text-sm font-semibold text-ink">Portfolio Quant</p>
            <p className="mt-2 text-xs leading-relaxed text-ink-subtle">{SHORT_DISCLAIMER}</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-muted">
            <Link href="/methodology" className="hover:text-ink">Methodology</Link>
            <Link href="/disclaimer" className="hover:text-ink">Disclaimer</Link>
            <Link href="/assets" className="hover:text-ink">Asset universe</Link>
            <Link href="/settings" className="hover:text-ink">Data settings</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
