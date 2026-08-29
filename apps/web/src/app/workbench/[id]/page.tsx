import { redirect } from "next/navigation";

import { PORTAL_SITE_ID, workbenchGeneSetUrl } from "@/lib/routes";

export default async function BareWorkbenchItemPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<never> {
  const { id } = await params;
  redirect(workbenchGeneSetUrl(PORTAL_SITE_ID, id));
}
