import { useState, useEffect } from "react";

export default function useWarmupScheduler(mode: "fullscreen" | "inline") {
  const [renderCanvas, setRenderCanvas] = useState(mode === "fullscreen");

  useEffect(() => {
    if (renderCanvas) {
      return;
    }

    const scheduleWarmup = (callback: () => void) => {
      if (typeof window === "undefined") {
        return;
      }

      if (typeof window.requestIdleCallback === "function") {
        const handle = window.requestIdleCallback(callback, { timeout: 1500 });
        return () => {
          if (typeof window.cancelIdleCallback === "function") {
            window.cancelIdleCallback(handle);
          }
        };
      }

      const timeout = window.setTimeout(callback, 250);
      return () => window.clearTimeout(timeout);
    };

    const cleanup = scheduleWarmup(() => setRenderCanvas(true));
    return () => cleanup?.();
  }, [renderCanvas]);

  return renderCanvas;
}
