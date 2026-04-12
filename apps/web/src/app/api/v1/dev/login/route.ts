import { type NextRequest } from "next/server";

import { proxyJsonRequest } from "../../_proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const search = req.nextUrl.search;
  return proxyJsonRequest(req, `/api/v1/dev/login${search}`);
}
