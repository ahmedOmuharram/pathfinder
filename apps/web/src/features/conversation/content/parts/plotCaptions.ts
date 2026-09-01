/** The one sentence printed under a plot. The model's sentence leads and the
 * study and the numbers follow it in parentheses; without a model sentence the
 * facts are the caption. */
export function plotCaption(
  modelCaption: string,
  study: string,
  numbers: string,
): string {
  const facts = study.length > 0 ? `${study} - ${numbers}` : numbers;
  const written = modelCaption.trim().replace(/\.+$/, "");
  return written.length > 0 ? `${written} (${facts}).` : `${facts}.`;
}
