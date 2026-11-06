// Types for the audit feature (mirror its backend schemas).

export type AuditEvent = {
  id: number;
  created_at: string;
  action: string;
  outcome: "success" | "failure" | "denied";
  actor_id: string | null;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
};
