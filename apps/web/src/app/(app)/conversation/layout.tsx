import { ChatShell } from "@/features/conversation/ChatShell";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <ChatShell />
      {children}
    </>
  );
}
