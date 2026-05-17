"use client";

import React, { ReactNode } from "react";
import { UICalendarDay, UINurse, UIShift } from "@/types/scheduling";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  iconButtonVariants,
  selectableCardVariants,
} from "@/components/ui/styles";
import useModalTransition from "@/hooks/use-modal-transition";

interface ShiftModalProps {
  selectedDay: UICalendarDay | null;
  isModalVisible: boolean;
  closeModal: () => void;

  selectedShift: UIShift | null;
  selectedNurse: UINurse | null;
  selectShift: (shift: UIShift) => void;
  openNurseDetails: (nurse: UINurse) => void;

  children?: ReactNode;
}

const modalDateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

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
  const { renderedDay, isVisible } = useModalTransition({
    selectedDay,
    isModalVisible,
  });

  if (!renderedDay || !renderedDay.schedule) return null;

  const backdropClasses = isVisible
    ? "bg-foreground/35 opacity-100 pointer-events-auto"
    : "bg-foreground/0 opacity-0 pointer-events-none";

  const contentClasses = isVisible ? "scale-100 opacity-100" : "scale-95 opacity-0";

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ease-out",
        backdropClasses,
      )}
      onClick={closeModal}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shift-modal-title"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "app-modal-surface flex h-[90vh] max-w-4xl min-h-0 flex-col transition-all duration-300 ease-out md:flex-row",
          contentClasses,
        )}
      >
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

        {children}
      </div>
    </div>
  );
}
