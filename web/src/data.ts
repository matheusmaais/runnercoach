import type { FrontendPayload } from "./types";

type LoadPayloadOptions = {
  cacheBust?: boolean;
};

export async function loadPayload(options: LoadPayloadOptions = {}): Promise<FrontendPayload> {
  const cacheKey = options.cacheBust ? `?ts=${Date.now()}` : "";
  const response = await fetch(`${import.meta.env.BASE_URL}data/app-data.json${cacheKey}`, {
    headers: { Accept: "application/json" },
    cache: options.cacheBust ? "no-store" : "default",
  });

  if (!response.ok) {
    throw new Error(`Frontend payload unavailable: HTTP ${response.status}`);
  }

  return response.json() as Promise<FrontendPayload>;
}
