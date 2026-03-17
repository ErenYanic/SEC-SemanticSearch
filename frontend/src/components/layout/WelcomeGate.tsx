"use client";

/**
 * Welcome screen gate — wraps the entire app layout.
 *
 * When the backend requires per-session EDGAR credentials
 * (`edgar_session_required: true` in status response), this component
 * renders a form instead of the app.  Once the user provides their
 * SEC EDGAR name and email, the credentials are stored in
 * `sessionStorage` and the app is shown.
 *
 * When session credentials are **not** required (Scenario A with
 * server-side env vars), the gate is transparent — children render
 * immediately.
 */

import { type FormEvent, useState, type ReactNode } from "react";
import { useEdgarSession } from "@/hooks/useEdgarSession";
import { useStatus } from "@/hooks/useStatus";
import { Button, Spinner } from "@/components/ui";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface WelcomeGateProps {
  children: ReactNode;
}

export function WelcomeGate({ children }: WelcomeGateProps) {
  const { data: status, isLoading, isError } = useStatus();
  const { isAuthenticated, login } = useEdgarSession();

  // If the status endpoint hasn't loaded yet, show a spinner.
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // On error, let the app through — the real pages have their own
  // error handling.  We don't want the Welcome gate to permanently
  // block the app if the backend is temporarily down.
  if (isError || !status) {
    return <>{children}</>;
  }

  // If the server says session credentials are not required, skip the gate.
  if (!status.edgar_session_required) {
    return <>{children}</>;
  }

  // If the user already has credentials in sessionStorage, let them through.
  if (isAuthenticated) {
    return <>{children}</>;
  }

  // Show the Welcome form.
  return <WelcomeForm onLogin={login} />;
}

// ---------------------------------------------------------------------------
// Welcome form (internal)
// ---------------------------------------------------------------------------

interface WelcomeFormProps {
  onLogin: (name: string, email: string) => void;
}

function WelcomeForm({ onLogin }: WelcomeFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (name.trim() && email.trim()) {
      onLogin(name, email);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="mx-auto w-full max-w-md space-y-8 rounded-xl border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-950">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            SEC Semantic Search
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            The SEC requires a name and email in every EDGAR request.
            Please enter your details to continue.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="edgar-name"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Full name
            </label>
            <input
              id="edgar-name"
              type="text"
              required
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
            />
          </div>
          <div>
            <label
              htmlFor="edgar-email"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Email address
            </label>
            <input
              id="edgar-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
            />
          </div>
          <Button type="submit" className="w-full">
            Continue
          </Button>
        </form>

        {/* Privacy notice */}
        <p className="text-center text-xs text-gray-500 dark:text-gray-500">
          Your credentials are stored only in this browser tab and are
          never saved on the server. Closing the tab clears them automatically.
        </p>
      </div>
    </div>
  );
}
