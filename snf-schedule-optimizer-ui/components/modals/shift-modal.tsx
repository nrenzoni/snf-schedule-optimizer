import React, { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { UICalendarDay, UINurse, UIShift } from "@/types/scheduling";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  iconButtonVariants,
  selectableCardVariants,
} from "@/components/ui/styles";

interface ShiftModalProps {
  selectedDay: UICalendarDay | null;
  isModalVisible: boolean;
  closeModal: () => void;

  selectedShift: UIShift | null;
  selectedNurse: UINurse | null;
  selectShift: (shift: UIShift) => void;
  openNurseDetails: (nurse: UINurse) => void;

  // 2. REMOVE the specific panel props (remove, add, closeDetails)
  // 3. ADD children prop
  children?: ReactNode;
}

const TRANSITION_DURATION = 300;

export default function ShiftModal({
  selectedDay,
  isModalVisible,
  closeModal,
  selectedShift,
  selectedNurse,
  selectShift,
  openNurseDetails,
  children,
}: ShiftModalProps) {
  const [renderedDay, setRenderedDay] = useState<UICalendarDay | null>(
    selectedDay,
  );
  const [isVisible, setIsVisible] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameRef = useRef<number | null>(null);

  // Date formatter for the modal header (e.g., 'Nov 25, 2025')
  const modalDateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
    [],
  );

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

  // Return null early if data isn't ready
  if (!renderedDay || !renderedDay.schedule) return null;

  // --- Dynamic Class Control ---
  // Backdrop fade-in/out
  const backdropClasses = isVisible
    ? "bg-foreground/35 opacity-100 pointer-events-auto"
    : "bg-foreground/0 opacity-0 pointer-events-none";

  // Modal Content zoom/scale (to give depth illusion)
  const contentClasses = isVisible ? "scale-100 opacity-100" : "scale-95 opacity-0";

  return (
    // 1. BACKDROP CONTAINER: Handles the blur and opacity fade of the whole screen
    <div
      // Use the dynamic classes for fade control
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ease-out",
        backdropClasses,
      )}
      onClick={closeModal}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shift-modal-title"
    >
      {/* 2. MODAL CONTENT: Apply the zoom/scale transition */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "app-modal-surface flex h-[90vh] max-w-4xl min-h-0 flex-col transition-all duration-300 ease-out md:flex-row",
          contentClasses,
        )}
      >
        {/* Left Panel (Shift Summary & Nurse List - Level 1) */}
        <div className="flex min-h-0 min-w-0 flex-grow flex-col p-4 md:min-w-[20rem] md:p-6">
          <div className="mb-4 flex items-start justify-between border-b border-slate-200/70 pb-3">
            <h3 id="shift-modal-title" className="app-title text-xl md:text-2xl">
              Schedule:{" "}
              {renderedDay.date
                ? modalDateFormatter.format(renderedDay.date)
                : renderedDay.dateString}
            </h3>
            <button
              onClick={closeModal}
              className={iconButtonVariants({ tone: "soft" })}
              aria-label="Close shift details"
            >
              <X size={24} />
            </button>
          </div>

          <div className="mb-4 max-h-64 space-y-4 overflow-y-auto pr-1">
            {renderedDay.schedule.shifts.map((shift: UIShift) => (
              <button
                key={shift.shiftId}
                onClick={() => selectShift(shift)}
                type="button"
                  className={selectableCardVariants({
                    tone:
                      selectedShift?.shiftName === shift.shiftName
                        ? "success"
                        : shift.isHPRDMet
                          ? "success"
                          : "danger",
                    selected: selectedShift?.shiftName === shift.shiftName,
                  })}
                aria-pressed={selectedShift?.shiftName === shift.shiftName}
              >
                <div className="flex justify-between items-center mb-1">
                  <p
                    className={cn(
                      "text-lg font-semibold",
                      shift.isHPRDMet ? "text-green-600" : "text-red-700",
                    )}
                  >
                    {shift.shiftName} Shift:{" "}
                    {shift.isHPRDMet ? "MET" : "NOT MET"}
                  </p>
                  <span className="text-sm font-bold text-slate-500">
                    ({shift.nurses.length} Nurses)
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Required: {shift.requiredHours.toFixed(1)} hrs | Actual:{" "}
                  {shift.actualHours.toFixed(1)} hrs
                </p>
              </button>
            ))}
          </div>

          {/* Nurse List (Active Shift) */}
          <h4 className="mb-3 border-t border-slate-200/70 pt-3 text-xl font-black text-slate-900">
            Nurses for {selectedShift?.shiftName || "Selected"} Shift
          </h4>
          <div className="min-h-0 flex-grow space-y-2 overflow-y-auto pr-1">
            {selectedShift ? (
              selectedShift.nurses.length > 0 ? (
                selectedShift.nurses.map((nurse: UINurse) => (
                  <button
                    key={nurse.id}
                    onClick={() => openNurseDetails(nurse)}
                    type="button"
                    className={selectableCardVariants({
                      tone: selectedNurse?.id === nurse.id ? "success" : "neutral",
                      selected: selectedNurse?.id === nurse.id,
                    })}
                    aria-pressed={selectedNurse?.id === nurse.id}
                  >
                    <span className="font-bold text-slate-800">
                      {nurse.name}
                    </span>
                    <span className="text-sm font-medium text-primary">
                      {nurse.shiftHours} hrs
                    </span>
                  </button>
                ))
              ) : (
                <p className="italic text-slate-500">
                  No nurses currently scheduled for this shift.
                </p>
              )
            ) : (
              <p className="italic text-slate-500">
                Select a shift above to view the nurse list.
              </p>
            )}
          </div>
        </div>

        {/* 5. Right Panel Slot (Render Children) */}
        {/* If children exist (i.e. a nurse is selected), we render them here */}
        {children}
      </div>
    </div>
  );
}
