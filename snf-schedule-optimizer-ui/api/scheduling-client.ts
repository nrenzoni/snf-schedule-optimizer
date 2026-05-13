import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { SchedulingService } from "@/gen/scheduling/v1/scheduling_pb";

export const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";
const configuredRunId = process.env.NEXT_PUBLIC_E2E_RUN_ID?.trim();

const transport = createConnectTransport({
  baseUrl: configuredBaseUrl || "http://invalid.localhost",
  interceptors: [],
  fetch: (input, init) => {
    if (!configuredBaseUrl) {
      throw new Error(
        "Missing NEXT_PUBLIC_API_BASE_URL. Configure the UI with an explicit backend base URL.",
      );
    }

    if (!configuredRunId) {
      return fetch(input, init);
    }

    const headers = new Headers(init?.headers);
    headers.set("x-e2e-run-id", configuredRunId);

    return fetch(input, {
      ...init,
      headers,
    });
  },
});

export const schedulingClient = createClient(SchedulingService, transport);
