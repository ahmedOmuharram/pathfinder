import { Globe, Loader2, Database, BookOpen } from "lucide-react";

const TOOL_ICONS: Record<string, typeof Globe> = {
  web_search: Globe,
  literature_search: BookOpen,
  search_for_searches: Database,
  list_searches: Database,
  get_search_parameters: Database,
  get_record_types: Database,
  lookup_genes: Database,
};

export function ToolIndicator({ name, active }: { name: string; active: boolean }) {
  const Icon = TOOL_ICONS[name] ?? Database;
  const label = name.replace(/_/g, " ");
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-medium ${
        active ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"
      }`}
    >
      <Icon className="h-2.5 w-2.5" />
      {active ? (
        <>
          <Loader2 className="h-2.5 w-2.5 animate-spin" />
          {label}
        </>
      ) : (
        label
      )}
    </span>
  );
}
