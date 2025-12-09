import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function LoadingOverlay({ isVisible }: { isVisible: boolean }) {
  if (!isVisible) return null;

  return (
    <div
      className={cn(
        // 1. Positioning: Cover the entire parent container
        "absolute inset-0 z-50",

        // 2. Layout: Center the spinner
        "flex items-center justify-center",

        // 3. Visuals: Semi-transparent white + Blur effect
        "bg-white/50 backdrop-blur-sm",

        // 4. Interaction: Block clicks to underlying elements
        "cursor-wait",
      )}
    >
      <div className="bg-white p-4 rounded-xl shadow-xl border border-slate-100 animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          <span className="text-sm font-semibold text-slate-700">
            Refreshing...
          </span>
        </div>
      </div>
    </div>
  );
}
