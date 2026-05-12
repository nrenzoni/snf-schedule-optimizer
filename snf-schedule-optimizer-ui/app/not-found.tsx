import Link from "next/link";

export default function NotFound() {
  return (
    <div className="app-bg flex min-h-screen items-center justify-center px-4">
      <div className="app-card w-full max-w-lg p-8">
        <p className="app-eyebrow">
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
          className="app-button-primary mt-6"
        >
          Open Dashboard
        </Link>
      </div>
    </div>
  );
}
