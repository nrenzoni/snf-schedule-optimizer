import { z } from "zod";

export const schedulerSettingsSchema = z
  .object({
    useMLForecast: z.boolean(),
    useCalloutBuffer: z.boolean(),
    bufferThreshold: z.number().min(0).max(20),
    minRestPeriod: z.number().min(8).max(16),
    maxShiftLength: z.number().min(8).max(14),
    premiumWeekend: z.boolean(),
    premiumHoliday: z.boolean(),
    overtimeAvoidancePenalty: z.number().min(0),
    teamConsistencyPenalty: z.number().min(0),
    highRiskShiftPenalty: z.number().min(0),
    customPreferencePenalty: z.number().min(0),
  })
  .refine((data) => data.minRestPeriod <= data.maxShiftLength, {
    message: "Min rest period must not exceed max shift length",
    path: ["minRestPeriod"],
  });

export type SchedulerSettingsFormValues = z.infer<typeof schedulerSettingsSchema>;
