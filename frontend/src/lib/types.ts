// Types shared by several features. They mirror app/api/schemas.py and
// app/features/users/schemas.py; keep them in sync with the backend.
// Feature-specific types live in src/features/<feature>/types.ts.

export type RoleBrief = { id: number; name: string };

export type User = {
  id: string;
  email: string;
  name: string;
  /** In priority order: the FIRST role decides the landing page. */
  roles: RoleBrief[];
  is_active: boolean;
  must_change_password: boolean;
  is_locked: boolean;
  /** Two-factor method the user chose in Settings, or null. */
  mfa_method: MfaMethod | null;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AuthStatus = {
  app_name: string;
  app_tagline: string;
  environment: "development" | "test" | "production";
  auth_enabled: boolean;
  auth_bypass: boolean;
  setup_required: boolean;
  setup_token_required: boolean;
  turnstile_enabled: boolean;
  turnstile_site_key: string | null;
  /** Email is configured: forgot-password and email 2FA codes are available. */
  mail_enabled: boolean;
  /** Show "Sign in with Microsoft" (only allowed email domains can use it). */
  microsoft_sso_enabled: boolean;
  csrf_token: string;
  user: User | null;
  /** Every page AND feature key, e.g. "users" or "dashboard.recent_activity". Empty when signed out. */
  permissions: Record<string, Permission>;
  /** Where to go after sign-in; null if the user can open no page. */
  landing_path: string | null;
};

export type Permission = { read: boolean; write: boolean };

export type MfaMethod = "totp" | "email";

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

/** What every lookup returns: an id and a display label, nothing else. */
export type LookupItem = { id: number; label: string };
