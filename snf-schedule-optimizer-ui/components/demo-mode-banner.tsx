"use client";

import React from "react";
import { DatabaseZap, FlaskConical, RotateCcw, Sparkles } from "lucide-react";

export default function DemoModeBanner({
  onReset,
}: {
  onReset: () => void;
}) {
  return (
    <section
      data-testid="demo-mode-banner"
      className="mb-5 overflow-hidden rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-slate-950 via-indigo-950 to-slate-900 px-5 py-4 text-white shadow-xl shadow-indigo-950/15"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-cyan-200">
            <FlaskConical size={14} className="text-indigo-200" />
            Demo Mode
          </div>
          <h2 className="mt-1 text-lg font-black tracking-tight text-white">
            Explore scheduling, scenarios, and forecasts with guided sample data.
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-300">
            Live schedule reads come from the API; optimization and simulation
            actions remain guided for a repeatable demo.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-indigo-100 ring-1 ring-white/15">
            <DatabaseZap size={14} className="text-cyan-200" />
            Live API reads
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-indigo-100 ring-1 ring-white/15">
            <Sparkles size={14} className="text-purple-200" />
            Try Optimize, Summary, drag-drop
          </div>
          <button
            data-testid="reset-demo-state"
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-black text-slate-950 shadow-lg shadow-black/20 transition hover:bg-cyan-100"
          >
            <RotateCcw size={14} />
            Reset Demo State
          </button>
        </div>
      </div>
    </section>
  );
}
