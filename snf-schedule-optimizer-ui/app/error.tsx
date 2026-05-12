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
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-sm ring-1 ring-black/5">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-indigo-600">
          App Error
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">
          The dashboard could not finish loading.
        </h1>
        <p className="mt-3 text-sm text-slate-600">
          Refresh the page or retry the last render. If the issue keeps
          happening, check the API connection and browser console.
        </p>
        <pre className="mt-6 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">
          {error.message}
        </pre>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={reset}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            Retry
          </button>
          <Link
            href="/"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
