import { type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_COLLECTOR = "http://signoz-otel-collector:4318";

export async function POST(req: NextRequest): Promise<Response> {
  const collector = process.env["SIGNOZ_OTEL_COLLECTOR_HTTP"] ?? DEFAULT_COLLECTOR;
  const target = `${collector.replace(/\/+$/, "")}/v1/traces`;
  const body = await req.arrayBuffer();
  const contentType = req.headers.get("content-type") ?? "application/x-protobuf";

  try {
    const upstream = await fetch(target, {
      method: "POST",
      body,
      headers: { "content-type": contentType },
    });
    return new Response(null, { status: upstream.ok ? 204 : upstream.status });
  } catch {
    return new Response(null, { status: 204 });
  }
}

export function OPTIONS(): Response {
  return new Response(null, {
    status: 204,
    headers: { allow: "POST, OPTIONS" },
  });
}
