"use client";

import React from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="app-bg flex min-h-screen items-center justify-center px-4">
      <div className="app-card w-full max-w-lg p-8">
        <p className="app-eyebrow">
          App Error
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">
          The dashboard could not finish loading.
        </h1>
        <p className="mt-3 text-sm text-slate-600">
          Refresh the page or retry the last render. If the issue keeps
          happening, check the API connection and browser console.
        </p>
        <pre className="mt-6 overflow-x-auto rounded-lg bg-foreground p-4 text-xs text-background">
          {error.message}
        </pre>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={reset}
            className="app-button-primary"
          >
            Retry
          </button>
          <Link
            href="/"
            className="app-button-secondary"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
