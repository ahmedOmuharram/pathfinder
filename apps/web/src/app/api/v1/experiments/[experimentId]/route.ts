/**
 * Route handler for /api/v1/experiments/:experimentId.
 *
 * Proxies GET, DELETE, PATCH, and POST to the upstream FastAPI backend.
 */

import { type NextRequest } from "next/server";
import { proxyJsonRequest } from "../../_proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ experimentId: string }> };

function upstreamPath(req: NextRequest, experimentId: string): string {
  const base = `/api/v1/experiments/${encodeURIComponent(experimentId)}`;
  const qs = new URL(req.url).searchParams.toString();
  return qs ? `${base}?${qs}` : base;
}

export async function GET(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  return proxyJsonRequest(req, upstreamPath(req, experimentId));
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  return proxyJsonRequest(req, upstreamPath(req, experimentId), { method: "DELETE" });
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  return proxyJsonRequest(req, upstreamPath(req, experimentId), {
    method: "PATCH",
    includeBody: true,
  });
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  const { pathname } = new URL(req.url);
  const suffix = pathname.split(`/experiments/${experimentId}`)[1] ?? "";
  const base = `/api/v1/experiments/${encodeURIComponent(experimentId)}${suffix}`;
  const qs = new URL(req.url).searchParams.toString();
  const path = qs ? `${base}?${qs}` : base;
  return proxyJsonRequest(req, path, { method: "POST", includeBody: true });
}
