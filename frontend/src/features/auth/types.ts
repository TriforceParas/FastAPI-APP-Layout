// Types for the auth feature (mirror its backend schemas).

import type { MfaMethod, User } from "@/lib/types";

export type AuthResult = { user: User; csrf_token: string };

/** POST /auth/login: either signed in, or a second step to complete. */
export type LoginResponse = {
  mfa_required?: boolean;
  mfa_method?: MfaMethod;
  challenge_token?: string;
  destination_hint?: string;
  user?: User;
  csrf_token?: string;
};

export type MfaChallenge = { method: MfaMethod; token: string; destinationHint?: string };
