import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { useSettingsStore } from "@/state/useSettingsStore";

export function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="flex-shrink-0 size-7 rounded-full bg-primary flex items-center justify-center text-[11px] font-bold text-primary-foreground">
      {initials}
    </div>
  );
}

export function AssistantAvatar({ modelId }: { modelId?: string }) {
  const catalog = useSettingsStore((s) => s.modelCatalog);
  const entry = catalog.find((m) => m.id === modelId);
  const provider = entry?.provider ?? "openai";
  return (
    <div className="flex-shrink-0 size-7 rounded-md bg-muted flex items-center justify-center">
      <ProviderIcon provider={provider} size={16} />
    </div>
  );
}
