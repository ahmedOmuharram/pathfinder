import { useMemo, useState } from "react";
import { Search as SearchIcon, Sparkles } from "lucide-react";
import { Modal } from "@/lib/components/Modal";
import { Button } from "@/lib/components/ui/Button";
import { GeneLookupPanel } from "../GeneLookupPanel";
import { ValidatedGeneInput } from "../ValidatedGeneInput";
import { AiAssistantPanel } from "../AiAssistantPanel";
import type { ResolvedGene } from "@/lib/api/client";

interface ControlsModalProps {
  open: boolean;
  siteId: string;
  positiveGenes: ResolvedGene[];
  onPositiveGenesChange: (genes: ResolvedGene[]) => void;
  negativeGenes: ResolvedGene[];
  onNegativeGenesChange: (genes: ResolvedGene[]) => void;
  onClose: () => void;
}

export function ControlsModal({
  open,
  siteId,
  positiveGenes,
  onPositiveGenesChange,
  negativeGenes,
  onNegativeGenesChange,
  onClose,
}: ControlsModalProps) {
  const [showGeneLookup, setShowGeneLookup] = useState(false);
  const [showAiPanel, setShowAiPanel] = useState(false);

  const positiveGeneIds = useMemo(
    () => new Set(positiveGenes.map((g) => g.geneId)),
    [positiveGenes],
  );
  const negativeGeneIds = useMemo(
    () => new Set(negativeGenes.map((g) => g.geneId)),
    [negativeGenes],
  );

  const positiveControls = useMemo(
    () => positiveGenes.map((g) => g.geneId),
    [positiveGenes],
  );
  const negativeControls = useMemo(
    () => negativeGenes.map((g) => g.geneId),
    [negativeGenes],
  );

  const handleGeneAdd = (geneId: string, role: "positive" | "negative") => {
    const gene: ResolvedGene = {
      geneId,
      displayName: geneId,
      organism: "",
      product: "",
      geneName: "",
      geneType: "",
      location: "",
    };
    if (role === "positive") {
      if (!positiveGeneIds.has(geneId)) {
        onPositiveGenesChange([...positiveGenes, gene]);
      }
    } else {
      if (!negativeGeneIds.has(geneId)) {
        onNegativeGenesChange([...negativeGenes, gene]);
      }
    }
  };

  const aiContext = useMemo(
    () => ({
      positiveControls,
      negativeControls,
    }),
    [positiveControls, negativeControls],
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Control Genes"
      maxWidth={showAiPanel ? "max-w-6xl" : "max-w-3xl"}
    >
      <div className="flex max-h-[80vh]">
        {/* Main content */}
        <div className="min-w-0 flex-1 space-y-5 overflow-y-auto p-5">
          <div className="flex items-center gap-2">
            {!showGeneLookup && (
              <Button
                variant="outline"
                className="flex-1 border-dashed"
                onClick={() => setShowGeneLookup(true)}
              >
                <SearchIcon className="h-4 w-4" />
                Find Gene IDs via Site Search
              </Button>
            )}
            <Button
              variant={showAiPanel ? "default" : "outline"}
              className={showAiPanel ? "" : "flex-1 border-dashed"}
              onClick={() => setShowAiPanel(!showAiPanel)}
            >
              <Sparkles className="h-4 w-4" />
              {showAiPanel ? "Hide AI" : "Ask AI for Control Genes"}
            </Button>
          </div>

          {showGeneLookup && (
            <GeneLookupPanel
              siteId={siteId}
              positiveGeneIds={positiveGeneIds}
              negativeGeneIds={negativeGeneIds}
              onAddPositive={(gene) => onPositiveGenesChange([...positiveGenes, gene])}
              onAddNegative={(gene) => onNegativeGenesChange([...negativeGenes, gene])}
              onClose={() => setShowGeneLookup(false)}
            />
          )}

          <ValidatedGeneInput
            siteId={siteId}
            genes={positiveGenes}
            onGenesChange={onPositiveGenesChange}
            excludeGeneIds={negativeGeneIds}
            label="Positive Controls (known genes that SHOULD be found)"
            placeholder="Type a gene ID and press Enter..."
            variant="positive"
          />

          <ValidatedGeneInput
            siteId={siteId}
            genes={negativeGenes}
            onGenesChange={onNegativeGenesChange}
            excludeGeneIds={positiveGeneIds}
            label="Negative Controls (known genes that should NOT be found)"
            placeholder="Type a gene ID and press Enter..."
            variant="negative"
          />

          <div className="flex justify-end pt-2">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>

        {/* AI Assistant side panel */}
        {showAiPanel && (
          <div className="w-96 shrink-0">
            <AiAssistantPanel
              siteId={siteId}
              step="controls"
              context={aiContext}
              onGeneAdd={handleGeneAdd}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
