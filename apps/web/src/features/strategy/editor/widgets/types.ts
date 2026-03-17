import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { VocabOption, VocabNode } from "@/lib/utils/vocab";

export type ParamWidgetProps = {
  spec: ParamSpec;
  /** Single-pick value */
  value: string | undefined;
  /** Whether this is a multi-pick param */
  multi: boolean;
  /** Multi-pick values (coerced to string[]) */
  multiValue: string[];
  /** Flat vocabulary options */
  options: VocabOption[];
  /** Hierarchical tree (null if flat) */
  vocabTree: VocabNode[] | null;
  /** Callback for single-pick value change */
  onChangeSingle: (value: string) => void;
  /** Callback for multi-pick value change */
  onChangeMulti: (value: string[]) => void;
  /** Optional CSS class for field border styling */
  fieldBorderClass?: string;
};
