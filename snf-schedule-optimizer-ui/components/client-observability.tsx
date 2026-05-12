"use client";

import { useEffect } from "react";

export default function ClientObservability() {
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      console.error("[client-error]", event.message, event.error);
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error("[client-rejection]", event.reason);
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  return null;
}
