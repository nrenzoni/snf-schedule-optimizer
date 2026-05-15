"use client";

import React from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-card border-dashed border-amber-200/80 p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
            <AlertTriangle size={24} />
          </div>
          <h3 className="mt-4 text-xl font-semibold text-slate-900">
            {this.props.fallbackTitle ?? "Something went wrong"}
          </h3>
          <p className="mx-auto mt-2 max-w-lg text-sm text-slate-600">
            {this.state.error?.message ?? "An unexpected error occurred in this section."}
          </p>
          <button
            type="button"
            onClick={this.handleReset}
            className="app-button-primary mt-5"
          >
            <RefreshCcw size={16} />
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
