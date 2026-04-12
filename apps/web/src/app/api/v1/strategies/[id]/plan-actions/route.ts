import { type NextRequest } from "next/server";

import { proxyJsonRequest } from "@/app/api/v1/_proxy";

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  return proxyJsonRequest(req, `/api/v1/strategies/${id}/plan-actions`, {
    includeBody: true,
  });
}
