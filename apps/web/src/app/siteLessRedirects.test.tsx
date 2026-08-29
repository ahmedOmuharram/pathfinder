import { beforeEach, describe, expect, it, vi } from "vitest";

const redirectMock = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (url: string) => redirectMock(url),
}));

import {
  chatRoot,
  PORTAL_SITE_ID,
  workbenchGeneSetUrl,
  workbenchRoot,
} from "@/lib/routes";
import BareConversationPage from "./conversation/page";
import RootPage from "./page";
import BareWorkbenchItemPage from "./workbench/[id]/page";
import BareWorkbenchPage from "./workbench/page";

describe("site-less entry points", () => {
  beforeEach(() => redirectMock.mockClear());

  it("sends the bare root to the portal's chat", () => {
    RootPage();
    expect(redirectMock).toHaveBeenCalledWith(chatRoot(PORTAL_SITE_ID));
    expect(redirectMock).toHaveBeenCalledWith("/veupathdb/conversation");
  });

  it("sends a site-less conversation path to the portal's chat", () => {
    BareConversationPage();
    expect(redirectMock).toHaveBeenCalledWith(chatRoot(PORTAL_SITE_ID));
  });

  it("sends a site-less workbench path to the portal's workbench", () => {
    BareWorkbenchPage();
    expect(redirectMock).toHaveBeenCalledWith(workbenchRoot(PORTAL_SITE_ID));
  });

  it("keeps the gene set id when it sends a site-less workbench item to the portal", async () => {
    await BareWorkbenchItemPage({ params: Promise.resolve({ id: "gs-42" }) });
    expect(redirectMock).toHaveBeenCalledWith(
      workbenchGeneSetUrl(PORTAL_SITE_ID, "gs-42"),
    );
    expect(redirectMock).toHaveBeenCalledWith("/veupathdb/workbench/gs-42");
  });
});
