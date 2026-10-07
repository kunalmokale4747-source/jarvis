"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import StatusPill from "@/components/StatusPill";
import { API_URL, api } from "@/lib/api";
import type { MetaResponse } from "@/lib/types";

export default function SettingsPage() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<MetaResponse>("/api/v1/meta")
      .then(setMeta)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-zinc-100">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Full settings arrive with later phases. What exists today is shown below.
        </p>
      </header>

      <section className="rounded-xl border border-zinc-800 p-4 text-sm">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">Runtime</h2>
        <dl className="mt-3 space-y-2">
          <Row term="App" value={meta ? `${meta.name} v${meta.version}` : "…"} />
          <Row term="Phase" value={meta ? String(meta.phase) : "…"} />
          <Row term="Auth mode" value={meta?.auth_mode ?? "…"} />
          <Row term="API URL" value={API_URL} />
        </dl>
        <p className="mt-3 text-[11px] text-zinc-600">
          Supabase Auth, notification channels, permission overrides and schedules are configured
          in later phases.
        </p>
      </section>

      <section className="rounded-xl border border-zinc-800 p-4 text-sm">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">Integrations</h2>
        {error ? <p className="mt-3 text-red-400">{error}</p> : null}
        <ul className="mt-3 space-y-2">
          {meta
            ? Object.entries(meta.integrations).map(([name, info]) => (
                <li key={name} className="flex items-center justify-between gap-2">
                  <span className="text-zinc-300">{name}</span>
                  <span className="flex items-center gap-2">
                    <span className="text-[11px] text-zinc-600">Phase {info.phase}</span>
                    <StatusPill
                      label={info.status.replace("_", " ")}
                      state={info.status === "connected" ? "on" : info.status === "error" ? "off" : "warn"}
                    />
                  </span>
                </li>
              ))
            : null}
          {!meta && !error ? <li className="text-zinc-500">Loading…</li> : null}
        </ul>
        <p className="mt-3 text-[11px] text-zinc-600">
          No integration is connected in Phase 1 — nothing here is simulated.
        </p>
      </section>

      <section className="rounded-xl border border-zinc-800 p-4 text-sm">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">Your data</h2>
        <Link href="/profile" className="mt-3 inline-block text-amber-600 hover:text-amber-400">
          Edit profile →
        </Link>
      </section>
    </div>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-zinc-500">{term}</dt>
      <dd className="text-right text-zinc-200">{value}</dd>
    </div>
  );
}
