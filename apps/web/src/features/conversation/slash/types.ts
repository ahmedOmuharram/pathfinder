import type { ReactNode } from "react";

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

export type ParamDef =
  | {
      kind: "select";
      name: string;
      label: string;
      options: SelectOption[];
      optionsFn?: undefined;
    }
  | {
      kind: "select";
      name: string;
      label: string;
      options?: undefined;
      optionsFn: (ctx: CommandContext) => Promise<SelectOption[]> | SelectOption[];
    }
  | {
      kind: "text";
      name: string;
      label: string;
      placeholder?: string;
    }
  | {
      kind: "textarea";
      name: string;
      label: string;
      placeholder?: string;
      rows?: number;
    }
  | {
      kind: "file";
      name: string;
      label: string;
      accept: string;
    };

export type ParamValues = Record<string, string>;

export interface CommandContext {
  conversationId: string;
  siteId: string;
  /** Step count from the current strategy. Used by specialist/launcher
   * commands to enforce preconditions (e.g. `/validate` requires ≥1 step). */
  stepCount: number;
  /** Kind of the active specialist mode, if any. Lets the slash menu
   * grey out launchers + specialist-enter commands while a specialist
   * session is open (the backend would 409 SESSION_CONFLICT anyway). */
  activeSpecialistKind?: "validate" | "research" | null;
}

export interface DeterministicHandlerResult {
  kind: "toast";
  type: "success" | "error" | "info";
  message: string;
}

export interface DeterministicDownloadResult {
  kind: "download";
  url: string;
  filename: string;
}

export interface PrefillResult {
  kind: "prefill";
  text: string;
  submit?: boolean;
}

export type CommandResult =
  | DeterministicHandlerResult
  | DeterministicDownloadResult
  | PrefillResult
  | { kind: "noop" };

export type DisabledReasonResolver = (ctx: CommandContext) => string | null;

export interface DeterministicCommand {
  kind: "deterministic";
  name: string;
  aliases?: string[];
  description: string;
  icon?: ReactNode;
  params: ParamDef[];
  disabledReason?: DisabledReasonResolver;
  run: (
    values: ParamValues,
    ctx: CommandContext,
  ) => Promise<CommandResult> | CommandResult;
}

export interface LlmPrefillCommand {
  kind: "llm-prefill";
  name: string;
  aliases?: string[];
  description: string;
  icon?: ReactNode;
  params: ParamDef[];
  disabledReason?: DisabledReasonResolver;
  prompt: (values: ParamValues, ctx: CommandContext) => string;
  autoSubmit?: boolean;
}

/**
 * Enters a specialist mode (`/validate`, `/research`). The composer handles
 * selection by POSTing to the enter endpoint instead of running a handler.
 * `params` is empty so the existing `ParamStepper` branch is skipped.
 */
export interface SpecialistEnterCommand {
  kind: "specialist-enter";
  name: string;
  aliases?: string[];
  description: string;
  icon?: ReactNode;
  params: [];
  disabledReason?: DisabledReasonResolver;
}

/**
 * Opens a launcher form (`/optimize`). The composer handles selection by
 * showing the form anchored to the composer; the form posts to the launcher
 * endpoint.
 */
export interface LauncherCommand {
  kind: "launcher";
  name: string;
  aliases?: string[];
  description: string;
  icon?: ReactNode;
  params: [];
  disabledReason?: DisabledReasonResolver;
}

export type Command =
  | DeterministicCommand
  | LlmPrefillCommand
  | SpecialistEnterCommand
  | LauncherCommand;
