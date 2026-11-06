import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, MailCheck } from "lucide-react";

import { Alert, Button, Field, Input, PasswordInput } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import type { MfaChallenge } from "@/features/auth/types";
import { AuthLayout, errorText } from "@/features/auth/components/auth-screen";
import { Turnstile } from "@/features/auth/components/turnstile";

/* -------------------------------------------------------------------------- */
/* Sign-in step 2: authenticator / email code, or a recovery code              */
/* -------------------------------------------------------------------------- */

export function MfaStep({ challenge, onCancel }: { challenge: MfaChallenge; onCancel: () => void }) {
  const { verifyMfa, resendMfa } = useAuth();
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [cooldown, setCooldown] = useState(challenge.method === "email" ? 30 : 0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [cooldown]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setInfo(null);
    try {
      await verifyMfa(challenge.token, code); // on success the app re-renders signed in
    } catch (err) {
      const message = errorText(err);
      setError(message);
      setExpired(/sign in again/i.test(message));
      setCode("");
    } finally {
      setPending(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      await resendMfa(challenge.token);
      setInfo("We sent a new code.");
      setCooldown(30);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      {error && (
        <Alert title={expired ? "Please sign in again" : "Could not verify"} tone="danger" className="mb-5">
          {error}
        </Alert>
      )}
      {info && <Alert title={info} tone="success" className="mb-5" />}

      {expired ? (
        <Button variant="primary" size="lg" className="w-full" onClick={onCancel}>
          <ArrowLeft size={14} /> Back to sign in
        </Button>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field
            label={recovery ? "Recovery code" : "Verification code"}
            htmlFor="mfa-code"
            hint={recovery ? "One of the 10 codes you saved when you turned on two-factor. Each works once." : undefined}
          >
            <Input
              id="mfa-code"
              name="code"
              value={code}
              onChange={(e) => setCode(recovery ? e.target.value : e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode={recovery ? "text" : "numeric"}
              autoComplete="one-time-code"
              placeholder={recovery ? "xxxxx-xxxxx" : "123456"}
              maxLength={recovery ? 11 : 6}
              className={recovery ? "font-mono" : "text-center font-mono text-lg tracking-[0.5em]"}
              required
              autoFocus
            />
          </Field>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            className="w-full"
            loading={pending}
            disabled={recovery ? code.replace(/[^a-z0-9]/gi, "").length !== 10 : code.length !== 6}
          >
            Verify <ArrowRight size={14} />
          </Button>

          <div className="flex items-center justify-between text-[11px]">
            <button type="button" onClick={onCancel} className="text-[#999] hover:text-emerald-300">
              <ArrowLeft size={11} className="mr-1 inline" />
              Back
            </button>
            <span className="flex gap-3">
              {challenge.method === "email" && !recovery && (
                <button
                  type="button"
                  onClick={() => void resend()}
                  disabled={cooldown > 0}
                  className="text-[#999] hover:text-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setRecovery((r) => !r);
                  setCode("");
                }}
                className="text-[#999] hover:text-emerald-300"
              >
                {recovery ? "Use a verification code" : "Use a recovery code"}
              </button>
            </span>
          </div>
        </form>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Forgot password                                                             */
/* -------------------------------------------------------------------------- */

export function ForgotPasswordForm({ onBack }: { onBack: () => void }) {
  const { status } = useAuth();
  const turnstileKey = status?.turnstile_enabled ? status.turnstile_site_key : null;
  const [token, setToken] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "").trim();
    setPending(true);
    setError(null);
    try {
      const result = await api.post<{ detail: string }>("/auth/password/forgot", {
        email,
        turnstile_token: token ?? undefined,
      });
      setSent(result.detail);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
      if (turnstileKey) setRound((n) => n + 1);
    }
  }

  if (sent) {
    return (
      <div className="space-y-5">
        <Alert title="Check your inbox" tone="success">
          {sent} The link expires soon and works once.
        </Alert>
        <Button size="lg" className="w-full" onClick={onBack}>
          <ArrowLeft size={14} /> Back to sign in
        </Button>
      </div>
    );
  }

  return (
    <>
      {error && (
        <Alert title="Unable to continue" tone="danger" className="mb-5">
          {error}
        </Alert>
      )}
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email address" htmlFor="forgot-email">
          <Input
            id="forgot-email"
            name="email"
            type="email"
            autoComplete="username"
            placeholder="you@example.com"
            maxLength={254}
            required
            autoFocus
          />
        </Field>
        {turnstileKey && <Turnstile siteKey={turnstileKey} action="forgot" onToken={setToken} resetKey={round} />}
        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="w-full"
          loading={pending}
          disabled={turnstileKey !== null && !token}
        >
          <MailCheck size={14} /> Email me a reset link
        </Button>
        <button type="button" onClick={onBack} className="block w-full text-center text-[11px] text-[#999] hover:text-emerald-300">
          <ArrowLeft size={11} className="mr-1 inline" />
          Back to sign in
        </button>
      </form>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Reset password (link from the email: /reset-password?token=...)            */
/* -------------------------------------------------------------------------- */

function takeTokenFromUrl(): string | null {
  const url = new URL(window.location.href);
  const token = url.searchParams.get("token");
  if (token) {
    // Remove the secret from the address bar and browser history immediately.
    url.searchParams.delete("token");
    window.history.replaceState(null, "", url.pathname + url.search);
  }
  return token;
}

export function ResetPasswordScreen() {
  const [token] = useState(takeTokenFromUrl);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    if (password !== String(form.get("confirm") ?? "")) {
      setError("Passwords do not match.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api.post("/auth/password/reset", { token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  const goToSignIn = () => window.location.assign("/");

  return (
    <AuthLayout
      panel={{
        badge: "Account recovery",
        headline: "Choose a new password.",
        body: "For your security this signs you out on every device. Two-factor, if you use it, still applies.",
      }}
      icon={done ? <CheckCircle2 size={17} /> : <KeyRound size={17} />}
      title={done ? "Password updated" : "Set a new password"}
      subtitle={done ? "You can now sign in with your new password." : "Use at least 12 characters. A passphrase works well."}
    >
      {!token ? (
        <div className="space-y-5">
          <Alert title="This link is incomplete" tone="danger">
            Open the link from your email again, or request a new one from the sign-in page.
          </Alert>
          <Button size="lg" className="w-full" onClick={goToSignIn}>
            <ArrowLeft size={14} /> Back to sign in
          </Button>
        </div>
      ) : done ? (
        <Button variant="primary" size="lg" className="w-full" onClick={goToSignIn}>
          Sign in <ArrowRight size={14} />
        </Button>
      ) : (
        <>
          {error && (
            <Alert title="Unable to reset password" tone="danger" className="mb-5">
              {error}
            </Alert>
          )}
          <form onSubmit={submit} className="space-y-4">
            <Field label="New password" htmlFor="reset-password">
              <PasswordInput
                id="reset-password"
                name="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                autoFocus
                showStrength
              />
            </Field>
            <Field label="Confirm password" htmlFor="reset-confirm">
              <PasswordInput id="reset-confirm" name="confirm" autoComplete="new-password" minLength={12} maxLength={128} required />
            </Field>
            <Button type="submit" variant="primary" size="lg" className="w-full" loading={pending}>
              Update password <ArrowRight size={14} />
            </Button>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
