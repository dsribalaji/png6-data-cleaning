import { format as dateFnsFormat, isValid } from "date-fns";

/**
 * Utility to conditionally concatenate class names together.
 */
export function cx(...classes: (string | boolean | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/**
 * Safely converts an input into a valid Date object or null if invalid.
 */
function toDate(input: Date | string | number | null | undefined): Date | null {
  if (input === null || input === undefined || input === "") return null;
  const d = input instanceof Date ? input : new Date(input);
  return isValid(d) ? d : null;
}

/**
 * Format date in dd-MM-yyyy (e.g. 30-09-2026) per PRD / OQ-22.
 */
export function formatDate(input: Date | string | number | null | undefined): string {
  const d = toDate(input);
  if (!d) return "—";
  return dateFnsFormat(d, "dd-MM-yyyy");
}

/**
 * Format datetime in user's local timezone: dd-MM-yyyy HH:mm (24h).
 */
export function formatDateTime(input: Date | string | number | null | undefined): string {
  const d = toDate(input);
  if (!d) return "—";
  return dateFnsFormat(d, "dd-MM-yyyy HH:mm");
}

/**
 * Format audit timestamp in UTC: dd-MM-yyyy HH:mm:ss UTC (PRD Section 7 / OQ-22).
 */
export function formatUtc(
  input: Date | string | number | null | undefined,
  includeSeconds = true
): string {
  const d = toDate(input);
  if (!d) return "—";

  const pad = (n: number) => n.toString().padStart(2, "0");
  const day = pad(d.getUTCDate());
  const month = pad(d.getUTCMonth() + 1);
  const year = d.getUTCFullYear();
  const hours = pad(d.getUTCHours());
  const minutes = pad(d.getUTCMinutes());
  const seconds = pad(d.getUTCSeconds());

  const timeStr = includeSeconds
    ? `${hours}:${minutes}:${seconds}`
    : `${hours}:${minutes}`;

  return `${day}-${month}-${year} ${timeStr} UTC`;
}

/**
 * Format integer with thousands separators (e.g. 154,292).
 */
export function formatInt(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return "0";
  return new Intl.NumberFormat("en-US").format(val);
}

/**
 * Format percentage (e.g. 0.4% or 95%).
 * Handles both fractional values (if assumeDecimal) and percentage values directly.
 */
export function formatPct(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined || isNaN(val)) return "0%";
  return `${Number(val.toFixed(decimals))}%`;
}

/**
 * Format monetary or currency value.
 */
export function formatMoney(
  val: number | null | undefined,
  currency = "USD"
): string {
  if (val === null || val === undefined || isNaN(val)) return "$0.00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
}
