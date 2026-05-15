import { useMemo } from "react";
import { UICalendarDay, ScheduleMap } from "@/types/scheduling";
import {
  formatDateYYYYMMDD,
  FOURTEEN_DAYS_AHEAD,
  getStartOfWeek,
  TODAY,
  TODAY_STRING,
} from "@/utils/scheduling-logic";

interface UseScheduleCalendarParams {
  effectiveScheduleMap: ScheduleMap;
  isLoading: boolean;
  anchorDateStr: string;
  isTwoWeekView: boolean;
}

export function useScheduleCalendar({
  effectiveScheduleMap,
  isLoading,
  anchorDateStr,
  isTwoWeekView,
}: UseScheduleCalendarParams) {
  const currentViewAnchorDate = useMemo(
    () => new Date(anchorDateStr),
    [anchorDateStr],
  );

  const calendarDays = useMemo<UICalendarDay[]>(() => {
    if (isLoading) {
      return [];
    }

    const startDate = isTwoWeekView
      ? getStartOfWeek(TODAY)
      : (() => {
          const year = currentViewAnchorDate.getFullYear();
          const month = currentViewAnchorDate.getMonth();
          const firstDayOfMonth = new Date(year, month, 1);
          const startOffset = firstDayOfMonth.getDay();
          return new Date(year, month, 1 - startOffset);
        })();

    const iterationDay = new Date(startDate);
    const days: UICalendarDay[] = [];
    const todayStart = new Date(TODAY);
    todayStart.setHours(0, 0, 0, 0);
    const todayStartMs = todayStart.getTime();
    const windowEndMs = FOURTEEN_DAYS_AHEAD.getTime();
    const totalDaysToRender = isTwoWeekView ? 14 : 42;
    const contextMonth = currentViewAnchorDate.getMonth();

    for (let i = 0; i < totalDaysToRender; i++) {
      const dayDate = new Date(iterationDay);
      const dayDateString = formatDateYYYYMMDD(dayDate);
      const schedule = effectiveScheduleMap.get(dayDateString) || null;
      const dayDateMs = dayDate.getTime();

      let dayHPRDPercentage = 0;
      if (schedule) {
        const totalRequiredHours = schedule.shifts.reduce(
          (sum, shift) => sum + shift.requiredHours,
          0,
        );
        const totalActualHours = schedule.shifts.reduce(
          (sum, shift) => sum + shift.actualHours,
          0,
        );
        if (totalRequiredHours > 0) {
          dayHPRDPercentage = Math.min(
            100,
            (totalActualHours / totalRequiredHours) * 100,
          );
        }
      }

      const isWithinWindow =
        dayDateMs >= todayStartMs && dayDateMs <= windowEndMs;
      const isSelectable = isTwoWeekView
        ? isWithinWindow
        : dayDate.getMonth() === contextMonth && isWithinWindow;

      days.push({
        coverage: 0,
        isPadding: false,
        date: dayDate,
        dateString: dayDateString,
        dayOfMonth: dayDate.getDate(),
        isToday: dayDateString === TODAY_STRING,
        isCurrentMonth:
          !isTwoWeekView && dayDate.getMonth() === contextMonth,
        isSelectable,
        schedule,
        dayHPRDPercentage,
      });

      iterationDay.setDate(iterationDay.getDate() + 1);
    }
    return days;
  }, [currentViewAnchorDate, effectiveScheduleMap, isTwoWeekView, isLoading]);

  return { calendarDays, currentViewAnchorDate };
}
