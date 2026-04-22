/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { Skeleton } from "@/components/ui/skeleton";

describe("Skeleton", () => {
  it("renders with skeleton data-slot", () => {
    const { container } = render(<Skeleton className="h-4 w-32" />);
    const node = container.querySelector('[data-slot="skeleton"]');
    expect(node).not.toBeNull();
    expect(node?.className).toContain("h-4");
    expect(node?.className).toContain("w-32");
  });
});
