import { redirect } from "next/navigation";

export default async function BareWorkbenchItemPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<never> {
  const { id } = await params;
  redirect(`/veupathdb/workbench/${id}`);
}
