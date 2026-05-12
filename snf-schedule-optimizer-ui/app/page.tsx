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

export default function HomePage() {
  return (
    <main className="app-bg min-h-screen overflow-hidden text-slate-950">
      <div className="pointer-events-none absolute inset-0" />

      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="app-shell-card flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#168039] text-white">
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
            <div className="mb-6 inline-flex items-center gap-2 rounded-lg border border-[#E0E0E0] bg-white px-3 py-1.5 text-sm font-medium text-[#168039]">
              <Sparkles size={16} className="text-[#168039]" />
              Guided demo with live schedule reads and repeatable AI workflows
            </div>

            <h1 className="text-balance text-5xl font-semibold tracking-tight text-[#212529] sm:text-6xl lg:text-7xl">
              Make SNF staffing feel predictable, compliant, and cost-aware.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-[#6C757D]">
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
                  <Icon className="mb-3 text-[#168039]" size={22} />
                  <h2 className="font-medium text-[#212529]">{title as string}</h2>
                  <p className="mt-2 text-sm leading-6 text-[#6C757D]">{copy as string}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-3 rounded-xl bg-[#168039]/5" />
            <div className="app-shell-card relative overflow-hidden">
              <div className="border-b border-[#E0E0E0] bg-white px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="app-eyebrow">Demo Preview</p>
                    <h2 className="app-title mt-1 text-xl">Staffing Control Room</h2>
                  </div>
                  <div className="rounded-lg bg-[#DFFFEA] px-3 py-1 text-xs font-medium text-[#28A745] ring-1 ring-[#28A745]/30">
                    96% coverage
                  </div>
                </div>
              </div>

              <div className="space-y-4 p-5">
                <div className="grid grid-cols-3 gap-3">
                  {[
                    ["Open Shifts", "7", "text-amber-600"],
                    ["Agency Hours", "-18%", "text-emerald-600"],
                    ["OT Risk", "Medium", "text-[#168039]"],
                  ].map(([label, value, color]) => (
                    <div key={label} className="rounded-lg bg-white p-3 ring-1 ring-[#E0E0E0]">
                      <p className="text-[10px] font-medium uppercase tracking-wide text-[#6C757D]">{label}</p>
                      <p className={`mt-2 text-2xl font-black ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-[#E0E0E0] bg-white p-4 text-[#212529] shadow-sm">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-[#6C757D]">Timeline</p>
                      <p className="font-semibold">Unit A: RN Coverage</p>
                    </div>
                    <CheckCircle2 size={20} className="text-emerald-500" />
                  </div>
                  <div className="grid grid-cols-6 gap-2">
                    {Array.from({ length: 18 }).map((_, index) => (
                      <div
                        key={index}
                        className={`h-12 rounded-xl ${
                          index % 7 === 0
                            ? "bg-[#FFF8E1] ring-1 ring-[#FBC02D]/40"
                            : index % 5 === 0
                              ? "bg-[#DFFFEA] ring-1 ring-[#28A745]/40"
                              : "bg-[#F4F6F8] ring-1 ring-[#E0E0E0]"
                        }`}
                      />
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-[#28A745]/30 bg-[#DFFFEA] p-4">
                  <p className="text-sm font-medium text-[#168039]">AI recommendation</p>
                  <p className="mt-1 text-sm leading-6 text-[#212529]">
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
