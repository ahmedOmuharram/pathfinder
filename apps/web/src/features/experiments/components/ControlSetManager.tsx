import { useCallback, useEffect, useState } from "react";
import type { ControlSet, ControlSetSource } from "@pathfinder/shared";
import {
  Database,
  Plus,
  Tag,
  Trash2,
  BookOpen,
  FlaskConical,
  Server,
  HelpCircle,
  Check,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { Input } from "@/lib/components/ui/Input";
import { listControlSets, createControlSet, deleteControlSet } from "../api";

const SOURCE_CONFIG: Record<
  ControlSetSource,
  { label: string; icon: typeof BookOpen; className: string }
> = {
  paper: {
    label: "Paper",
    icon: BookOpen,
    className:
      "border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-200",
  },
  curation: {
    label: "Curated",
    icon: FlaskConical,
    className:
      "border-green-300 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-900 dark:text-green-200",
  },
  db_build: {
    label: "DB Build",
    icon: Server,
    className:
      "border-purple-300 bg-purple-50 text-purple-800 dark:border-purple-700 dark:bg-purple-900 dark:text-purple-200",
  },
  other: {
    label: "Other",
    icon: HelpCircle,
    className:
      "border-gray-300 bg-gray-50 text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200",
  },
};

interface ControlSetManagerProps {
  siteId: string;
  recordType: string;
  onSelect?: (cs: ControlSet) => void;
  selectedId?: string | null;
}

export function ControlSetManager({
  siteId,
  recordType,
  onSelect,
  selectedId,
}: ControlSetManagerProps) {
  const [controlSets, setControlSets] = useState<ControlSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const all = await listControlSets(siteId);
      setControlSets(all.filter((cs) => cs.recordType === recordType));
    } catch {
      /* swallow - empty list is fine */
    } finally {
      setLoading(false);
    }
  }, [siteId, recordType]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Database className="h-4 w-4" />
          Saved Control Sets
        </h3>
        <Button variant="outline" size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="h-3.5 w-3.5" />
          {showCreate ? "Cancel" : "New"}
        </Button>
      </div>

      {showCreate && (
        <CreateControlSetForm
          siteId={siteId}
          recordType={recordType}
          onCreated={() => {
            setShowCreate(false);
            void refresh();
          }}
        />
      )}

      {loading && (
        <p className="text-xs text-muted-foreground">Loading control sets...</p>
      )}
      {!loading && controlSets.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No saved control sets yet. Create one to reuse across experiments.
        </p>
      )}
      {controlSets.map((cs) => {
        const src = SOURCE_CONFIG[cs.source as ControlSetSource] ?? SOURCE_CONFIG.other;
        const isSelected = selectedId === cs.id;
        return (
          <div
            key={cs.id}
            className={`group relative rounded-lg border p-3 transition ${
              isSelected
                ? "border-primary bg-primary/5"
                : "border-border bg-card hover:border-primary/30"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">{cs.name}</span>
                  <Badge className={`text-[10px] ${src.className}`}>
                    <src.icon className="mr-1 h-2.5 w-2.5" />
                    {src.label}
                  </Badge>
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                  <span>+{cs.positiveIds.length} pos</span>
                  <span>-{cs.negativeIds.length} neg</span>
                  <span>v{cs.version}</span>
                </div>
                {cs.tags.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {cs.tags.map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="text-[10px] py-0 px-1.5"
                      >
                        <Tag className="mr-0.5 h-2 w-2" />
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
                {cs.provenanceNotes && (
                  <p className="mt-1 text-xs text-muted-foreground/80 line-clamp-2">
                    {cs.provenanceNotes}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-1">
                {onSelect && (
                  <Button
                    variant={isSelected ? "default" : "outline"}
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => onSelect(cs)}
                  >
                    {isSelected ? (
                      <>
                        <Check className="h-3 w-3" /> Selected
                      </>
                    ) : (
                      "Use"
                    )}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100"
                  onClick={async () => {
                    await deleteControlSet(cs.id);
                    void refresh();
                  }}
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CreateControlSetForm({
  siteId,
  recordType,
  onCreated,
}: {
  siteId: string;
  recordType: string;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<ControlSetSource>("paper");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [posIds, setPosIds] = useState("");
  const [negIds, setNegIds] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const parseLine = (raw: string) =>
        raw
          .split(/[\n,]+/)
          .map((s) => s.trim())
          .filter(Boolean);
      await createControlSet({
        name: name.trim(),
        siteId,
        recordType,
        positiveIds: parseLine(posIds),
        negativeIds: parseLine(negIds),
        source,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        provenanceNotes: notes || undefined,
        isPublic: false,
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-primary/20 bg-primary/5 p-4">
      <Input
        placeholder="Control set name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Source
          </label>
          <select
            className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm"
            value={source}
            onChange={(e) => setSource(e.target.value as ControlSetSource)}
          >
            {Object.entries(SOURCE_CONFIG).map(([val, { label }]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Tags (comma-separated)
          </label>
          <Input
            placeholder="e.g. invasion, blood-stage"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-muted-foreground">
          Provenance notes
        </label>
        <textarea
          className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm"
          rows={2}
          placeholder="Paper DOI, curation date, DB build version..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Positive control IDs (one per line or comma-separated)
          </label>
          <textarea
            className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs"
            rows={4}
            value={posIds}
            onChange={(e) => setPosIds(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Negative control IDs (one per line or comma-separated)
          </label>
          <textarea
            className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs"
            rows={4}
            value={negIds}
            onChange={(e) => setNegIds(e.target.value)}
          />
        </div>
      </div>
      <Button size="sm" onClick={handleSubmit} disabled={saving || !name.trim()}>
        {saving ? "Saving..." : "Save Control Set"}
      </Button>
    </div>
  );
}
