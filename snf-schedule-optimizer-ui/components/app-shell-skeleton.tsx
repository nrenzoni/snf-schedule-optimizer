import React from "react";

export default function AppShellSkeleton() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto h-12 w-full max-w-xl animate-pulse rounded-2xl bg-white shadow-sm ring-1 ring-black/5" />
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
            <div className="mb-4 h-8 w-56 animate-pulse rounded bg-gray-100" />
            <div className="grid grid-cols-7 gap-2">
              {Array.from({ length: 14 }).map((_, idx) => (
                <div
                  key={idx}
                  className="h-24 animate-pulse rounded-xl bg-gray-100"
                />
              ))}
            </div>
          </section>

          <section className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
            <div className="h-6 w-40 animate-pulse rounded bg-gray-100" />
            <div className="h-24 animate-pulse rounded-xl bg-gray-100" />
            <div className="h-24 animate-pulse rounded-xl bg-gray-100" />
            <div className="h-24 animate-pulse rounded-xl bg-gray-100" />
          </section>
        </div>
      </div>
    </div>
  );
}
