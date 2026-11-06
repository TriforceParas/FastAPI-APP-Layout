import { useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, Check, Hexagon, KeyRound, LoaderCircle, LockKeyhole, ShieldCheck } from "lucide-react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Alert, Button, Field, Input, PasswordInput } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import type { MfaChallenge } from "@/features/auth/types";
import { ForgotPasswordForm, MfaStep } from "@/features/auth/components/auth-flows";
import { Turnstile } from "@/features/auth/components/turnstile";

type AuthMode = "setup" | "login" | "change-password";

/* Result of "Sign in with Microsoft", handed back in the URL by the server:
   /?sso_error=<code>  or  /#sso_mfa=<challenge>&method=..&hint=..  */
const SSO_ERRORS: Record<string, string> = {
  domain_not_allowed: "That Microsoft account's email domain isn't allowed to sign in here.",
  organisation_not_allowed: "Accounts from that Microsoft organisation can't sign in here. Personal Microsoft accounts aren't supported.",
  no_account: "There's no account for that Microsoft address yet. Ask an administrator to add you.",
  linked_elsewhere: "This account is already linked to a different Microsoft account. Ask an administrator for help.",
  account_unavailable: "This account is disabled or temporarily locked.",
  cancelled: "Microsoft sign-in was cancelled.",
  expired: "The Microsoft sign-in took too long or was started in another browser. Please try again.",
  unavailable: "Microsoft sign-in is unavailable right now. Please try again shortly.",
  failed: "Microsoft sign-in failed. Please try again.",
};

type SsoResult = { error: string | null; mfa: MfaChallenge | null };
let ssoResult: SsoResult | undefined;

/** Read once and remove from the address bar (the challenge must not stay in history). */
function takeSsoResult(): SsoResult {
  if (ssoResult) return ssoResult;
  const url = new URL(window.location.href);
  const code = url.searchParams.get("sso_error");
  const fragment = new URLSearchParams(url.hash.slice(1));
  const token = fragment.get("sso_mfa");
  const method = fragment.get("method");
  const result: SsoResult = {
    error: code ? (SSO_ERRORS[code] ?? SSO_ERRORS.failed ?? null) : null,
    mfa:
      token && (method === "totp" || method === "email")
        ? { token, method, destinationHint: fragment.get("hint") ?? undefined }
        : null,
  };
  if (code || token) {
    url.searchParams.delete("sso_error");
    window.history.replaceState(null, "", url.pathname + url.search);
  }
  ssoResult = result;
  return result;
}

function MicrosoftLogo() {
  return (
    <svg aria-hidden width="14" height="14" viewBox="0 0 21 21">
      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
  );
}

function value(form: FormData, key: string) {
  const v = form.get(key);
  return typeof v === "string" ? v : "";
}

export const errorText = (err: unknown) =>
  err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong.";

type Panel = { badge: string; headline: string; body: string };

const FEATURES = [
  "Argon2id password hashing",
  "Server-side sessions with CSRF protection",
  "Role-based access and optional two-factor",
];

/** The two-column sign-in layout (marketing panel + form column). */
export function AuthLayout({
  panel,
  icon,
  title,
  subtitle,
  footer,
  children,
}: {
  panel: Panel;
  icon: ReactNode;
  title: string;
  subtitle: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const { status } = useAuth();
  const appName = status?.app_name ?? "Workspace";
  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[#151515] text-[#ededed] lg:grid-cols-[minmax(420px,0.9fr)_minmax(560px,1.1fr)]">
      <ThemeToggle className="absolute top-5 right-5 z-10 border border-white/[0.09] bg-[#171717]" />
      <section className="auth-panel relative hidden min-h-screen flex-col overflow-hidden border-r border-white/[0.08] p-6 sm:p-10 lg:flex lg:p-12">
        <div aria-hidden className="auth-grid absolute inset-0" />
        <div aria-hidden className="auth-orb auth-orb-one" />
        <div aria-hidden className="auth-orb auth-orb-two" />

        <Brand appName={appName} tagline={status?.app_tagline} />

        <div className="auth-content-rise relative my-auto max-w-md py-16 [animation-delay:120ms]">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.09] px-2.5 py-1 text-[10px] font-medium text-emerald-300">
            <ShieldCheck size={12} /> {panel.badge}
          </div>
          <h1 className="text-3xl leading-tight font-medium tracking-[-0.035em] text-[#f2f2f2] sm:text-4xl">
            {panel.headline}
          </h1>
          <p className="mt-4 max-w-sm text-sm leading-6 text-[#858585]">{panel.body}</p>

          <div className="mt-9 space-y-4">
            {FEATURES.map((feature, index) => (
              <div
                key={feature}
                className="auth-feature-rise flex items-center gap-3 text-xs text-[#a7a7a7]"
                style={{ animationDelay: `${220 + index * 90}ms` }}
              >
                <span className="flex size-5 items-center justify-center rounded-full border border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-400">
                  <Check size={11} />
                </span>
                {feature}
              </div>
            ))}
          </div>
        </div>

        <p className="auth-content-rise relative text-[11px] text-[#999] [animation-delay:420ms]">
          Private environment · Authorised users only
        </p>
      </section>

      <section className="flex min-h-screen items-center justify-center p-5 sm:p-10">
        <div className="auth-form-rise w-full max-w-[390px]">
          <div className="mb-8 lg:hidden">
            <Brand appName={appName} tagline={status?.app_tagline} />
          </div>
          <div className="mb-7">
            <div className="mb-4 flex size-9 items-center justify-center rounded-md border border-white/[0.09] bg-white/[0.035] text-[#999]">
              {icon}
            </div>
            <h2 className="text-xl font-medium tracking-tight">{title}</h2>
            <p className="mt-1.5 text-xs leading-relaxed text-[#999]">{subtitle}</p>
          </div>
          {children}
          {footer && (
            <div className="mt-6 border-t border-white/[0.08] pt-5 text-center text-[11px] leading-relaxed text-[#999]">
              {footer}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

const SIGN_IN_PANEL: Panel = {
  badge: "Secure workspace",
  headline: "Everything your team needs, in one place.",
  body: "Sign in to continue to your dashboard, manage people and review activity.",
};

/** Initial setup, sign-in (with optional 2FA step and forgot password), or forced password change. */
export function AuthScreen({ mode }: { mode: AuthMode }) {
  const { status, login, setup, refresh, logout } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(() => (mode === "login" ? takeSsoResult().error : null));
  const [mfa, setMfa] = useState<MfaChallenge | null>(() => (mode === "login" ? takeSsoResult().mfa : null));
  const [leaving, setLeaving] = useState(false);
  const [forgot, setForgot] = useState(false);
  const appName = status?.app_name ?? "Workspace";
  const choosingPassword = mode !== "login";
  // Bot protection on sign-in and first-run setup (not on the password change).
  const turnstileKey = mode !== "change-password" && status?.turnstile_enabled ? status.turnstile_site_key : null;
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0); // bump to get a fresh, single-use token

  if (mode === "login" && mfa) {
    return (
      <AuthLayout
        panel={SIGN_IN_PANEL}
        icon={<ShieldCheck size={17} />}
        title="Two-step verification"
        subtitle={
          mfa.method === "email"
            ? `Enter the 6-digit code we emailed to ${mfa.destinationHint ?? "you"}.`
            : "Enter the 6-digit code from your authenticator app."
        }
        footer="Lost access? Use one of your recovery codes, or ask an administrator to reset two-factor."
      >
        <MfaStep challenge={mfa} onCancel={() => setMfa(null)} />
      </AuthLayout>
    );
  }

  if (mode === "login" && forgot) {
    return (
      <AuthLayout
        panel={SIGN_IN_PANEL}
        icon={<KeyRound size={17} />}
        title="Reset your password"
        subtitle="Enter your account's email address and we'll send you a link to choose a new password."
      >
        <ForgotPasswordForm onBack={() => setForgot(false)} />
      </AuthLayout>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    if (choosingPassword && value(form, "password") !== value(form, "confirmPassword")) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "setup") {
        await setup({
          name: value(form, "name").trim(),
          email: value(form, "email").trim(),
          password: value(form, "password"),
          setup_token: value(form, "setupToken").trim() || undefined,
          turnstile_token: turnstileToken,
        });
      } else if (mode === "login") {
        const next = await login(value(form, "email").trim(), value(form, "password"), turnstileToken);
        if (next) setMfa(next);
      } else {
        await api.post("/me/password", {
          current_password: value(form, "currentPassword"),
          new_password: value(form, "password"),
        });
        await refresh();
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSubmitting(false);
      // Turnstile tokens are single-use: always fetch a new one after an attempt.
      if (turnstileKey) setChallenge((n) => n + 1);
    }
  }

  const layout =
    mode === "setup"
      ? {
          panel: {
            badge: "First-time setup",
            headline: `Set up ${appName}.`,
            body: "No accounts exist yet. Create the first administrator to start managing your workspace.",
          },
          title: "Create the administrator",
          subtitle: "This account can invite and manage everyone else.",
          footer: "Registration closes automatically once the first account exists.",
        }
      : mode === "login"
        ? {
            panel: SIGN_IN_PANEL,
            title: "Welcome back",
            subtitle: `Use your ${appName} credentials to continue.`,
            footer: "Too many failed attempts temporarily lock the account.",
          }
        : {
            panel: {
              badge: "Action required",
              headline: "Choose a new password.",
              body: "Your administrator set a temporary password. Pick your own before continuing.",
            },
            title: "Update your password",
            subtitle: "Other devices will be signed out.",
            footer: "Use a long passphrase you don't use anywhere else.",
          };

  return (
    <AuthLayout
      panel={layout.panel}
      icon={mode === "change-password" ? <KeyRound size={17} /> : <LockKeyhole size={17} />}
      title={layout.title}
      subtitle={layout.subtitle}
      footer={
        <>
          {layout.footer}
          {mode === "change-password" && (
            <button
              type="button"
              onClick={() => void logout()}
              className="mt-2 block w-full text-[#999] hover:text-emerald-300"
            >
              Sign out instead
            </button>
          )}
        </>
      }
    >
      {error && (
        <Alert title="Unable to continue" tone="danger" className="mb-5">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "setup" && status?.setup_token_required && (
          <Field
            label="Setup token"
            htmlFor="setup-token"
            hint="Printed in the server log on first start (or stored in data/setup-token)."
          >
            <Input id="setup-token" name="setupToken" autoComplete="off" spellCheck={false} required autoFocus />
          </Field>
        )}

        {mode === "setup" && (
          <Field label="Full name" htmlFor="setup-name">
            <Input
              id="setup-name"
              name="name"
              autoComplete="name"
              placeholder="Alex Morgan"
              minLength={2}
              maxLength={100}
              required
              autoFocus={!status?.setup_token_required}
            />
          </Field>
        )}

        {mode !== "change-password" && (
          <Field label="Email address" htmlFor="auth-email">
            <Input
              id="auth-email"
              name="email"
              type="email"
              autoComplete={mode === "setup" ? "email" : "username"}
              placeholder="you@example.com"
              maxLength={254}
              required
              autoFocus={mode === "login"}
            />
          </Field>
        )}

        {mode === "change-password" && (
          <Field label="Current password" htmlFor="current-password">
            <PasswordInput
              id="current-password"
              name="currentPassword"
              autoComplete="current-password"
              maxLength={128}
              required
              autoFocus
            />
          </Field>
        )}

        <Field
          label={choosingPassword ? "New password" : "Password"}
          htmlFor="auth-password"
          hint={choosingPassword ? "At least 12 characters. A passphrase works well." : undefined}
        >
          <PasswordInput
            id="auth-password"
            name="password"
            autoComplete={choosingPassword ? "new-password" : "current-password"}
            minLength={choosingPassword ? 12 : undefined}
            maxLength={128}
            required
            showStrength={choosingPassword}
          />
        </Field>

        {mode === "login" && status?.mail_enabled && (
          <div className="-mt-2 text-right">
            <button
              type="button"
              onClick={() => setForgot(true)}
              className="text-[11px] text-[#999] hover:text-emerald-300"
            >
              Forgot password?
            </button>
          </div>
        )}

        {choosingPassword && (
          <Field label="Confirm password" htmlFor="confirm-password">
            <PasswordInput
              id="confirm-password"
              name="confirmPassword"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
            />
          </Field>
        )}

        {turnstileKey && (
          <Turnstile
            siteKey={turnstileKey}
            action={mode === "setup" ? "setup" : "login"}
            onToken={setTurnstileToken}
            resetKey={challenge}
          />
        )}

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="mt-2 w-full"
          disabled={submitting || (turnstileKey !== null && !turnstileToken)}
        >
          {submitting ? (
            <>
              <LoaderCircle size={14} className="animate-spin" /> Please wait
            </>
          ) : (
            <>
              {mode === "setup" ? `Set up ${appName}` : mode === "login" ? "Sign in" : "Update password"}
              <ArrowRight size={14} />
            </>
          )}
        </Button>
      </form>

      {mode === "login" && status?.microsoft_sso_enabled && (
        <>
          <div className="my-5 flex items-center gap-3 text-[10px] tracking-wider text-[#666] uppercase">
            <span className="flex-1 border-t border-white/[0.08]" />
            or
            <span className="flex-1 border-t border-white/[0.08]" />
          </div>
          {/* A full-page navigation: the server redirects to Microsoft and back. */}
          <a
            href="/api/auth/microsoft/login"
            onClick={() => setLeaving(true)}
            aria-disabled={leaving || undefined}
            className="flex h-10 w-full items-center justify-center gap-2.5 rounded-md border border-white/[0.11] bg-white/[0.04] text-sm font-medium text-[#ededed] transition hover:bg-white/[0.075] focus-visible:border-emerald-400 focus-visible:outline-none aria-disabled:pointer-events-none aria-disabled:opacity-60"
          >
            {leaving ? <LoaderCircle size={14} className="animate-spin" /> : <MicrosoftLogo />}
            Sign in with Microsoft
          </a>
        </>
      )}
    </AuthLayout>
  );
}

function Brand({ appName, tagline }: { appName: string; tagline?: string }): ReactNode {
  return (
    <div className="auth-content-rise relative flex items-center gap-3">
      <div className="flex size-8 items-center justify-center rounded-md bg-emerald-400 text-[#052719]">
        <Hexagon size={18} strokeWidth={2.25} />
      </div>
      <div>
        <p className="text-sm font-semibold tracking-tight">{appName}</p>
        {tagline && <p className="text-[10px] tracking-[0.17em] text-[#999] uppercase">{tagline}</p>}
      </div>
    </div>
  );
}
