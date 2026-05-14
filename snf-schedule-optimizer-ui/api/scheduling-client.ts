import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import {
  GetOptimizationRunResponse,
  GetScheduleStatusResponse,
  OptimizationRunEvent,
  PatchConflict,
  SchedulingService,
  StagedSchedulePatch,
  StartOptimizationRunResponse,
  ValidateShiftMoveResponse,
} from "@/gen/scheduling/v1/scheduling_pb";

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

export const streamOptimizationRun = async (
  runId: string,
  onEvent: (event: OptimizationRunEvent) => void,
  signal?: AbortSignal,
): Promise<void> => {
  for await (const event of schedulingClient.streamOptimizationRun({ runId }, { signal })) {
    onEvent(event);
  }
};

export const pollOptimizationRun = async (
  runId: string,
): Promise<GetOptimizationRunResponse> => {
  return schedulingClient.getOptimizationRun({ runId });
};

export const getScheduleStatus = async (input: {
  orgId: string;
  facilityId: string;
  scheduleId: string;
  currentScheduleVersion: number;
}): Promise<GetScheduleStatusResponse> => {
  return schedulingClient.getScheduleStatus(input);
};

export const validateShiftMove = async (input: {
  orgId: string;
  facilityId: string;
  scheduleId: string;
  employeeId: string;
  fromShiftId: string;
  toShiftId: string;
  payPeriodStartTs: bigint;
  scheduleVersion: number;
  stagedPatches: StagedSchedulePatch[];
  patchId: string;
}): Promise<ValidateShiftMoveResponse> => {
  return schedulingClient.validateShiftMove(input);
};

export const startOptimizationRun = async (input: {
  orgId: string;
  facilityId: string;
  scheduleId: string;
  baseScheduleVersion: number;
  startDate: string;
  endDate: string;
  stagedPatches: StagedSchedulePatch[];
  clientRequestId: string;
  allowOverwrite: boolean;
  persistResult: boolean;
  settings: NonNullable<Parameters<typeof schedulingClient.startOptimizationRun>[0]["settings"]>;
}): Promise<StartOptimizationRunResponse> => {
  return schedulingClient.startOptimizationRun(input);
};

export const hasBlockingConflicts = (conflicts: PatchConflict[]): boolean => conflicts.length > 0;
