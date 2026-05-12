"use client";

import React from "react";
import { FlaskConical, RotateCcw, Sparkles } from "lucide-react";

export default function DemoModeBanner({
  onReset,
}: {
  onReset: () => void;
}) {
  return (
    <section
      data-testid="demo-mode-banner"
      className="mb-4 rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-purple-50 px-4 py-3 shadow-sm"
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-indigo-700">
            <FlaskConical size={14} />
            Demo Mode
          </div>
          <h2 className="mt-1 text-base font-semibold text-slate-900">
            Explore scheduling, scenarios, and forecasts with guided sample data.
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-600">
            Live schedule reads come from the API; optimization and simulation
            actions remain guided for a repeatable demo.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            <Sparkles size={14} className="text-purple-600" />
            Try Optimize, Summary, and Timeline drag-drop
          </div>
          <button
            data-testid="reset-demo-state"
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-700"
          >
            <RotateCcw size={14} />
            Reset Demo State
          </button>
        </div>
      </div>
    </section>
  );
}
