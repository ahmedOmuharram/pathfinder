import { use } from "react";

import { SavedStrategiesPage } from "@/features/saved/SavedStrategiesPage";

export default function Page({
  params,
}: {
  params: Promise<{ siteId: string }>;
}) {
  const { siteId } = use(params);
  return <SavedStrategiesPage siteId={siteId} />;
}
