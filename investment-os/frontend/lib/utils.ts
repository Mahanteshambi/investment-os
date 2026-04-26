import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { formatDistanceToNow } from "date-fns"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(...inputs))
}

/** Format number as Indian rupee string: ₹1,48,234 */
export function formatINR(value: number): string {
  if (value === null || value === undefined || isNaN(value)) return "₹0"
  const absVal = Math.abs(value)
  const sign = value < 0 ? "-" : ""
  const formatted = absVal.toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
  return `${sign}₹${formatted}`
}

/** Format as percentage with sign and fixed decimals */
export function formatPct(value: number, decimals = 2): string {
  if (value === null || value === undefined || isNaN(value)) return "0.00%"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(decimals)}%`
}

/** Relative time from ISO string */
export function relativeTime(isoString: string | null): string {
  if (!isoString) return "Never"
  try {
    return formatDistanceToNow(new Date(isoString), { addSuffix: true })
  } catch {
    return "Unknown"
  }
}

/** Compact INR for large values: ₹1.48L, ₹2.3Cr */
export function formatINRCompact(value: number): string {
  if (value >= 1_00_00_000) return `₹${(value / 1_00_00_000).toFixed(2)}Cr`
  if (value >= 1_00_000) return `₹${(value / 1_00_000).toFixed(2)}L`
  return formatINR(value)
}
