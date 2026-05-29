import type { FrontendPayload } from "./types";

export async function loadPayload(): Promise<FrontendPayload> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/app-data.json`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Frontend payload unavailable: HTTP ${response.status}`);
  }

  return response.json() as Promise<FrontendPayload>;
}
