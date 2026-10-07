"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import StatusPill from "@/components/StatusPill";
import { ApiError, api } from "@/lib/api";
import { CURRENT_PHASE, PHASE_TITLES } from "@/lib/nav";
import type { HealthResponse, MetaResponse, Profile } from "@/lib/types";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning.";
  if (hour < 18) return "Good afternoon.";
  return "Good evening.";
}

function connectedCount(meta: MetaResponse | null): number {
  if (!meta) return 0;
  return Object.values(meta.integrations).filter((i) => i.status === "connected").length;
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [h, m, p] = await Promise.all([
          api<HealthResponse>("/health"),
          api<MetaResponse>("/api/v1/meta"),
          api<Profile>("/api/v1/me/profile"),
        ]);
        if (cancelled) return;
        setHealth(h);
        setMeta(m);
        setProfile(p);
      } catch (err) {
        if (!cancelled && err instanceof ApiError) setError(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading dashboard…</p>;
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
        <p className="font-semibold">{error.code}</p>
        <p className="mt-1">{error.whatHappened}</p>
        <p className="mt-1 text-red-400">{error.whatNext}</p>
      </div>
    );
  }

  const priority = profile?.current_priorities?.[0] ?? null;
  const nextAction = !profile?.is_complete
    ? "Complete your profile — everything JARVIS does depends on it."
    : "Phase 2 delivers chat, memory, goals and tasks. Nothing to execute yet.";

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-zinc-500">{greeting()}</p>
        <h1 className="text-2xl font-semibold text-zinc-100">JARVIS</h1>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <p className="text-xs uppercase tracking-widest text-zinc-500">Today&apos;s objective</p>
        <p className="mt-2 text-lg text-amber-300">
          {priority ?? "No priorities recorded yet."}
        </p>
        {!priority ? (
          <Link href="/profile" className="mt-2 inline-block text-sm text-amber-600 hover:text-amber-400">
            Set priorities in your profile →
          </Link>
        ) : null}
      </section>

      <section>
        <p className="text-xs uppercase tracking-widest text-zinc-500">Next action</p>
        <p className="mt-2 text-sm text-zinc-200">{nextAction}</p>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Stat
          label="API"
          value={health?.components.api.status === "online" ? "ONLINE" : "OFFLINE"}
          pill={health?.components.api.status === "online" ? "on" : "off"}
        />
        <Stat
          label="Database"
          value={health?.components.database.status === "online" ? "ONLINE" : "OFFLINE"}
          pill={health?.components.database.status === "online" ? "on" : "off"}
        />
        <Stat
          label="Profile"
          value={profile?.is_complete ? "COMPLETE" : "INCOMPLETE"}
          pill={profile?.is_complete ? "on" : "warn"}
        />
        <Stat
          label="Integrations"
          value={`${connectedCount(meta)} connected`}
          pill="off"
        />
        <Stat label="Auth" value={meta?.auth_mode ?? "—"} pill="warn" />
        <Stat
          label="Phase"
          value={`${CURRENT_PHASE} · ${PHASE_TITLES[CURRENT_PHASE]}`}
          pill="on"
        />
      </section>

      <section className="rounded-xl border border-zinc-800 p-4">
        <p className="text-xs uppercase tracking-widest text-zinc-500">Build status</p>
        <ul className="mt-3 space-y-1.5 text-sm">
          {Object.entries(PHASE_TITLES).map(([phase, title]) => {
            const n = Number(phase);
            const done = n < CURRENT_PHASE;
            const active = n === CURRENT_PHASE;
            return (
              <li key={phase} className="flex items-center gap-2">
                <span
                  className={
                    done
                      ? "text-emerald-500"
                      : active
                        ? "text-amber-500"
                        : "text-zinc-600"
                  }
                >
                  {done ? "✓" : active ? "●" : "○"}
                </span>
                <span className={active ? "text-zinc-100" : "text-zinc-500"}>
                  Phase {phase} — {title}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-[11px] text-zinc-600">
          Nothing on this screen is simulated. Offline components are shown as offline.
        </p>
      </section>
    </div>
  );
}

function Stat({ label, value, pill }: { label: string; value: string; pill: "on" | "off" | "warn" }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <p className="text-[11px] uppercase tracking-widest text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-100">{value}</p>
      <div className="mt-2">
        <StatusPill label={pill === "on" ? "ok" : pill === "warn" ? "attention" : "offline"} state={pill} />
      </div>
    </div>
  );
}
