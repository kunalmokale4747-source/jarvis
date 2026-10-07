export interface NavItem {
  label: string;
  href: string;
  phase: number;
}

/**
 * Navigation mirrors the product spec. Items whose phase is greater than the
 * current phase link to an honest "not built yet" page — never fake screens.
 */
export const NAV: NavItem[] = [
  { label: "Dashboard", href: "/", phase: 1 },
  { label: "Chat", href: "/s/chat", phase: 2 },
  { label: "Tasks", href: "/s/tasks", phase: 2 },
  { label: "Goals", href: "/s/goals", phase: 2 },
  { label: "Projects", href: "/s/projects", phase: 2 },
  { label: "Memory", href: "/s/memory", phase: 2 },
  { label: "Opportunities", href: "/s/opportunities", phase: 3 },
  { label: "Research", href: "/s/research", phase: 3 },
  { label: "Applications", href: "/s/applications", phase: 4 },
  { label: "Calendar", href: "/s/calendar", phase: 5 },
  { label: "Email", href: "/s/email", phase: 5 },
  { label: "CRM", href: "/s/crm", phase: 6 },
  { label: "Business", href: "/s/business", phase: 6 },
  { label: "Social", href: "/s/social", phase: 7 },
  { label: "Analytics", href: "/s/analytics", phase: 9 },
  { label: "Settings", href: "/settings", phase: 1 },
];

export const CURRENT_PHASE = 1;

export const PHASE_TITLES: Record<number, string> = {
  1: "Foundation",
  2: "Brain (chat, profile, memory, goals, tasks)",
  3: "Intelligence (agents, opportunity scoring)",
  4: "Career (applications, resume, cover letters)",
  5: "Productivity (email, calendar, planner, reports)",
  6: "Business (CRM, business agent)",
  7: "Social (LinkedIn, Instagram)",
  8: "Autonomy (events, workers, schedules)",
  9: "Cloud (deployment, monitoring, security hardening)",
  10: "Advanced (voice, browser agent, mobile)",
};

export function sectionMeta(section: string): { label: string; phase: number } | null {
  const item = NAV.find((n) => n.href === `/s/${section}`);
  if (!item) return null;
  return { label: item.label, phase: item.phase };
}
