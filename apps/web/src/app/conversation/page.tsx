import { redirect } from "next/navigation";

import { chatRoot, PORTAL_SITE_ID } from "@/lib/routes";

export default function BareConversationPage(): never {
  redirect(chatRoot(PORTAL_SITE_ID));
}
