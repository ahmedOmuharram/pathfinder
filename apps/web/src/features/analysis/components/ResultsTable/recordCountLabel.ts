/**
 * Label a result count with the unit WDK actually counted.
 *
 * A gene set of 438 genes returns 448 transcript records, because one gene
 * can have several transcripts. Rendering both as bare "records" vs "genes"
 * reads as a data inconsistency; naming the unit explains it.
 */
export function recordCountLabel(count: number, recordType: string | null): string {
  const formatted = count.toLocaleString();
  if (recordType == null || recordType === "") {
    return `${formatted} records`;
  }
  const noun = recordType.replace(/_/g, " ");
  return `${formatted} ${count === 1 ? noun : `${noun}s`}`;
}
