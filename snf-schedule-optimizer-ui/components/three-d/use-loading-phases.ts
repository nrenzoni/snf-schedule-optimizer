import { useState, useEffect } from "react";

export const LOADING_PHASES = [
  "Ingesting staff constraints...",
  "Calculating geometric optimality...",
  "Balancing RN/LPN ratios...",
  "Fitting puzzle pieces together...",
  "Solving linear programming variables...",
  "Checking overtime constraints...",
  "Finalizing the golden schedule...",
];

export default function useLoadingPhases(isLoading: boolean) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    if (!isLoading) return;
    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % LOADING_PHASES.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [isLoading]);

  return msgIndex;
}
