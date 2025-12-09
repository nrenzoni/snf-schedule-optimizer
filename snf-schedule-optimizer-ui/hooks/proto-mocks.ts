// --- PROTO TYPES (Client Side) ---

export enum ValidationLevel {
  VALIDATION_OK = 0,
  VALIDATION_WARNING = 1, // Yellow
  VALIDATION_CRITICAL = 2, // Red/Block
}

export type SimulateActionRequest = {
  shiftId: string;
  targetUnitId?: string; // Derived from staffId/Group
  targetWorkerId?: string;
  targetDateStr: string;
  targetShiftType: string;
};

export type SimulateActionResponse = {
  isAllowed: boolean;
  rejectionReason?: string;
  costDelta: number;
  causesOvertime: boolean;
  hprdDelta: number;
  complianceStatus: ValidationLevel;
};

// --- MOCK BACKEND SERVICE ---

export const mockSimulateAction = async (
  req: SimulateActionRequest,
): Promise<SimulateActionResponse> => {
  console.log(
    "Simulating action for shift:",
    req.shiftId,
    "to worker:",
    req.targetWorkerId,
    "on date:",
    req.targetDateStr,
  );

  // Simulate network latency (debounce feel)
  await new Promise((resolve) => setTimeout(resolve, 300));

  // Mock Logic:
  // If moving to "Mary" (who we pretend is 'st1'), she hits OT.
  // If moving to "Bob" ('st2'), he is cheap.

  if (req.targetWorkerId === "st1") {
    return {
      isAllowed: true,
      costDelta: 75.0,
      causesOvertime: true,
      hprdDelta: 0.2, // Positive means better compliance usually
      complianceStatus: ValidationLevel.VALIDATION_WARNING,
    };
  }

  // Simulate a critical error (e.g., double booking)
  if (req.targetWorkerId === "st4") {
    return {
      isAllowed: false,
      rejectionReason: "Double Booking",
      costDelta: 0,
      causesOvertime: false,
      hprdDelta: 0,
      complianceStatus: ValidationLevel.VALIDATION_CRITICAL,
    };
  }

  // Standard Move
  return {
    isAllowed: true,
    costDelta: 0,
    causesOvertime: false,
    hprdDelta: 0.05,
    complianceStatus: ValidationLevel.VALIDATION_OK,
  };
};
