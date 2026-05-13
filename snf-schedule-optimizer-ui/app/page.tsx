import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Brain,
  CalendarClock,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  TrendingDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function HomePage() {
  return (
    <main className="app-bg min-h-screen overflow-hidden text-slate-950">
      <div className="pointer-events-none absolute inset-0" />

      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="app-shell-card flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <CalendarClock size={20} />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight">SNF Schedule Optimizer</p>
              <p className="text-xs text-slate-500">AI-assisted staffing command center</p>
            </div>
          </div>
          <Link
            href="/schedule?tab=scheduling&view=timeline"
            className="app-button-primary hidden sm:inline-flex"
          >
            Launch Demo
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[1fr_0.92fr] lg:py-16">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-primary">
              <Sparkles size={16} className="text-primary" />
              Guided demo with live schedule reads and repeatable AI workflows
            </div>

            <h1 className="text-balance text-5xl font-semibold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
              Make SNF staffing feel predictable, compliant, and cost-aware.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">
              Explore a polished operating dashboard for schedule optimization,
              scenario analysis, and ML-driven staffing forecasts built for skilled
              nursing leaders.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/schedule?tab=scheduling&view=timeline"
                className="app-button-primary px-6 py-3"
              >
                Launch Interactive Demo
                <ArrowRight size={18} />
              </Link>
              <Link
                href="/schedule?tab=ml-forecasts"
                className="app-button-secondary px-6 py-3"
              >
                View Forecasts
                <Brain size={18} />
              </Link>
            </div>

            <div className="mt-10 grid gap-3 sm:grid-cols-3">
              {[
                [TrendingDown, "Labor Cost", "Surface overtime and agency risk before it hits payroll."],
                [ShieldCheck, "Compliance", "Flag unsafe moves while planners are still deciding."],
                [BarChart3, "Forecasting", "Translate census and staffing signals into next actions."],
              ].map(([Icon, title, copy]) => (
                <div
                  key={title as string}
                  className="app-card p-4"
                >
                  <Icon className="mb-3 text-primary" size={22} />
                  <h2 className="font-medium text-foreground">{title as string}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{copy as string}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-3 rounded-xl bg-primary/5" />
            <div className="app-shell-card relative overflow-hidden">
              <div className="border-b border-border bg-card px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="app-eyebrow">Demo Preview</p>
                    <h2 className="app-title mt-1 text-xl">Staffing Control Room</h2>
                  </div>
                  <div className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-green-600 ring-1 ring-primary/20">
                    96% coverage
                  </div>
                </div>
              </div>

              <div className="space-y-4 p-5">
                <div className="grid grid-cols-3 gap-3">
                  {[
                    ["Open Shifts", "7", "text-amber-600"],
                    ["Agency Hours", "-18%", "text-emerald-600"],
                    ["OT Risk", "Medium", "text-primary"],
                  ].map(([label, value, color]) => (
                    <div key={label} className="rounded-lg bg-card p-3 ring-1 ring-border">
                      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                      <p className={`mt-2 text-2xl font-black ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>

                <div className="app-card p-4 text-foreground">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timeline</p>
                      <p className="font-semibold">Unit A: RN Coverage</p>
                    </div>
                    <CheckCircle2 size={20} className="text-emerald-500" />
                  </div>
                  <div className="grid grid-cols-6 gap-2">
                    {Array.from({ length: 18 }).map((_, index) => (
                      <div
                        key={index}
                        className={cn("h-12 rounded-xl", 
                          index % 7 === 0
                            ? "bg-amber-50 ring-1 ring-amber-300/50"
                            : index % 5 === 0
                              ? "bg-accent ring-1 ring-primary/20"
                              : "bg-background ring-1 ring-border"
                        )}
                      />
                    ))}
                  </div>
                </div>

                <div className="app-callout-success p-4">
                  <p className="text-sm font-medium text-primary">AI recommendation</p>
                  <p className="mt-1 text-sm leading-6 text-foreground">
                    Convert 2 agency evening shifts to internal PRN coverage to lower projected labor variance.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
