import {createConnectTransport} from "@connectrpc/connect-web";
import {createClient} from "@connectrpc/connect";
import {SchedulingService} from "@/gen/scheduling/v1/scheduling_pb";

const transport = createConnectTransport({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  interceptors: [],
});

export const schedulingClient = createClient(SchedulingService, transport);
