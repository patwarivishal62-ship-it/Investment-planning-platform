/** Presentation helpers. All formatting lives here; no page formats numbers inline. */

/** Indian numbering: ₹10,00,000 (lakh / crore grouping). */
export function formatINR(
  value: number | null | undefined,
  options: { compact?: boolean; decimals?: number } = {},
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const { compact = false, decimals } = options;
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (compact) {
    if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(decimals ?? 2)} Cr`;
    if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(decimals ?? 2)} L`;
    if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(decimals ?? 1)}K`;
    return `${sign}₹${abs.toFixed(decimals ?? 0)}`;
  }

  const rounded = decimals !== undefined ? abs.toFixed(decimals) : Math.round(abs).toString();
  return `${sign}₹${groupIndian(rounded)}`;
}

/** Group digits 2-2-3 as used in the Indian numbering system. */
export function groupIndian(digits: string): string {
  const [whole, fraction] = digits.split(".");
  if (whole.length <= 3) return fraction ? `${whole}.${fraction}` : whole;
  const lastThree = whole.slice(-3);
  const rest = whole.slice(0, -3);
  const grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${grouped},${lastThree}${fraction ? `.${fraction}` : ""}`;
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatSignedPercent(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(decimals);
}

export function formatScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${Math.round(value)}/100`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const CLASS_LABELS: Record<string, string> = {
  equity: "Equity",
  bond: "Fixed Income",
  gold: "Gold",
  silver: "Silver",
  commodity: "Commodity",
  international_equity: "International Equity",
  reit: "REIT / InvIT",
  cash: "Cash",
};

export function classLabel(assetClass: string): string {
  return CLASS_LABELS[assetClass] ?? assetClass.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Muted, ordered palette for asset classes -- deliberately non-neon. */
export const ASSET_CLASS_COLORS: Record<string, string> = {
  equity: "#4338CA",
  international_equity: "#0E7490",
  bond: "#0F766E",
  gold: "#B45309",
  silver: "#64748B",
  commodity: "#7C3AED",
  reit: "#BE185D",
  cash: "#94A3B8",
  other: "#A8A29E",
};

/** A stable, restrained chart palette for per-asset series. */
export const SERIES_COLORS = [
  "#4338CA",
  "#0F766E",
  "#B45309",
  "#0E7490",
  "#7C3AED",
  "#BE185D",
  "#4D7C0F",
  "#64748B",
  "#A16207",
  "#334155",
];

export function colorForIndex(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

export function riskBandTone(band: string): string {
  switch (band) {
    case "Very Low":
      return "bg-slate-100 text-slate-700 border-slate-200";
    case "Low":
      return "bg-teal-50 text-teal-800 border-teal-200";
    case "Moderate":
      return "bg-indigo-50 text-indigo-800 border-indigo-200";
    case "High":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "Very High":
      return "bg-rose-50 text-rose-800 border-rose-200";
    default:
      return "bg-stone-100 text-stone-700 border-stone-200";
  }
}
