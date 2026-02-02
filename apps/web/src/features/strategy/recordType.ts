export const normalizeRecordType = (value: string | null | undefined) =>
  value ? value.trim() : value;

export const toApiRecordType = (value: string | null | undefined) =>
  value === "gene" ? "transcript" : value;
