export default function StatusPill({
  label,
  state,
}: {
  label: string;
  state: "on" | "off" | "warn";
}) {
  const styles =
    state === "on"
      ? "border-emerald-800 text-emerald-400"
      : state === "warn"
        ? "border-amber-800 text-amber-400"
        : "border-zinc-700 text-zinc-500";
  const dot =
    state === "on" ? "bg-emerald-500" : state === "warn" ? "bg-amber-500" : "bg-zinc-600";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-wider ${styles}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
