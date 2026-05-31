import { z } from "zod";

export const OntologyTermSchema = z.object({
  term: z.string(),
  display: z.string().optional(),
  type: z.enum(["string", "number", "date", "longitude", "multiFilter"]).optional(),
  parent: z.string().optional(),
  values: z.array(z.union([z.string(), z.null()])).optional(),
  isRange: z.boolean().optional(),
  precision: z.number().optional(),
});

export const OntologySchema = z.array(OntologyTermSchema);

export type OntologyTerm = z.infer<typeof OntologyTermSchema>;
