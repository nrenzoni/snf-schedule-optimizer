import React from "react";

export default function AppShellSkeleton() {
  return (
    <div className="app-bg min-h-screen" role="status" aria-live="polite" aria-busy="true">
      <div className="mx-auto flex min-h-screen w-full max-w-[1800px] flex-col gap-6 p-3 md:p-4">
        <div className="app-shell-card overflow-hidden p-4">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-center">
            <div className="space-y-3">
              <div className="h-3 w-28 animate-pulse rounded-full bg-muted" />
              <div className="h-8 w-64 animate-pulse rounded-lg bg-muted" />
              <div className="h-4 w-72 animate-pulse rounded-full bg-muted" />
            </div>

            <div className="app-soft-panel mx-auto w-full max-w-md px-4 py-3 sm:min-w-[320px]">
              <div className="space-y-2">
                <div className="h-4 w-full animate-pulse rounded-full bg-muted" />
                <div className="h-4 w-2/3 animate-pulse rounded-full bg-muted" />
              </div>
            </div>

            <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
              {Array.from({ length: 3 }).map((_, idx) => (
                <div
                  key={idx}
                  className="h-10 w-32 animate-pulse rounded-xl bg-muted"
                />
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          {Array.from({ length: 5 }).map((_, idx) => (
            <div
              key={idx}
              className="h-9 w-28 animate-pulse rounded-xl bg-muted"
            />
          ))}
        </div>

        <section className="app-card overflow-hidden p-4">
          <div className="mb-4 flex items-center justify-between gap-3 border-b border-border pb-4">
            <div className="h-6 w-40 animate-pulse rounded-lg bg-muted" />
            <div className="h-8 w-44 animate-pulse rounded-xl bg-muted" />
          </div>

          <div className="grid grid-cols-[180px_repeat(6,minmax(0,1fr))] gap-2">
            {Array.from({ length: 7 }).map((_, idx) => (
              <div
                key={`header-${idx}`}
                className="h-12 animate-pulse rounded-lg bg-muted"
              />
            ))}
            {Array.from({ length: 24 }).map((_, idx) => (
              <div
                key={`cell-${idx}`}
                className="h-16 animate-pulse rounded-lg bg-muted/80"
              />
            ))}
          </div>
        </section>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="app-card p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-3">
                  <div className="h-3 w-24 animate-pulse rounded-full bg-muted" />
                  <div className="h-8 w-20 animate-pulse rounded-lg bg-muted" />
                </div>
                <div className="h-10 w-10 animate-pulse rounded-xl bg-muted" />
              </div>
              <div className="mt-3 h-4 w-40 animate-pulse rounded-full bg-muted" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
