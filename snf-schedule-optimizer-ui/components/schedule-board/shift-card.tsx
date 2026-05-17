"use client";

// Shift Card (With Hover Portal)
import { ROLES, Shift, ViewMode } from "@/types/scheduler";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";
import { AlertCircle, DollarSign, Pin, Trash2, TriangleAlert } from "lucide-react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { motion } from "framer-motion";
import { iconButtonVariants } from "@/components/ui/styles";

export default function ShiftCard({
  shift,
  mode,
  isOverlay = false,
  dragDisabled = false,
  onDelete,
}: {
  shift: Shift;
  mode: ViewMode;
  isOverlay?: boolean;
  dragDisabled?: boolean;
  onDelete?: (shift: Shift) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: shift.id,
      data: { shift },
      disabled: dragDisabled,
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
        return "bg-amber-50 border-l-amber-400 text-amber-700";
      return "bg-card border-l-input text-foreground";
    }
    // Role Colors - Using white backgrounds with strong borders is cleaner
    if (shift.role === "RN")
      return "bg-accent border-l-green-600 text-green-600";
    if (shift.role === "LPN")
      return "bg-accent border-l-green-600 text-green-600";
    if (shift.role === "THERAPIST")
      return "bg-amber-50 border-l-amber-400 text-amber-700";
    return "bg-accent border-l-green-600 text-green-600";
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
        "group relative mx-auto flex h-full min-h-[3.25rem] w-[96%] select-none flex-col justify-center rounded-lg border border-l-4 text-[10px] shadow-none transition-shadow hover:shadow-sm",
        dragDisabled ? "cursor-not-allowed opacity-70" : "cursor-grab active:cursor-grabbing",
        getColor(),
        agencyStripe,
        // Remove 'scale' transforms from here, rely on dnd-kit or framer
        isOverlay &&
          "scale-105 bg-card opacity-90 shadow-md ring-2 ring-ring",
      )}
      >
      {onDelete ? (
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDelete(shift);
          }}
          className={cn(
            iconButtonVariants({ tone: "soft" }),
            "absolute right-1 top-1 z-10 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
          )}
          aria-label={`Delete ${shift.employeeName} from shift`}
        >
          <Trash2 size={12} className="text-red-600" />
        </button>
      ) : null}
      <div className="flex justify-between">
        <span>{shift.role}</span>
        <div className="flex items-center gap-1">
          {shift.pinned ? <Pin size={10} className="text-primary" aria-label="Pinned shift" /> : null}
          {shift.warnings?.length ? <TriangleAlert size={10} className="text-amber-600" aria-label="Shift has warnings" /> : null}
          {shift.isAgency && <AlertCircle size={10} className="text-red-600" aria-label="Agency shift" />}
        </div>
      </div>

      <div className="flex justify-between items-center font-bold px-1.5 leading-tight">
        <span>{shift.role}</span>
        {/* Visual Icons for Context */}
        <div className="flex gap-0.5">
          {shift.isAgency && <AlertCircle size={10} className="text-red-600" aria-label="Agency shift" />}
          {mode === "BUDGET" && shift.isOvertime && !shift.isAgency && (
            <DollarSign size={10} className="text-amber-600" aria-label="Overtime pay" />
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
      className="flex h-full min-h-14 items-stretch justify-center py-1"
    >
      {/* Hover Card logic remains same... */}
      {isInteractive ? (
        <HoverCard openDelay={200} closeDelay={0}>
          <HoverCardTrigger asChild>{renderContent()}</HoverCardTrigger>
          <HoverCardContent
            className="z-[9999] w-64 rounded-lg border-border bg-card p-3 text-foreground shadow-md"
            align="start"
          >
            <div className="space-y-2">
              <div className="flex justify-between border-b border-border pb-2">
                <span className="font-bold">{ROLES[shift.role].label}</span>
                <span
                  className={cn(
                    "px-1 rounded text-[10px]",
                     shift.isAgency ? "bg-red-600 text-white" : "bg-muted text-muted-foreground",
                  )}
                >
                  {shift.isAgency ? "AGENCY" : "STAFF"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-muted-foreground">Rate</div>
                  <div className="font-mono">
                    ${ROLES[shift.role].baseRate}/hr
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Status</div>
                  <div
                    className={
                      shift.isOvertime ? "text-amber-600" : "text-green-600"
                    }
                  >
                    {shift.isOvertime ? "Overtime" : "Standard"}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Draft</div>
                  <div className={shift.pinned ? "text-primary" : "text-muted-foreground"}>
                    {shift.pinned ? "Pinned" : "Server"}
                  </div>
                </div>
              </div>
              {shift.warnings?.length ? (
                <div className="rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-700">
                  {shift.warnings.join(" ")}
                </div>
              ) : null}
            </div>
          </HoverCardContent>
        </HoverCard>
      ) : (
        renderContent()
      )}
    </div>
  );
}
