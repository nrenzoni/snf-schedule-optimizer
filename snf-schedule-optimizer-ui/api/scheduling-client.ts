import {createConnectTransport} from "@connectrpc/connect-web";
import {createClient} from "@connectrpc/connect";
import {SchedulingService} from "../gen/schema/scheduling_pb"; // Placeholder for generated code

// Configuration for the Connect transport
const transport = createConnectTransport({
    baseUrl: "http://localhost:8080", // **UPDATE THIS TO YOUR PYTHON BACKEND URL**
    // Recommended for authentication and cross-origin security
    interceptors: [
        // Add interceptors here for logging, authentication, etc.
    ],
});

/**
 * Connect RPC client instance for the SchedulingService.
 * This client is used to make strongly-typed RPC calls to the backend.
 */
export const schedulingClient = createClient(SchedulingService, transport);

// You would typically use a code generation step here:
// E.g., buf generate && connect-es --ts_proto_out src/proto proto/scheduling.proto
// This generates 'scheduling_connect.ts' and 'scheduling.ts' files (our placeholder).