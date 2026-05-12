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
    <main className="min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-[-16rem] h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-indigo-500/30 blur-3xl" />
        <div className="absolute right-[-10rem] top-40 h-[28rem] w-[28rem] rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute bottom-[-14rem] left-[-8rem] h-[32rem] w-[32rem] rounded-full bg-emerald-400/10 blur-3xl" />
      </div>

      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 shadow-2xl shadow-black/20 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-950 shadow-lg shadow-indigo-500/20">
              <CalendarClock size={20} />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight">SNF Schedule Optimizer</p>
              <p className="text-xs text-slate-400">AI-assisted staffing command center</p>
            </div>
          </div>
          <Link
            href="/schedule?tab=scheduling&view=timeline"
            className="hidden rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-indigo-100 sm:inline-flex"
          >
            Launch Demo
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[1fr_0.92fr] lg:py-16">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-300/30 bg-indigo-400/10 px-3 py-1.5 text-sm font-semibold text-indigo-100 shadow-lg shadow-indigo-950/30">
              <Sparkles size={16} className="text-cyan-200" />
              Guided demo with live schedule reads and repeatable AI workflows
            </div>

            <h1 className="text-balance text-5xl font-black tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
              Make SNF staffing feel predictable, compliant, and cost-aware.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              Explore a polished operating dashboard for schedule optimization,
              scenario analysis, and ML-driven staffing forecasts built for skilled
              nursing leaders.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/schedule?tab=scheduling&view=timeline"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-indigo-400 px-6 py-3 text-sm font-black text-slate-950 shadow-xl shadow-indigo-500/30 transition hover:-translate-y-0.5 hover:bg-cyan-300"
              >
                Launch Interactive Demo
                <ArrowRight size={18} />
              </Link>
              <Link
                href="/schedule?tab=ml-forecasts"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/5 px-6 py-3 text-sm font-bold text-white backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/10"
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
                  className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 shadow-xl shadow-black/10 backdrop-blur"
                >
                  <Icon className="mb-3 text-cyan-200" size={22} />
                  <h2 className="font-bold text-white">{title as string}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{copy as string}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-4 rounded-[2rem] bg-gradient-to-br from-indigo-400/30 via-cyan-300/10 to-emerald-300/20 blur-2xl" />
            <div className="relative overflow-hidden rounded-[2rem] border border-white/15 bg-slate-900/90 shadow-2xl shadow-black/40 backdrop-blur">
              <div className="border-b border-white/10 bg-white/[0.04] px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-200">Demo Preview</p>
                    <h2 className="mt-1 text-xl font-black tracking-tight">Staffing Control Room</h2>
                  </div>
                  <div className="rounded-full bg-emerald-400/15 px-3 py-1 text-xs font-bold text-emerald-200 ring-1 ring-emerald-300/20">
                    96% coverage
                  </div>
                </div>
              </div>

              <div className="space-y-4 p-5">
                <div className="grid grid-cols-3 gap-3">
                  {[
                    ["Open Shifts", "7", "text-amber-200"],
                    ["Agency Hours", "-18%", "text-emerald-200"],
                    ["OT Risk", "Medium", "text-cyan-200"],
                  ].map(([label, value, color]) => (
                    <div key={label} className="rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
                      <p className={`mt-2 text-2xl font-black ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-2xl bg-white p-4 text-slate-950 shadow-2xl">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Timeline</p>
                      <p className="font-black">Unit A: RN Coverage</p>
                    </div>
                    <CheckCircle2 size={20} className="text-emerald-500" />
                  </div>
                  <div className="grid grid-cols-6 gap-2">
                    {Array.from({ length: 18 }).map((_, index) => (
                      <div
                        key={index}
                        className={`h-12 rounded-xl ${
                          index % 7 === 0
                            ? "bg-amber-100 ring-1 ring-amber-200"
                            : index % 5 === 0
                              ? "bg-indigo-100 ring-1 ring-indigo-200"
                              : "bg-slate-100 ring-1 ring-slate-200"
                        }`}
                      />
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-4">
                  <p className="text-sm font-bold text-cyan-100">AI recommendation</p>
                  <p className="mt-1 text-sm leading-6 text-slate-300">
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
