// Types for the settings feature (mirror its backend schemas).

import type { MfaMethod } from "@/lib/types";

export type MfaStatus = {
  method: MfaMethod | null;
  enabled_at: string | null;
  recovery_codes_remaining: number;
  email_available: boolean;
};

export type TotpEnrollment = { challenge_token: string; secret: string; otpauth_uri: string; qr_code: string };

export type EmailEnrollment = { challenge_token: string; destination_hint: string };

export type SessionInfo = {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  current: boolean;
};
