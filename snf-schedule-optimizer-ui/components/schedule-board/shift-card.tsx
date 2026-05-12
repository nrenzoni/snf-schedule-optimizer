"use client";

// Shift Card (With Hover Portal)
import { ROLES, Shift, ViewMode } from "@/types/scheduler";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";
import { AlertCircle, DollarSign } from "lucide-react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { motion } from "framer-motion";

export default function ShiftCard({
  shift,
  mode,
  isOverlay = false,
}: {
  shift: Shift;
  mode: ViewMode;
  isOverlay?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: shift.id,
      data: { shift },
    });

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging && !isOverlay ? 0.3 : 1,
  };

  const isInteractive = !isDragging && !isOverlay;

  // This creates a subtle diagonal stripe effect for agency staff
  const agencyStripe = shift.isAgency
    ? "bg-[image:repeating-linear-gradient(45deg,transparent,transparent_5px,rgba(0,0,0,0.05)_5px,rgba(0,0,0,0.05)_10px)]"
    : "";

  const getColor = () => {
    if (mode === "BUDGET") {
      if (shift.isAgency) return "bg-red-50 border-l-red-500 text-red-700";
      if (shift.isOvertime)
        return "bg-[#FFF8E1] border-l-[#FBC02D] text-[#FBC02D]";
      return "bg-white border-l-[#CED4DA] text-[#212529]";
    }
    // Role Colors - Using white backgrounds with strong borders is cleaner
    if (shift.role === "RN")
      return "bg-[#DFFFEA] border-l-[#28A745] text-[#28A745]";
    if (shift.role === "LPN")
      return "bg-[#DFFFEA] border-l-[#28A745] text-[#28A745]";
    if (shift.role === "THERAPIST")
      return "bg-[#FFF8E1] border-l-[#FBC02D] text-[#FBC02D]";
    return "bg-[#DFFFEA] border-l-[#28A745] text-[#28A745]";
  };

  const renderContent = () => (
    <motion.div
      // KEY CHANGE: Unique ID tells Framer "This is the same card" across different parents
      layoutId={isOverlay ? undefined : shift.id}
      // Enable layout animation
      layout={!isOverlay}
      // Smooth spring animation for the "Undo" action
      transition={{
        type: "spring",
        stiffness: 400,
        damping: 30,
      }}
      className={cn(
        "group relative mx-auto flex h-[90%] w-[96%] cursor-grab select-none flex-col justify-center rounded-lg border border-l-4 text-[10px] shadow-none transition-shadow active:cursor-grabbing hover:shadow-sm",
        getColor(),
        agencyStripe,
        // Remove 'scale' transforms from here, rely on dnd-kit or framer
        isOverlay &&
          "scale-105 bg-white opacity-90 shadow-md ring-2 ring-[#168039]",
      )}
    >
      <div className="flex justify-between">
        <span>{shift.role}</span>
        {shift.isAgency && <AlertCircle size={10} className="text-red-600" />}
      </div>

      <div className="flex justify-between items-center font-bold px-1.5 leading-tight">
        <span>{shift.role}</span>
        {/* Visual Icons for Context */}
        <div className="flex gap-0.5">
          {shift.isAgency && <AlertCircle size={10} className="text-red-600" />}
          {mode === "BUDGET" && shift.isOvertime && !shift.isAgency && (
            <DollarSign size={10} className="text-amber-600" />
          )}
        </div>
      </div>
      {/* Optional: Show Label on Budget Mode */}
      {mode === "BUDGET" && (
        <div className="px-1.5 text-[9px] opacity-80 font-mono">
          {shift.isAgency ? "$$$" : shift.isOvertime ? "1.5x" : "1.0x"}
        </div>
      )}
    </motion.div>
  );

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="h-full flex items-center justify-center"
    >
      {/* Hover Card logic remains same... */}
      {isInteractive ? (
        <HoverCard openDelay={200} closeDelay={0}>
          <HoverCardTrigger asChild>{renderContent()}</HoverCardTrigger>
          <HoverCardContent
            className="z-[9999] w-64 rounded-lg border-[#E0E0E0] bg-white p-3 text-[#212529] shadow-md"
            align="start"
          >
            <div className="space-y-2">
              <div className="flex justify-between border-b border-[#E0E0E0] pb-2">
                <span className="font-bold">{ROLES[shift.role].label}</span>
                <span
                  className={cn(
                    "px-1 rounded text-[10px]",
                     shift.isAgency ? "bg-red-600 text-white" : "bg-[#E9EEF1] text-[#6C757D]",
                  )}
                >
                  {shift.isAgency ? "AGENCY" : "STAFF"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-[#6C757D]">Rate</div>
                  <div className="font-mono">
                    ${ROLES[shift.role].baseRate}/hr
                  </div>
                </div>
                <div>
                  <div className="text-[#6C757D]">Status</div>
                  <div
                    className={
                      shift.isOvertime ? "text-[#FBC02D]" : "text-[#28A745]"
                    }
                  >
                    {shift.isOvertime ? "Overtime" : "Standard"}
                  </div>
                </div>
              </div>
            </div>
          </HoverCardContent>
        </HoverCard>
      ) : (
        renderContent()
      )}
    </div>
  );
}
