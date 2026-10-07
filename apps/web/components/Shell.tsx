"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clearToken, getToken } from "@/lib/api";
import { CURRENT_PHASE, NAV } from "@/lib/nav";

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  function logout() {
    const token = getToken();
    if (token) {
      void fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/v1/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
    }
    clearToken();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-zinc-500">
        Loading JARVIS…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
        <div className="flex h-14 items-center gap-3 px-4">
          <button
            type="button"
            aria-label="Toggle navigation"
            onClick={() => setOpen((v) => !v)}
            className="rounded-md border border-zinc-700 px-2 py-1 text-sm text-zinc-300 md:hidden"
          >
            ☰
          </button>
          <Link href="/" className="tracking-[0.3em] text-sm font-semibold text-amber-300">
            JARVIS
          </Link>
          <span className="rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] uppercase tracking-widest text-zinc-500">
            phase {CURRENT_PHASE}
          </span>
          <div className="ml-auto flex items-center gap-3">
            <Link href="/profile" className="text-sm text-zinc-400 hover:text-zinc-100">
              Profile
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-900"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl">
        <nav
          className={`${
            open ? "block" : "hidden"
          } fixed inset-x-0 top-14 z-20 max-h-[calc(100vh-3.5rem)] overflow-y-auto border-b border-zinc-800 bg-zinc-950 p-3 md:static md:block md:w-56 md:shrink-0 md:border-b-0 md:border-r md:bg-transparent`}
        >
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : item.href === "/settings"
                    ? pathname.startsWith("/settings")
                    : pathname === item.href;
              const future = item.phase > CURRENT_PHASE;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`flex items-center justify-between rounded-md px-3 py-2 text-sm ${
                      active
                        ? "bg-zinc-900 text-amber-300"
                        : "text-zinc-300 hover:bg-zinc-900 hover:text-zinc-100"
                    }`}
                  >
                    <span>{item.label}</span>
                    {future ? (
                      <span className="text-[10px] text-zinc-600">P{item.phase}</span>
                    ) : null}
                  </Link>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 px-3 text-[11px] leading-relaxed text-zinc-600">
            Phases marked with a number are not built yet. JARVIS shows real data only.
          </p>
        </nav>

        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
