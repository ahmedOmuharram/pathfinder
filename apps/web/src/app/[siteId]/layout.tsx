import { SystemReadyGate } from "@/app/components/SystemReadyGate";

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return <SystemReadyGate>{children}</SystemReadyGate>;
}
