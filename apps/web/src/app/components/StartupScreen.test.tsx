/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { StartupScreen, startupStatus } from "./StartupScreen";

afterEach(() => {
  cleanup();
});

describe("startupStatus", () => {
  it("stays booting inside the grace window", () => {
    expect(
      startupStatus({
        data: undefined,
        isError: false,
        elapsedMs: 1000,
        graceMs: 20000,
      }),
    ).toEqual({ kind: "booting", notReady: [] });
  });

  it("reports unreachable when stalled with no response", () => {
    expect(
      startupStatus({
        data: undefined,
        isError: false,
        elapsedMs: 25000,
        graceMs: 20000,
      }),
    ).toEqual({ kind: "unreachable" });
  });

  it("reports unreachable when stalled and the query errored", () => {
    expect(
      startupStatus({
        data: undefined,
        isError: true,
        elapsedMs: 25000,
        graceMs: 20000,
      }),
    ).toEqual({ kind: "unreachable" });
  });

  it("reports degraded with the failing subsystems when stalled but reachable", () => {
    expect(
      startupStatus({
        data: {
          ready: false,
          apiReady: false,
          workerAlive: true,
          notReady: ["database"],
        },
        isError: false,
        elapsedMs: 25000,
        graceMs: 20000,
      }),
    ).toEqual({ kind: "degraded", notReady: ["database"] });
  });
});

describe("StartupScreen", () => {
  it("shows the spinner and pending subsystems while booting", () => {
    render(<StartupScreen status={{ kind: "booting", notReady: ["worker"] }} />);
    expect(screen.getByText(/starting up/i)).toBeInTheDocument();
    expect(screen.getByText(/worker/)).toBeInTheDocument();
  });

  it("surfaces a degraded error naming the failing subsystem", () => {
    render(<StartupScreen status={{ kind: "degraded", notReady: ["database"] }} />);
    expect(screen.getByText(/failed to start/i)).toBeInTheDocument();
    expect(screen.getByText(/database/)).toBeInTheDocument();
    expect(screen.getByText(/report this to an administrator/i)).toBeInTheDocument();
  });

  it("surfaces an unreachable error and tells the user to report it", () => {
    render(<StartupScreen status={{ kind: "unreachable" }} />);
    expect(screen.getByText(/can't reach the server/i)).toBeInTheDocument();
    expect(screen.getByText(/report this to an administrator/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /retry/i })).toBeNull();
  });
});
