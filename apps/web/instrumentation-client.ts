/**
 * Next.js 16 client-side instrumentation entrypoint.
 *
 * Runs once, before any app code, on the browser. This is the only place
 * where we can safely call `initTelemetry()` — the global fetch patcher in
 * `FetchInstrumentation` has to install before the first `fetch()` the app
 * makes, otherwise the initial API requests escape instrumentation.
 *
 * Global error handlers are installed here too so window-level crashes that
 * happen during app bootstrap (before any component mounts) are still
 * captured.
 *
 * Reference: https://nextjs.org/docs/app/guides/instrumentation-client
 */

import { initTelemetry } from "@/lib/telemetry/init";
import { installGlobalErrorHandlers } from "@/lib/telemetry/globalHandlers";

initTelemetry();
installGlobalErrorHandlers();
