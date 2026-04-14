import { randomUUID } from "node:crypto";
import { redirect } from "next/navigation";

export default function ChatNewPage(): never {
  redirect(`/chat/${randomUUID()}`);
}
