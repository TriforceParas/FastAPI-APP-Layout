import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, onUnauthorized, setCsrfToken } from "@/lib/api";
import type { AuthResult, LoginResponse, MfaChallenge } from "@/features/auth/types";
import type { AuthStatus, User } from "@/lib/types";

type AuthContextValue = {
  status: AuthStatus | null;
  user: User | null;
  /** True if the user may Read (default) or Write the page/feature key, e.g. can("users", "write"). */
  can: (key: string, kind?: "read" | "write") => boolean;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Resolves to a 2FA challenge when the account has two-factor turned on, else null (signed in). */
  login: (email: string, password: string, turnstileToken?: string | null) => Promise<MfaChallenge | null>;
  /** Second step: a 6-digit code (authenticator or email) or a recovery code. */
  verifyMfa: (challengeToken: string, code: string) => Promise<void>;
  resendMfa: (challengeToken: string) => Promise<void>;
  setup: (input: {
    name: string;
    email: string;
    password: string;
    setup_token?: string;
    turnstile_token?: string | null;
  }) => Promise<void>;
  logout: () => Promise<void>;
  /** Replace the cached user after a profile/password change. */
  setUser: (user: User) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await api.get<AuthStatus>("/auth/status");
      setCsrfToken(next.csrf_token);
      setStatus(next);
      setError(null);
      document.title = next.app_name;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach the server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    onUnauthorized(() => void refresh());
    return () => onUnauthorized(null);
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: status?.user ?? null,
      can: (key, kind = "read") => Boolean(status?.permissions[key]?.[kind]),
      loading,
      error,
      refresh,
      // After sign-in, reload the full status so permissions and landing page are current.
      login: async (email, password, turnstileToken) => {
        const result = await api.post<LoginResponse>("/auth/login", {
          email,
          password,
          turnstile_token: turnstileToken ?? undefined,
        });
        if (result.mfa_required && result.challenge_token && result.mfa_method) {
          return { method: result.mfa_method, token: result.challenge_token, destinationHint: result.destination_hint };
        }
        if (result.csrf_token) setCsrfToken(result.csrf_token);
        await refresh();
        return null;
      },
      verifyMfa: async (challengeToken, code) => {
        const result = await api.post<LoginResponse>("/auth/login/verify", { challenge_token: challengeToken, code });
        if (result.csrf_token) setCsrfToken(result.csrf_token);
        await refresh();
      },
      resendMfa: async (challengeToken) => {
        await api.post("/auth/login/resend", { challenge_token: challengeToken });
      },
      setup: async (input) => {
        const result = await api.post<AuthResult>("/auth/setup", input);
        setCsrfToken(result.csrf_token);
        await refresh();
      },
      logout: async () => {
        await api.post("/auth/logout").catch(() => undefined);
        await refresh();
      },
      setUser: (user) => setStatus((current) => (current ? { ...current, user } : current)),
    }),
    [status, loading, error, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
