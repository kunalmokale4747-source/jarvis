export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  phase: number;
  time: string;
  components: Record<string, { status: "online" | "offline"; detail?: string | null }>;
}

export interface IntegrationInfo {
  status: "connected" | "pending_oauth" | "not_configured" | "error";
  phase: number;
}

export interface MetaResponse {
  name: string;
  version: string;
  phase: number;
  auth_mode: string;
  integrations: Record<string, IntegrationInfo>;
}

export interface Profile {
  user_id: string;
  name: string | null;
  location: string | null;
  languages: string[] | null;
  skills: { name: string; level?: string }[] | null;
  career_goals: { summary?: string } | null;
  business_goals: { summary?: string } | null;
  financial_goals: { summary?: string } | null;
  current_priorities: string[] | null;
  education: unknown;
  experience: unknown;
  projects: unknown;
  preferences: Record<string, unknown> | null;
  availability: Record<string, unknown> | null;
  resume: Record<string, unknown> | null;
  portfolio: unknown;
  social_profiles: Record<string, unknown> | null;
  professional_profiles: Record<string, unknown> | null;
  is_complete: boolean;
  updated_at: string;
}
