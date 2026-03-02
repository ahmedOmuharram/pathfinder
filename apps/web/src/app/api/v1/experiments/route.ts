/**
 * Route handler for /api/v1/experiments.
 *
 * - GET: plain JSON proxy (list experiments).
 * - POST: streaming SSE proxy (create experiment).
 * - DELETE: plain JSON proxy (delete experiment).
 */

import { type NextRequest } from "next/server";

import { proxyJsonRequest, proxySSEPost } from "../_proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  const path = `/api/v1/experiments${qs ? `?${qs}` : ""}`;
  return proxyJsonRequest(req, path);
}

export async function POST(req: NextRequest) {
  return proxySSEPost(req, "/api/v1/experiments");
}

export async function DELETE(req: NextRequest) {
  return proxyJsonRequest(req, "/api/v1/experiments", { method: "DELETE" });
}
