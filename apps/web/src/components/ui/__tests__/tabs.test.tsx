/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

describe("Tabs", () => {
  it("switches active panel when a trigger is clicked", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="alpha">
        <TabsList>
          <TabsTrigger value="alpha">Alpha</TabsTrigger>
          <TabsTrigger value="beta">Beta</TabsTrigger>
        </TabsList>
        <TabsContent value="alpha">Alpha panel</TabsContent>
        <TabsContent value="beta">Beta panel</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Alpha panel")).toBeInTheDocument();
    expect(screen.queryByText("Beta panel")).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Beta" }));

    expect(screen.getByText("Beta panel")).toBeInTheDocument();
    expect(screen.queryByText("Alpha panel")).toBeNull();
  });
});
