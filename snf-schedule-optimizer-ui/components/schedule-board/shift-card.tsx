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

  const color =
    mode === "BUDGET"
      ? shift.isAgency
        ? "bg-red-50 border-l-red-500 text-red-900"
        : shift.isOvertime
          ? "bg-amber-50 border-l-amber-500 text-amber-900"
          : "bg-white border-l-slate-400 text-slate-700"
      : shift.role === "RN"
        ? "bg-blue-50/50 border-l-blue-500 text-blue-700"
        : "bg-purple-50/50 border-l-purple-500 text-purple-700";

  const getColor = () => {
    if (mode === "BUDGET") {
      if (shift.isAgency) return "bg-red-50 border-l-red-500 text-red-900";
      if (shift.isOvertime)
        return "bg-amber-50 border-l-amber-500 text-amber-900";
      return "bg-white border-l-slate-400 text-slate-700";
    }
    // Role Colors - Using white backgrounds with strong borders is cleaner
    if (shift.role === "RN")
      return "bg-blue-50/50 border-l-blue-500 text-blue-700";
    if (shift.role === "LPN")
      return "bg-emerald-50/50 border-l-emerald-500 text-emerald-700";
    if (shift.role === "THERAPIST")
      return "bg-orange-50/50 border-l-orange-500 text-orange-700";
    return "bg-purple-50/50 border-l-purple-500 text-purple-700";
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
        "group relative h-[90%] w-[96%] mx-auto rounded-md shadow-sm border border-l-4 cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow select-none flex flex-col justify-center text-[10px]",
        getColor(),
        agencyStripe,
        // Remove 'scale' transforms from here, rely on dnd-kit or framer
        isOverlay &&
          "shadow-xl ring-2 ring-primary bg-white opacity-90 scale-105",
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
            className="w-64 p-3 bg-slate-900 border-slate-700 text-slate-100 z-[9999]"
            align="start"
          >
            <div className="space-y-2">
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="font-bold">{ROLES[shift.role].label}</span>
                <span
                  className={cn(
                    "px-1 rounded text-[10px]",
                    shift.isAgency ? "bg-red-600" : "bg-slate-700",
                  )}
                >
                  {shift.isAgency ? "AGENCY" : "STAFF"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-slate-400">Rate</div>
                  <div className="font-mono">
                    ${ROLES[shift.role].baseRate}/hr
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">Status</div>
                  <div
                    className={
                      shift.isOvertime ? "text-amber-400" : "text-emerald-400"
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
