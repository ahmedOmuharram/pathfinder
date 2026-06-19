/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";

import { useSiteTheme } from "./useSiteTheme";
import { applySiteTheme } from "@/features/sites/siteTheme";

vi.mock("@/features/sites/siteTheme", () => ({
  applySiteTheme: vi.fn(),
}));

const mockApply = vi.mocked(applySiteTheme);

afterEach(() => {
  cleanup();
  mockApply.mockClear();
});

describe("useSiteTheme", () => {
  it("applies the theme for the given site on mount", () => {
    renderHook(() => useSiteTheme("plasmodb"));
    expect(mockApply.mock.calls).toEqual([["plasmodb"]]);
  });

  it("does not apply a theme when the site id is empty", () => {
    renderHook(() => useSiteTheme(""));
    expect(mockApply).not.toHaveBeenCalled();
  });

  it("re-applies only when the site id changes", () => {
    const { rerender } = renderHook(
      ({ site }: { site: string }) => useSiteTheme(site),
      {
        initialProps: { site: "plasmodb" },
      },
    );
    expect(mockApply.mock.calls).toEqual([["plasmodb"]]);

    rerender({ site: "plasmodb" });
    expect(mockApply.mock.calls).toEqual([["plasmodb"]]);

    rerender({ site: "toxodb" });
    expect(mockApply.mock.calls).toEqual([["plasmodb"], ["toxodb"]]);
  });
});
