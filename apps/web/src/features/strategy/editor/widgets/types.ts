import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { VocabOption, VocabNode } from "@/lib/utils/vocab";

/** Props for form-aware parameter widgets. Widgets self-serve via useFormContext(). */
export type ParamWidgetProps = {
  /** WDK parameter specification */
  spec: ParamSpec;
  /** Form field name (= WDK parameter name) */
  name: string;
  /** Flat vocabulary options */
  options: VocabOption[];
  /** Hierarchical tree (null if flat) */
  vocabTree: VocabNode[] | null;
};
