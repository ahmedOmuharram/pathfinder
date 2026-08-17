/** Whether a gene set has a source strategy it can be taken from again. */
export function canRetakeGeneSet(set: { wdkStrategyId?: number | null }): boolean {
  return set.wdkStrategyId != null;
}
