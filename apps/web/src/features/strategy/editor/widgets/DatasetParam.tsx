"use client";

import { useState } from "react";
import {
  ClipboardListIcon,
  FileUpIcon,
  FolderIcon,
  ListChecksIcon,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils/cn";
import type { ParamWidgetProps } from "./types";
import {
  basketNameFromConfig,
  decodeDatasetValue,
  defaultIdListFromInitial,
  encodeDatasetValue,
  fileNameFromConfig,
  initialTabFor,
  parseIdsFromText,
  pasteTextFromConfig,
  strategyIdFromConfig,
  type DatasetConfig,
  type DatasetWidgetTab,
} from "./datasetParamLogic";
import {
  BasketTab,
  DefaultTab,
  PasteTab,
  StrategyTab,
  UploadTab,
} from "./DatasetParamTabs";

export function DatasetParam({ spec, name, field }: ParamWidgetProps) {
  const raw = typeof field.state.value === "string" ? field.state.value : "";
  const decoded = decodeDatasetValue(raw);
  const defaultIds = defaultIdListFromInitial(spec.initialDisplayValue);
  const hasDefault = defaultIds.length > 0;

  const [tab, setTab] = useState<DatasetWidgetTab>(() =>
    initialTabFor(decoded, hasDefault),
  );
  const [pasteText, setPasteText] = useState<string>(() =>
    pasteTextFromConfig(decoded),
  );

  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  const commit = (next: DatasetConfig | null) => {
    field.handleChange(encodeDatasetValue(next));
    field.handleBlur();
  };

  const updatePaste = (text: string) => {
    setPasteText(text);
    const ids = parseIdsFromText(text);
    if (ids.length === 0) {
      commit(null);
      return;
    }
    commit({ sourceType: "idList", sourceContent: { ids } });
  };

  const applyDefault = () => {
    commit({ sourceType: "idList", sourceContent: { ids: defaultIds } });
    setPasteText(defaultIds.join("\n"));
  };

  const handleFileSelected = (file: File, content: string) => {
    const ids = parseIdsFromText(content);
    commit({
      sourceType: "file",
      sourceContent: {
        fileName: file.name,
        ...(ids.length > 0 ? { temporaryFileId: `inline:${file.name}` } : {}),
      },
    });
  };

  const updateBasket = (basketName: string) => {
    if (basketName.trim() === "") {
      commit(null);
      return;
    }
    commit({ sourceType: "basket", sourceContent: { basketName } });
  };

  const updateStrategy = (strategyId: string) => {
    const trimmed = strategyId.trim();
    if (trimmed === "") {
      commit(null);
      return;
    }
    commit({ sourceType: "strategy", sourceContent: { strategyId: trimmed } });
  };

  const isDefaultApplied =
    decoded !== null &&
    decoded.sourceType === "idList" &&
    defaultIds.length > 0 &&
    decoded.sourceContent.ids.join(",") === defaultIds.join(",");

  return (
    <div
      data-testid="dataset-param-root"
      className={cn(
        "rounded-md border bg-card p-3",
        hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
      )}
    >
      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as DatasetWidgetTab)}
        className="w-full"
      >
        <TabsList className="w-full">
          <TabsTrigger value="paste">
            <ClipboardListIcon className="size-3.5" aria-hidden />
            Paste IDs
          </TabsTrigger>
          {hasDefault && (
            <TabsTrigger value="default">
              <ListChecksIcon className="size-3.5" aria-hidden />
              Default
            </TabsTrigger>
          )}
          <TabsTrigger value="upload">
            <FileUpIcon className="size-3.5" aria-hidden />
            Upload
          </TabsTrigger>
          <TabsTrigger value="basket">
            <FolderIcon className="size-3.5" aria-hidden />
            Basket
          </TabsTrigger>
          <TabsTrigger value="strategy">
            <ListChecksIcon className="size-3.5" aria-hidden />
            Strategy
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paste" className="mt-3">
          <PasteTab text={pasteText} onTextChange={updatePaste} name={name} />
        </TabsContent>
        {hasDefault && (
          <TabsContent value="default" className="mt-3">
            <DefaultTab
              defaultIds={defaultIds}
              isApplied={isDefaultApplied}
              onApply={applyDefault}
            />
          </TabsContent>
        )}
        <TabsContent value="upload" className="mt-3">
          <UploadTab
            fileName={fileNameFromConfig(decoded)}
            onFileSelected={handleFileSelected}
          />
        </TabsContent>
        <TabsContent value="basket" className="mt-3">
          <BasketTab
            value={basketNameFromConfig(decoded)}
            onChange={updateBasket}
            name={name}
          />
        </TabsContent>
        <TabsContent value="strategy" className="mt-3">
          <StrategyTab
            value={strategyIdFromConfig(decoded)}
            onChange={updateStrategy}
          />
        </TabsContent>
      </Tabs>

      {raw !== "" && decoded === null && (
        <p className="mt-2 text-xs text-amber-600">
          Existing value is not a recognized DatasetConfig; pick a tab to overwrite.
        </p>
      )}

      {hasError && errorMessage !== null && (
        <p id={`${name}-error`} role="alert" className="mt-2 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
