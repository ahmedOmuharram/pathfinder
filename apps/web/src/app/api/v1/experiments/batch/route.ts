/**
 * Streaming SSE proxy for the /api/v1/experiments/batch endpoint.
 */

import { type NextRequest } from "next/server";

import { proxySSEPost } from "../../_proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  return proxySSEPost(req, "/api/v1/experiments/batch");
}
