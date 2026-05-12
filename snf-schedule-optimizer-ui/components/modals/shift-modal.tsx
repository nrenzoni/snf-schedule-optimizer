import React, { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { UICalendarDay, UINurse, UIShift } from "@/types/scheduling";
import { X } from "lucide-react";

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
    ? "bg-[#212529]/35 opacity-100 pointer-events-auto"
    : "bg-[#212529]/0 opacity-0 pointer-events-none";

  // Modal Content zoom/scale (to give depth illusion)
  const contentClasses = isVisible ? "scale-100 opacity-100" : "scale-95 opacity-0";

  return (
    // 1. BACKDROP CONTAINER: Handles the blur and opacity fade of the whole screen
    <div
      // Use the dynamic classes for fade control
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ease-out ${backdropClasses}`}
      onClick={closeModal}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shift-modal-title"
    >
      {/* 2. MODAL CONTENT: Apply the zoom/scale transition */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={`flex h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-[#E0E0E0] bg-white shadow-md transition-all duration-300 ease-out md:flex-row ${contentClasses}`}
      >
        {/* Left Panel (Shift Summary & Nurse List - Level 1) */}
        <div className="flex min-w-0 flex-grow flex-col p-4 md:min-w-[20rem] md:p-6">
          <div className="mb-4 flex items-start justify-between border-b border-slate-200/70 pb-3">
            <h3 id="shift-modal-title" className="app-title text-xl md:text-2xl">
              Schedule:{" "}
              {renderedDay.date
                ? modalDateFormatter.format(renderedDay.date)
                : renderedDay.dateString}
            </h3>
            <button
              onClick={closeModal}
              className="rounded-lg p-1 text-[#6C757D] hover:bg-[#E9EEF1] hover:text-[#212529]"
              aria-label="Close shift details"
            >
              <X size={24} />
            </button>
          </div>

          <div className="space-y-4 mb-4">
            {renderedDay.schedule.shifts.map((shift: UIShift) => (
              <button
                key={shift.shiftName}
                onClick={() => selectShift(shift)}
                type="button"
                  className={`cursor-pointer rounded-lg border p-3 text-left transition duration-150 
                              ${selectedShift?.shiftName === shift.shiftName ? "border-[#168039] bg-[#DFFFEA] ring-1 ring-[#168039]" : "hover:border-[#28A745]"}
                              ${shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? "border-[#28A745] bg-[#DFFFEA]" : ""}
                              ${!shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? "border-red-200 bg-red-50" : ""}`}
                aria-pressed={selectedShift?.shiftName === shift.shiftName}
              >
                <div className="flex justify-between items-center mb-1">
                  <p
                    className={`text-lg font-semibold ${shift.isHPRDMet ? "text-[#28A745]" : "text-red-700"}`}
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
          <div className="overflow-y-auto space-y-2 flex-grow pr-1">
            {selectedShift ? (
              selectedShift.nurses.length > 0 ? (
                selectedShift.nurses.map((nurse: UINurse) => (
                  <button
                    key={nurse.id}
                    onClick={() => openNurseDetails(nurse)}
                    type="button"
                    className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 transition duration-150 hover:bg-[#DFFFEA] 
                                  ${selectedNurse?.id === nurse.id ? "border-[#168039] bg-[#DFFFEA]" : "border-[#E0E0E0] bg-white"}`}
                    aria-pressed={selectedNurse?.id === nurse.id}
                  >
                    <span className="font-bold text-slate-800">
                      {nurse.name}
                    </span>
                    <span className="text-sm font-medium text-[#168039]">
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
