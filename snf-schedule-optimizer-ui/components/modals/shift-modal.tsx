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
    ? "bg-black/60 opacity-100 backdrop-blur-sm pointer-events-auto"
    : "bg-black/0 opacity-0 backdrop-blur-0 pointer-events-none";

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
        className={`bg-white rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col md:flex-row transition-all duration-300 ease-out ${contentClasses}`}
      >
        {/* Left Panel (Shift Summary & Nurse List - Level 1) */}
        <div className="flex-grow p-4 md:p-6 flex flex-col min-w-0 md:min-w-[20rem]">
          <div className="flex justify-between items-start mb-4 border-b pb-3">
            <h3 id="shift-modal-title" className="text-xl md:text-2xl font-semibold text-gray-800">
              Schedule:{" "}
              {renderedDay.date
                ? modalDateFormatter.format(renderedDay.date)
                : renderedDay.dateString}
            </h3>
            <button
              onClick={closeModal}
              className="text-gray-400 hover:text-gray-600"
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
                className={`p-3 rounded-lg border transition duration-150 cursor-pointer 
                              ${selectedShift?.shiftName === shift.shiftName ? "ring-2 ring-indigo-500 shadow-lg bg-indigo-50" : "hover:shadow-md"}
                              ${shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? "bg-green-100" : ""}
                              ${!shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? "bg-red-100" : ""}`}
                aria-pressed={selectedShift?.shiftName === shift.shiftName}
              >
                <div className="flex justify-between items-center mb-1">
                  <p
                    className={`font-bold text-lg ${shift.isHPRDMet ? "text-green-700" : "text-red-700"}`}
                  >
                    {shift.shiftName} Shift:{" "}
                    {shift.isHPRDMet ? "MET" : "NOT MET"}
                  </p>
                  <span className="text-sm font-medium text-gray-500">
                    ({shift.nurses.length} Nurses)
                  </span>
                </div>
                <p className="text-xs text-gray-600">
                  Required: {shift.requiredHours.toFixed(1)} hrs | Actual:{" "}
                  {shift.actualHours.toFixed(1)} hrs
                </p>
              </button>
            ))}
          </div>

          {/* Nurse List (Active Shift) */}
          <h4 className="text-xl font-medium mb-3 border-t pt-3">
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
                    className={`p-3 border rounded-lg flex justify-between items-center cursor-pointer hover:bg-indigo-50 transition duration-150 
                                  ${selectedNurse?.id === nurse.id ? "bg-indigo-100 border-indigo-400" : "bg-white border-gray-200"}`}
                    aria-pressed={selectedNurse?.id === nurse.id}
                  >
                    <span className="font-medium text-gray-800">
                      {nurse.name}
                    </span>
                    <span className="text-sm font-semibold text-indigo-600">
                      {nurse.shiftHours} hrs
                    </span>
                  </button>
                ))
              ) : (
                <p className="text-gray-500 italic">
                  No nurses currently scheduled for this shift.
                </p>
              )
            ) : (
              <p className="text-gray-500 italic">
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
