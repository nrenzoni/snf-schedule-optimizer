"use client";

import React from "react";
import { DatabaseZap, FlaskConical, Sparkles } from "lucide-react";

export default function DemoModeBanner() {
  return (
    <section
      data-testid="demo-mode-banner"
      className="app-card mb-4 overflow-hidden px-4 py-3 text-foreground"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-primary">
          <FlaskConical size={14} className="text-primary" />
          Demo Mode
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="app-chip-muted">
            <DatabaseZap size={14} className="text-primary" />
            Live API reads
          </div>
          <div className="app-chip-muted">
            <Sparkles size={14} className="text-primary" />
            Guided actions
          </div>
        </div>
      </div>
    </section>
  );
}
