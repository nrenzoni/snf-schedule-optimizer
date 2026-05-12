"use client";

import React from "react";
import { FlaskConical, RotateCcw, Sparkles } from "lucide-react";

export default function DemoModeBanner({
  onReset,
}: {
  onReset: () => void;
}) {
  return (
    <section className="mb-6 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-purple-50 p-5 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-indigo-700">
            <FlaskConical size={16} />
            Demo Mode
          </div>
          <h2 className="mt-2 text-xl font-semibold text-slate-900">
            Explore scheduling, scenarios, and forecasts with guided sample data.
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            Live schedule reads come from the configured API. Optimization and
            simulation actions still use demo behavior so the experience remains
            explorable even without a full backend workflow.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200">
            <Sparkles size={16} className="text-purple-600" />
            Try Optimize, Summary, and Timeline drag-drop
          </div>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            <RotateCcw size={16} />
            Reset Demo State
          </button>
        </div>
      </div>
    </section>
  );
}
