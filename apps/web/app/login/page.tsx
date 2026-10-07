"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError, api, setToken } from "@/lib/api";

interface LoginResponse {
  token: string;
  expires_at: string;
  user: { id: string; email: string };
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email }),
        redirectOn401: false,
      });
      setToken(data.token);
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError) setError(err);
      else
        setError(
          new ApiError(0, {
            code: "NETWORK_ERROR",
            message: "Could not reach the JARVIS API.",
            what_failed: "Login request",
            what_happened: "The API did not respond.",
            what_next: "Start the API (scripts/dev.sh) and retry.",
          }),
        );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-2xl font-semibold tracking-[0.35em] text-amber-300">
          JARVIS
        </h1>
        <p className="mb-8 text-center text-sm text-zinc-500">
          Personal AI operating system — Phase 1
        </p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm text-zinc-400">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-600"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-amber-600 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-amber-500 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {error ? (
          <div className="mt-4 rounded-md border border-red-900 bg-red-950/40 p-3 text-xs text-red-300">
            <p className="font-semibold">{error.code}</p>
            <p className="mt-1">{error.whatHappened}</p>
            <p className="mt-1 text-red-400">{error.whatNext}</p>
          </div>
        ) : null}

        <p className="mt-6 text-center text-[11px] leading-relaxed text-zinc-600">
          Development sign-in (AUTH_MODE=dev). Supabase Auth is not implemented yet.
        </p>
      </div>
    </main>
  );
}
