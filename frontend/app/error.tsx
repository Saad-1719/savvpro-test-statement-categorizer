"use client";

// Shown instead of the page if a component crashes while rendering (Next.js error boundary).
// The user can try again without reloading, and nothing they uploaded leaves the browser.

import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-lg px-4 py-24 text-center">
      <h1 className="text-xl font-semibold text-slate-900">Something went wrong on this page</h1>
      <p className="mt-2 text-sm text-slate-600">
        The page hit an unexpected error. Your statement was not changed. Try again, or reload and upload it again.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Try again
      </button>
    </main>
  );
}
