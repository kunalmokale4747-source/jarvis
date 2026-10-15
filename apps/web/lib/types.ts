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

export interface Reminder {
  id: string;
  user_id: string;
  title: string;
  message: string | null;
  scheduled_at: string;
  timezone: string;
  status: "PENDING" | "SCHEDULED" | "FIRED" | "CANCELLED" | "FAILED";
  recurrence: "none" | "daily" | "weekly" | "monthly" | "yearly";
  recurrence_interval: number;
  task_id: string | null;
  channel: string;
  last_fired_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  reminder_id: string | null;
  title: string;
  body: string | null;
  channel: string;
  status: "QUEUED" | "SENT" | "FAILED" | "READ";
  error: string | null;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  user_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  provider: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  status: "OK" | "ERROR" | "OFFLINE";
  created_at: string;
}
