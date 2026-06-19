const HEADER = /^gene.?id$/i;

/** Parse gene IDs from a delimited file (CSV/TSV/plain text): one record per
 *  line, the gene ID is the first column (split on comma or tab). Strips a
 *  gene_id-style header row, trims, dedupes, and preserves first-occurrence
 *  order. For free-form pasted lists where commas separate IDs, use
 *  {@link parseGeneIds} instead. */
export function parseGeneCsv(text: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const first = (line.split(/[,\t]/)[0] ?? "").trim();
    if (first === "" || HEADER.test(first) || seen.has(first)) continue;
    seen.add(first);
    result.push(first);
  }
  return result;
}
