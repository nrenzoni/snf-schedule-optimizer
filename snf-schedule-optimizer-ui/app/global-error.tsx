"use client";

import { AlertTriangle, RefreshCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body className="m-0 flex min-h-screen items-center justify-center bg-[#f4f6f8] font-sans antialiased">
        <div className="app-card border-dashed border-red-200/60 p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-red-50 text-red-600">
            <AlertTriangle size={24} />
          </div>
          <h1 className="mt-4 text-xl font-semibold text-slate-900">
            Application Error
          </h1>
          <p className="mx-auto mt-2 max-w-lg text-sm text-slate-600">
            {error.message ?? "A critical error occurred. Please try again."}
          </p>
          <button
            type="button"
            onClick={reset}
            className="app-button-primary mt-5 inline-flex items-center gap-2 rounded-lg border-0 bg-[#168039] px-5 py-2.5 text-sm font-medium text-white"
          >
            <RefreshCcw size={16} />
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
