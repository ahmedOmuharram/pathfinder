import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { Strategy } from "@pathfinder/shared";
import { conversationDetailKey } from "@/lib/api/conversations";

export function makeQueryHarness(initial: Strategy | null = null) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  if (initial !== null) {
    client.setQueryData(conversationDetailKey(initial.id), initial);
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return {
    wrapper,
    client,
    getStrategy: (id: string): Strategy | null =>
      client.getQueryData<Strategy>(conversationDetailKey(id)) ?? null,
    setStrategy: (next: Strategy) =>
      client.setQueryData<Strategy>(conversationDetailKey(next.id), next),
  };
}
