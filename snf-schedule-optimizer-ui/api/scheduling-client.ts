import {createConnectTransport} from "@connectrpc/connect-web";
import {createClient} from "@connectrpc/connect";
import {SchedulingService} from "@/gen/scheduling/v1/scheduling_pb";

const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const transport = createConnectTransport({
  baseUrl: configuredBaseUrl ?? "http://localhost:8000",
  interceptors: [],
});

export const schedulingClient = createClient(SchedulingService, transport);
export const isUsingFallbackApiBaseUrl = !configuredBaseUrl;
