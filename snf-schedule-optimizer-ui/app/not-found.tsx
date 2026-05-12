import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-sm ring-1 ring-black/5">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-indigo-600">
          Not Found
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">
          This route does not exist.
        </h1>
        <p className="mt-3 text-sm text-slate-600">
          Head back to the main scheduling demo to continue exploring the app.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
        >
          Open Dashboard
        </Link>
      </div>
    </div>
  );
}
