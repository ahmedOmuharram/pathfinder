// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/features/settings/api/privacy", () => ({
  getPrivacySettings: vi.fn(),
  updatePrivacySettings: vi.fn(),
}));

const authState = { refreshed: true, signedIn: true };

vi.mock("@/lib/query/hooks/useAuthRefresh", () => ({
  useAuthRefresh: () => ({ authRefreshed: authState.refreshed }),
}));

vi.mock("@/lib/api/veupathdb-auth", () => ({
  authStatusOptions: (siteId: string) => ({
    queryKey: ["auth", "status", siteId],
    queryFn: () => ({ signedIn: authState.signedIn }),
  }),
}));

import {
  getPrivacySettings,
  updatePrivacySettings,
} from "@/features/settings/api/privacy";
import { EvalDataNotice } from "./EvalDataNotice";

const mockedGet = vi.mocked(getPrivacySettings);
const mockedUpdate = vi.mocked(updatePrivacySettings);

beforeEach(() => {
  mockedGet.mockReset();
  mockedUpdate.mockReset();
  authState.refreshed = true;
  authState.signedIn = true;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("EvalDataNotice", () => {
  it("shows once for an account that has not seen it", async () => {
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });

    render(<EvalDataNotice />);

    expect(await screen.findByText(/PathFinder improves by learning/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /^OK$/ })).toBeVisible();
  });

  it("never shows again once the account has seen it", async () => {
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: true });

    render(<EvalDataNotice />);

    await waitFor(() => {
      expect(mockedGet).toHaveBeenCalled();
    });
    expect(screen.queryByText(/PathFinder improves by learning/i)).toBe(null);
  });

  it("marks the notice seen on OK and keeps consent on", async () => {
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });
    mockedUpdate.mockResolvedValue({ evalDataConsent: true, noticeSeen: true });

    render(<EvalDataNotice />);
    fireEvent.click(await screen.findByRole("button", { name: /^OK$/ }));

    await waitFor(() => {
      expect(mockedUpdate).toHaveBeenCalledWith({ noticeSeen: true });
    });
  });

  it("opts out inline and marks the notice seen in the same call", async () => {
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });
    mockedUpdate.mockResolvedValue({ evalDataConsent: false, noticeSeen: true });

    render(<EvalDataNotice />);
    fireEvent.click(await screen.findByRole("button", { name: /turn off/i }));

    await waitFor(() => {
      expect(mockedUpdate).toHaveBeenCalledWith({
        noticeSeen: true,
        evalDataConsent: false,
      });
    });
  });

  it("closes after acknowledgement", async () => {
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });
    mockedUpdate.mockResolvedValue({ evalDataConsent: true, noticeSeen: true });

    render(<EvalDataNotice />);
    fireEvent.click(await screen.findByRole("button", { name: /^OK$/ }));

    await waitFor(() => {
      expect(screen.queryByText(/PathFinder improves by learning/i)).toBe(null);
    });
  });

  it("shows nothing while the decision is unknown", () => {
    mockedGet.mockReturnValue(new Promise(() => {}));

    render(<EvalDataNotice />);

    expect(screen.queryByText(/PathFinder improves by learning/i)).toBe(null);
  });
});

describe("EvalDataNotice before the session is ready", () => {
  it("asks nothing while the token refresh has not settled", async () => {
    authState.refreshed = false;
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });

    render(<EvalDataNotice />);

    await waitFor(() => {
      expect(screen.queryByText(/PathFinder improves by learning/i)).toBe(null);
    });
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("asks nothing for a visitor who is not signed in", async () => {
    authState.signedIn = false;
    mockedGet.mockResolvedValue({ evalDataConsent: true, noticeSeen: false });

    render(<EvalDataNotice />);

    await waitFor(() => {
      expect(screen.queryByText(/PathFinder improves by learning/i)).toBe(null);
    });
    expect(mockedGet).not.toHaveBeenCalled();
  });
});
