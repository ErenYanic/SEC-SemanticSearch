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
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="mx-auto w-full max-w-md space-y-8 rounded-2xl border border-hairline bg-card/80 p-8 shadow-2xl backdrop-blur-xl">
        {/* Header */}
        <div className="space-y-3 text-center">
          <div className="flex items-center justify-center">
            <span
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent/70 text-accent-fg shadow-lg shadow-accent/20"
              aria-hidden="true"
            >
              <span className="text-base font-bold">S</span>
            </span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">
            EDGAR credentials required
          </h1>
          <p className="text-sm text-fg-muted">
            The SEC requires a name and email in every EDGAR request. Please
            enter your details to continue.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <label htmlFor="edgar-name" className="block space-y-2">
            <span className="text-sm font-medium text-fg">Full name</span>
            <input
              id="edgar-name"
              type="text"
              required
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              className="block w-full rounded-lg border border-hairline bg-card px-4 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-accent focus:ring-2 focus:ring-accent/25"
            />
          </label>
          <label htmlFor="edgar-email" className="block space-y-2">
            <span className="text-sm font-medium text-fg">Email address</span>
            <input
              id="edgar-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              className="block w-full rounded-lg border border-hairline bg-card px-4 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-accent focus:ring-2 focus:ring-accent/25"
            />
          </label>
          <Button type="submit" size="lg" className="w-full">
            Continue
          </Button>
        </form>

        {/* Privacy notice */}
        <p className="border-t border-hairline pt-4 text-center text-xs text-fg-subtle">
          Credentials stay in this tab · Never saved on the server
        </p>
      </div>
    </div>
  );
}
