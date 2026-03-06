/**
 * Catch-all route for /api/v1/experiments/:experimentId/:action
 * (e.g. cross-validate, enrich, importable-strategies details).
 * Proxies GET and POST to the upstream backend.
 */

import { type NextRequest } from "next/server";
import { proxyJsonRequest } from "../../../_proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ experimentId: string; action: string[] }> };

function upstreamPath(
  req: NextRequest,
  experimentId: string,
  action: string[],
): string {
  const actionPath = action.map((a) => encodeURIComponent(a)).join("/");
  const base = `/api/v1/experiments/${encodeURIComponent(experimentId)}/${actionPath}`;
  const qs = new URL(req.url).searchParams.toString();
  return qs ? `${base}?${qs}` : base;
}

export async function GET(req: NextRequest, ctx: Ctx) {
  const { experimentId, action } = await ctx.params;
  return proxyJsonRequest(req, upstreamPath(req, experimentId, action));
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { experimentId, action } = await ctx.params;
  return proxyJsonRequest(req, upstreamPath(req, experimentId, action), {
    method: "POST",
    includeBody: true,
  });
}
