/**
 * Shared number formatting utilities.
 *
 * Eliminates DRY violations across chat, settings, and model catalog UI.
 */

/**
 * Format a number with K/M abbreviation (1 decimal place).
 *
 * Used for token counts and general large-number display.
 * - 1_500_000 -> "1.5M"
 * - 1_500     -> "1.5k"
 * - 42        -> "42"
 */
export function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/**
 * Format a number with K/M abbreviation, trimming unnecessary decimals.
 *
 * Used for context window sizes where clean numbers are preferred.
 * - 128_000   -> "128K"
 * - 1_500_000 -> "1.5M"
 * - 1_000_000 -> "1M"
 */
export function formatCompactClean(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`;
  return String(n);
}

/**
 * Format a number with K/M abbreviation (0 decimal places for K).
 *
 * Used for compact display in tight spaces like table placeholders.
 * - 128_000   -> "128k"
 * - 1_500_000 -> "1.5M"
 * - 42        -> "42"
 */
export function formatCompactShort(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

/**
 * Format a USD cost with appropriate precision.
 *
 * - 0 or null -> "<$0.01" is NOT shown; returns "<$0.01" only for tiny nonzero
 * - < 0.01    -> "<$0.01"
 * - >= 0.01   -> "$1.50"
 */
export function formatCost(n: number): string {
  if (n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}

/**
 * Format a price per million tokens.
 *
 * - 0    -> "Free"
 * - tiny -> "<$0.01"
 * - else -> "$1.50"
 */
export function formatPrice(n: number): string {
  if (n === 0) return "Free";
  if (n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}
