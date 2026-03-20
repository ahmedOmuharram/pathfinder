export const normalizeRecordType = (value: string | null | undefined) =>
  value != null && value !== "" ? value.trim() : value;
