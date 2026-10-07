"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { PHASE_TITLES, sectionMeta } from "@/lib/nav";

export default function NotBuiltSectionPage() {
  const params = useParams<{ section: string }>();
  const section = params.section;
  const meta = sectionMeta(section);

  if (!meta) {
    return (
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Unknown section</h1>
        <Link href="/" className="mt-3 inline-block text-amber-600 hover:text-amber-400">
          ← Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-zinc-100">{meta.label}</h1>
        <p className="mt-1 text-sm text-zinc-500">Not built yet — Phase {meta.phase}</p>
      </header>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 text-sm">
        <p className="text-zinc-300">
          {meta.label} is planned for <span className="text-amber-400">Phase {meta.phase}</span> —{" "}
          {PHASE_TITLES[meta.phase]}.
        </p>
        <p className="mt-2 text-zinc-500">
          This screen intentionally shows no data. JARVIS never displays simulated information as
          if it were real.
        </p>
      </div>

      <Link href="/" className="inline-block text-sm text-amber-600 hover:text-amber-400">
        ← Back to dashboard
      </Link>
    </div>
  );
}
