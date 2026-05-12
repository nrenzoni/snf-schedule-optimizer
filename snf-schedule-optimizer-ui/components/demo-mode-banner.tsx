"use client";

import React from "react";
import { DatabaseZap, FlaskConical, Sparkles } from "lucide-react";

export default function DemoModeBanner() {
  return (
    <section
      data-testid="demo-mode-banner"
      className="mb-2 overflow-hidden rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-slate-950 via-indigo-950 to-slate-900 px-3 py-2 text-white shadow-lg shadow-indigo-950/10"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-cyan-200">
          <FlaskConical size={14} className="text-indigo-200" />
          Demo Mode
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-indigo-100 ring-1 ring-white/15">
            <DatabaseZap size={14} className="text-cyan-200" />
            Live API reads
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-indigo-100 ring-1 ring-white/15">
            <Sparkles size={14} className="text-purple-200" />
            Guided actions
          </div>
        </div>
      </div>
    </section>
  );
}
