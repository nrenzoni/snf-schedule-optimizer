import React from "react";
import { AlertCircle, RefreshCcw } from "lucide-react";

export default function DashboardEmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="app-card border-dashed border-indigo-200/80 p-8 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-accent text-primary">
        <AlertCircle size={24} />
      </div>
      <h3 className="mt-4 text-xl font-semibold text-slate-900">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm text-slate-600">{description}</p>
      {onAction && actionLabel ? (
        <button
          type="button"
          onClick={onAction}
          className="app-button-primary mt-5"
        >
          <RefreshCcw size={16} />
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
