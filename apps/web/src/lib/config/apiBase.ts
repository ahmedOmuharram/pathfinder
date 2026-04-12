const MISSING_API_URL_MESSAGE =
  "NEXT_PUBLIC_API_URL is required. Copy .env.example or .env.dev.example and configure the API base URL before starting the web app.";

export function getConfiguredServerApiBaseUrl(): string {
  const value = process.env["NEXT_PUBLIC_API_URL"]?.trim();
  if (!value) {
    throw new Error(MISSING_API_URL_MESSAGE);
  }
  return value.replace(/\/+$/, "");
}

export { MISSING_API_URL_MESSAGE };
