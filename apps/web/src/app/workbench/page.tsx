import { redirect } from "next/navigation";

import { PORTAL_SITE_ID, workbenchRoot } from "@/lib/routes";

export default function BareWorkbenchPage(): never {
  redirect(workbenchRoot(PORTAL_SITE_ID));
}
