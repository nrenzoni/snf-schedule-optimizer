import { useEffect, useRef, useState } from "react";
import { UICalendarDay } from "@/types/scheduling";

const TRANSITION_DURATION = 300;

interface UseModalTransitionArgs {
  selectedDay: UICalendarDay | null;
  isModalVisible: boolean;
}

interface UseModalTransitionResult {
  renderedDay: UICalendarDay | null;
  isVisible: boolean;
}

export default function useModalTransition({
  selectedDay,
  isModalVisible,
}: UseModalTransitionArgs): UseModalTransitionResult {
  const [renderedDay, setRenderedDay] = useState<UICalendarDay | null>(
    selectedDay,
  );
  const [isVisible, setIsVisible] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    if (selectedDay && isModalVisible) {
      frameRef.current = requestAnimationFrame(() => {
        setRenderedDay(selectedDay);
        frameRef.current = requestAnimationFrame(() => setIsVisible(true));
      });
      return;
    }

    frameRef.current = requestAnimationFrame(() => setIsVisible(false));
    closeTimerRef.current = setTimeout(() => {
      setRenderedDay(null);
      closeTimerRef.current = null;
    }, TRANSITION_DURATION);

    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [isModalVisible, selectedDay]);

  return { renderedDay, isVisible };
}
