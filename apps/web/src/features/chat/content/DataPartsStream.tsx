"use client";

import type { DataPartKind } from "@pathfinder/shared";

import { DataPartRenderer } from "./DataPartRenderer";
import { dataPartComponents } from "./contentComponents";

export interface DataPartEntry {
  id: string;
  kind: string;
  data: unknown;
}

function isKnownKind(kind: string): kind is DataPartKind {
  return kind in dataPartComponents;
}

export function DataPartsStream({ parts }: { parts: DataPartEntry[] }) {
  if (parts.length === 0) return null;
  return (
    <div className="flex w-full flex-col gap-2">
      {parts.map((part) =>
        isKnownKind(part.kind) ? (
          <DataPartRenderer key={part.id} kind={part.kind} data={part.data} />
        ) : null,
      )}
    </div>
  );
}
