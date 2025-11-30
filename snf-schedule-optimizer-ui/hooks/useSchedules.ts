import {useCallback, useEffect, useState} from 'react';
import {DaySchedule as UIDaySchedule} from '@/types/scheduling';
import {formatDate, getStartOfMonth} from '@/utils/scheduling-logic';
import {schedulingClient} from "@/api/scheduling-client";
import {DaySchedule as ProtoDaySchedule} from "@/gen/schema/scheduling_pb";

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
        fetchSchedule(currentDate);
    }, [currentDate, fetchSchedule]);

    return { schedules, isLoading, fetchSchedule };
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

type ScheduleMap = Map<string, UIDaySchedule>;

