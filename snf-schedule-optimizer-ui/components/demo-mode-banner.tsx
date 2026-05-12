"use client";

import React from "react";
import { DatabaseZap, FlaskConical, Sparkles } from "lucide-react";

export default function DemoModeBanner() {
  return (
    <section
      data-testid="demo-mode-banner"
      className="mb-4 overflow-hidden rounded-lg border border-[#E0E0E0] bg-white px-4 py-3 text-[#212529] shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-[#168039]">
          <FlaskConical size={14} className="text-[#168039]" />
          Demo Mode
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="inline-flex items-center gap-2 rounded-lg bg-[#F4F6F8] px-3 py-1.5 text-xs font-medium text-[#6C757D] ring-1 ring-[#E0E0E0]">
            <DatabaseZap size={14} className="text-[#168039]" />
            Live API reads
          </div>
          <div className="inline-flex items-center gap-2 rounded-lg bg-[#F4F6F8] px-3 py-1.5 text-xs font-medium text-[#6C757D] ring-1 ring-[#E0E0E0]">
            <Sparkles size={14} className="text-[#168039]" />
            Guided actions
          </div>
        </div>
      </div>
    </section>
  );
}
