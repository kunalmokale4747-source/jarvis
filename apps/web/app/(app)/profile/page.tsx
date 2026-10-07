"use client";

import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { Profile } from "@/lib/types";

const ADVANCED_FIELDS = [
  "education",
  "experience",
  "projects",
  "preferences",
  "availability",
  "resume",
  "portfolio",
  "social_profiles",
  "professional_profiles",
] as const;

interface FormState {
  name: string;
  location: string;
  languages: string;
  skills: string;
  career_goals: string;
  business_goals: string;
  financial_goals: string;
  current_priorities: string;
  advanced: Record<string, string>;
}

function emptyForm(): FormState {
  return {
    name: "",
    location: "",
    languages: "",
    skills: "",
    career_goals: "",
    business_goals: "",
    financial_goals: "",
    current_priorities: "",
    advanced: Object.fromEntries(ADVANCED_FIELDS.map((f) => [f, ""])),
  };
}

function toForm(p: Profile): FormState {
  return {
    name: p.name ?? "",
    location: p.location ?? "",
    languages: (p.languages ?? []).join(", "),
    skills: (p.skills ?? []).map((s) => s.name).join(", "),
    career_goals: p.career_goals?.summary ?? "",
    business_goals: p.business_goals?.summary ?? "",
    financial_goals: p.financial_goals?.summary ?? "",
    current_priorities: (p.current_priorities ?? []).join("\n"),
    advanced: Object.fromEntries(
      ADVANCED_FIELDS.map((field) => {
        const value = (p as unknown as Record<string, unknown>)[field];
        return [field, value === undefined || value === null ? "" : JSON.stringify(value, null, 2)];
      }),
    ),
  };
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function splitCommas(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function ProfilePage() {
  const [form, setForm] = useState<FormState>(emptyForm());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<Profile>("/api/v1/me/profile")
      .then((p) => setForm(toForm(p)))
      .catch((err) => {
        if (err instanceof ApiError) setLoadError(err);
      })
      .finally(() => setLoading(false));
  }, []);

  function set(key: keyof Omit<FormState, "advanced">, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function setAdvanced(field: string, value: string) {
    setForm((f) => ({ ...f, advanced: { ...f.advanced, [field]: value } }));
  }

  async function save() {
    setSaving(true);
    setStatus(null);

    const payload: Record<string, unknown> = {
      name: form.name.trim() || null,
      location: form.location.trim() || null,
      languages: splitCommas(form.languages),
      skills: splitCommas(form.skills).map((name) => ({ name })),
      career_goals: form.career_goals.trim() ? { summary: form.career_goals.trim() } : null,
      business_goals: form.business_goals.trim() ? { summary: form.business_goals.trim() } : null,
      financial_goals: form.financial_goals.trim() ? { summary: form.financial_goals.trim() } : null,
      current_priorities: splitLines(form.current_priorities),
    };

    for (const field of ADVANCED_FIELDS) {
      const raw = form.advanced[field].trim();
      if (!raw) {
        payload[field] = null;
        continue;
      }
      try {
        payload[field] = JSON.parse(raw);
      } catch {
        setStatus({
          kind: "err",
          text: `Advanced field "${field}" is not valid JSON. Fix it before saving.`,
        });
        setSaving(false);
        return;
      }
    }

    try {
      const updated = await api<Profile>("/api/v1/me/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setForm(toForm(updated));
      setStatus({ kind: "ok", text: `Saved at ${new Date(updated.updated_at).toLocaleTimeString()}.` });
    } catch (err) {
      if (err instanceof ApiError) {
        setStatus({ kind: "err", text: `${err.code}: ${err.whatHappened} ${err.whatNext}` });
      } else {
        setStatus({ kind: "err", text: "Unexpected error while saving." });
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-zinc-500">Loading profile…</p>;

  if (loadError) {
    return (
      <div className="rounded-md border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
        <p className="font-semibold">{loadError.code}</p>
        <p className="mt-1">{loadError.whatHappened}</p>
        <p className="mt-1 text-red-400">{loadError.whatNext}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-zinc-100">Profile</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Stored in the database, never in source code. JARVIS reads this to understand your
          context.
        </p>
      </header>

      {status ? (
        <div
          className={`rounded-md border p-3 text-sm ${
            status.kind === "ok"
              ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
              : "border-red-900 bg-red-950/40 text-red-300"
          }`}
        >
          {status.text}
        </div>
      ) : null}

      <section className="space-y-4 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">Basics</h2>
        <Field label="Name">
          <input value={form.name} onChange={(e) => set("name", e.target.value)} className={inputCls} />
        </Field>
        <Field label="Location">
          <input
            value={form.location}
            onChange={(e) => set("location", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Languages (comma separated)">
          <input
            value={form.languages}
            onChange={(e) => set("languages", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Skills (comma separated)">
          <input
            value={form.skills}
            onChange={(e) => set("skills", e.target.value)}
            className={inputCls}
          />
        </Field>
      </section>

      <section className="space-y-4 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">Goals</h2>
        <Field label="Career goals">
          <textarea
            value={form.career_goals}
            onChange={(e) => set("career_goals", e.target.value)}
            rows={2}
            className={inputCls}
          />
        </Field>
        <Field label="Business goals">
          <textarea
            value={form.business_goals}
            onChange={(e) => set("business_goals", e.target.value)}
            rows={2}
            className={inputCls}
          />
        </Field>
        <Field label="Financial goals">
          <textarea
            value={form.financial_goals}
            onChange={(e) => set("financial_goals", e.target.value)}
            rows={2}
            className={inputCls}
          />
        </Field>
        <Field label="Current priorities (one per line)">
          <textarea
            value={form.current_priorities}
            onChange={(e) => set("current_priorities", e.target.value)}
            rows={3}
            className={inputCls}
          />
        </Field>
      </section>

      <section className="space-y-4 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-xs uppercase tracking-widest text-zinc-500">
          Advanced (JSON) — leave empty when unused
        </h2>
        {ADVANCED_FIELDS.map((field) => (
          <Field key={field} label={field}>
            <textarea
              value={form.advanced[field]}
              onChange={(e) => setAdvanced(field, e.target.value)}
              rows={2}
              spellCheck={false}
              className={`${inputCls} font-mono text-xs`}
            />
          </Field>
        ))}
      </section>

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-zinc-950 hover:bg-amber-500 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save profile"}
      </button>
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-600";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-zinc-400">{label}</span>
      {children}
    </label>
  );
}
