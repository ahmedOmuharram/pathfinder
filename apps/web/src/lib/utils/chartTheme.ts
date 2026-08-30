import { readChartTokens } from "@/lib/components/charts/chartTheme";
import { UNRESOLVED_SERIES_COLOR } from "@/lib/components/charts/unresolved";

/** Chart colors under the role names a Recharts chart reaches for. */
export interface ChartRoleColors {
  positive: string;
  negative: string;
  primary: string;
  secondary: string;
  warning: string;
  destructive: string;
  purple: string;
  cyan: string;
}

export function readChartRoleColors(): ChartRoleColors {
  const { series, positive, negative } = readChartTokens();
  const at = (index: number): string => series[index] ?? UNRESOLVED_SERIES_COLOR;
  return {
    positive,
    negative,
    primary: at(0),
    secondary: at(1),
    warning: at(2),
    destructive: at(3),
    purple: at(4),
    cyan: at(5),
  };
}
