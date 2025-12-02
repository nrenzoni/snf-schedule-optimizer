import {useCallback, useEffect, useMemo, useState} from 'react';
import {
    formatDate,
    generateEmptyScheduleMap,
    generateMockScheduleMap,
    getStartOfMonth,
    getStartOfWeek
} from '@/utils/scheduling-logic';
import {schedulingClient} from "@/api/scheduling-client";
import {DaySchedule as ProtoDaySchedule} from "@/gen/schema/scheduling_pb";
import {ScheduleMap, UIDaySchedule} from "@/types/scheduling";

// production hook to fetch real schedules from backend
export function useSchedules(currentDate: Date) {
    const [schedules, setSchedules] = useState<ScheduleMap>(new Map());
    const [isLoading, setIsLoading] = useState(false);

    const fetchSchedule = useCallback(async (date: Date) => {
        const startDateString = formatDate(getStartOfMonth(date));
        setIsLoading(true);

        try {
            const request = {startDate: startDateString};
            const response = await schedulingClient.getMonthlySchedule(request);

            const newSchedules = new Map<string, UIDaySchedule>();
            Object.entries(response.schedules).forEach(([dateStr, schedule]) => {
                newSchedules.set(dateStr, protoDayToUI(schedule as ProtoDaySchedule));
            });

            setSchedules(newSchedules);
        } catch (error) {
            setSchedules(new Map());
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        console.log("useEffect", "fetching schedules for date:", currentDate);
        fetchSchedule(currentDate);
    }, [currentDate, fetchSchedule]);

    return {schedules, isLoading, fetchSchedule};
}

export function useMockScheduling(currentDate: Date, optimizationTrigger: number) {
    const [isLoading, setIsLoading] = useState(false);
    const [isOptimized, setIsOptimized] = useState(false);

    const triggerOptimization = useCallback(() => {
        setIsOptimized(true);
    }, []);

    // 1. Calculate schedules purely inside useMemo based on the CURRENT month
    const schedules = useMemo(() => {

        const startOfGrid = getStartOfWeek(getStartOfMonth(currentDate));
        let mockMap;
        if (isOptimized) {
            // Post-Optimization: Use the fully calculated mock data
            mockMap = generateMockScheduleMap(startOfGrid, 42);
            console.log("Mock schedules (OPTIMIZED) generated.");
        } else {
            // Initial State: Use the 0% empty schedule data
            mockMap = generateEmptyScheduleMap(startOfGrid, 42);
            console.log("Mock schedules (EMPTY/0%) generated.");
        }

        return mockMap;
    }, [currentDate, isOptimized]);

    // 2. Manage loading state simulation in useEffect
    useEffect(() => {
        console.log("useEffect triggered for loading state. CurrentDate:", currentDate, "OptimizationTrigger:", optimizationTrigger);
        setIsLoading(true);
        // Simulate a network delay for 500ms
        const timer = setTimeout(() => {
            setIsLoading(false);
        }, 500);

        return () => clearTimeout(timer); // Cleanup on unmount or re-run
    }, [currentDate, optimizationTrigger]);

    const fetchSchedule = useCallback(() => {
        console.log("Mock fetch triggered.");
        // Does nothing for the mock, but keeps the interface the same
    }, []);

    return {schedules, isLoading, fetchSchedule, triggerOptimization};
}

// Convert a protobuf DaySchedule/Shift into the UI DaySchedule/Shift shape
const protoShiftToUI = (p: any): any => ({
    shiftName: (p.shiftName as any) as 'Morning' | 'Afternoon' | 'Night',
    patientCount: p.patientCount,
    requiredHPRD: (p.requiredHrpd ?? 0),
    requiredHours: p.requiredHours,
    actualHours: p.actualHours,
    isHPRDMet: p.isHrpdMet ?? false,
    nurses: (p.nurses || []).map((n: any) => ({
        id: n.id,
        name: n.name,
        shiftHours: n.shiftHours,
        schedulingRationale: n.schedulingRationale
    }))
});

const protoDayToUI = (d: ProtoDaySchedule): UIDaySchedule => ({
    date: d.date,
    shifts: (d.shifts || []).map(protoShiftToUI)
});
