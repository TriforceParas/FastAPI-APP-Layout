// Types for the dashboard feature (mirror its backend schemas).

import type { AuditEvent } from "@/features/audit/types";

/** Each group is null unless the user may read that dashboard feature. */
export type DashboardSummary = {
  users_total: number | null;
  users_active: number | null;
  admins: number | null;
  users_locked: number | null;
  sessions_active: number | null;
  my_sessions: number | null;
  my_last_login_at: string | null;
  recent_events: AuditEvent[] | null;
};
