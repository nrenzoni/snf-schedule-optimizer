"use client";

import React, {Suspense, useState} from "react";
import {Canvas} from "@react-three/fiber";
import {AnimatePresence, motion} from "framer-motion";
import { cn } from "@/lib/utils";
import LoaderScene from "@/components/three-d/loader-scene";
import useLoadingPhases, { LOADING_PHASES } from "@/components/three-d/use-loading-phases";
import useWarmupScheduler from "@/components/three-d/use-warmup-scheduler";

const LoaderSkeleton = () => (
  <div className="flex flex-col items-center gap-4">
    <div className="grid grid-cols-4 gap-2">
      {Array.from({ length: 16 }, (_, index) => (
        <div
          key={index}
          className="h-5 w-5 animate-pulse rounded-sm bg-primary/40"
          style={{ animationDelay: `${index * 60}ms` }}
        />
      ))}
    </div>
  </div>
);

export default function ThreeDAssemblyLoader({
  isLoading,
  mode = "fullscreen",
  progressPercent,
  message,
}: {
  isLoading: boolean;
  mode?: "fullscreen" | "inline";
  progressPercent?: number;
  message?: string;
}) {
  const msgIndex = useLoadingPhases(isLoading);
  const renderCanvas = useWarmupScheduler(mode);
  const [canvasReady, setCanvasReady] = useState(false);

  const displayMessage = message ?? LOADING_PHASES[msgIndex];
  const overlayClasses = mode === "fullscreen"
    ? "fixed inset-0 z-[100] bg-background/95"
    : "absolute inset-0 z-40 rounded-lg border border-border bg-background/60 backdrop-blur-sm";

  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          key="loader-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          className={cn(
            overlayClasses,
            "flex flex-col items-center justify-center overflow-hidden",
          )}
        >

          <div className={cn(
            "relative flex items-center justify-center",
            mode === "fullscreen" ? "h-[400px] w-full" : "h-full w-full min-h-[320px]",
          )}>
             {isLoading && renderCanvas ? (
                <Suspense fallback={<LoaderSkeleton />}>
                  <Canvas shadows dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
                    <Suspense fallback={null}>
                      <LoaderScene
                        isLoading={isLoading}
                        setReady={setCanvasReady}
                      />
                    </Suspense>
                  </Canvas>
                  {!canvasReady ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <LoaderSkeleton />
                    </div>
                  ) : null}
                </Suspense>
             ) : (
                <LoaderSkeleton />
             )}
           </div>

          <motion.div
             exit={{ opacity: 0, y: 10 }}
             transition={{ duration: 0.3 }}
             className={cn(
               "pointer-events-none absolute flex w-full flex-col items-center text-center",
               mode === "fullscreen" ? "bottom-1/4" : "bottom-8 px-6",
             )}
           >
             <div className="h-8 overflow-hidden relative w-full">
                 <AnimatePresence mode="wait">
                <motion.p
                    key={msgIndex}
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -20, opacity: 0 }}
                    className="text-lg font-semibold tracking-wide text-foreground"
                >
                    {displayMessage}
                 </motion.p>
                 </AnimatePresence>
             </div>

             <div className="mt-4 h-1 w-48 overflow-hidden rounded-full bg-muted">
                  <motion.div
                     className="h-full bg-primary"
                     initial={{ width: progressPercent !== undefined ? `${progressPercent}%` : "0%" }}
                     animate={{ width: progressPercent !== undefined ? `${Math.max(0, Math.min(100, progressPercent))}%` : "100%" }}
                     transition={
                       progressPercent !== undefined
                         ? { duration: 0.25, ease: "easeOut" }
                         : { duration: 8, ease: "linear", repeat: Infinity }
                     }
                  />
             </div>
           </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
