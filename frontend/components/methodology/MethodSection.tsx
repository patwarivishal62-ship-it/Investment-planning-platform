"use client";

import { useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";

/**
 * Methodology entry: plain-language summary always visible, technical detail in
 * a progressive-disclosure panel (spec section 50).
 */
export function MethodSection({
  title,
  plain,
  technical,
  formula,
}: {
  title: string;
  plain: string;
  technical: string[];
  formula?: string[];
}) {
  const [open, setOpen] = useState(false);
  const panelId = `method-${title.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <Card>
      <CardBody>
        <h2 className="text-base font-semibold tracking-tight text-ink">{title}</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{plain}</p>

        {formula?.length ? (
          <div className="mt-3 space-y-1">
            {formula.map((line) => (
              <p
                key={line}
                className="overflow-x-auto rounded-md bg-stone-50 px-3 py-1.5 font-mono text-xs text-ink"
              >
                {line}
              </p>
            ))}
          </div>
        ) : null}

        <button
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls={panelId}
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent-700 hover:text-accent-800"
        >
          {open ? "Hide technical detail" : "Show technical detail"}
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            fill="currentColor"
            aria-hidden
            className={open ? "rotate-180 transition-transform" : "transition-transform"}
          >
            <path d="M8 11 3 6h10z" />
          </svg>
        </button>

        {open ? (
          <div id={panelId} className="mt-3 border-t border-line pt-3">
            <ul className="space-y-2">
              {technical.map((item) => (
                <li key={item.slice(0, 40)} className="flex gap-2 text-sm leading-relaxed text-ink-muted">
                  <span aria-hidden className="select-none text-ink-subtle">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
