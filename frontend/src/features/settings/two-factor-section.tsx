import { useState, type FormEvent } from "react";
import { Copy, Download, KeyRound, Mail, ShieldCheck, ShieldOff, Smartphone } from "lucide-react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  cn,
  DescriptionList,
  Dialog,
  Field,
  Input,
  PasswordInput,
  Skeleton,
  useLatest,
  useToast,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { formatDate } from "@/lib/format";
import type { EmailEnrollment, MfaStatus, TotpEnrollment } from "@/features/settings/types";
import type { MfaMethod } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const message = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong.");

const METHODS: Record<MfaMethod, { label: string; description: string; icon: typeof Smartphone }> = {
  totp: {
    label: "Authenticator app",
    description: "Google Authenticator, Microsoft Authenticator, 1Password, Authy… Works offline. Recommended.",
    icon: Smartphone,
  },
  email: {
    label: "Email code",
    description: "We email you a 6-digit code each time you sign in.",
    icon: Mail,
  },
};

type Step =
  | { kind: "password"; purpose: "enroll" | "recovery" | "disable"; method?: MfaMethod }
  | { kind: "totp"; enrollment: TotpEnrollment }
  | { kind: "email"; enrollment: EmailEnrollment }
  | { kind: "codes"; codes: string[] };

export function TwoFactorSection() {
  const toast = useToast();
  const { refresh } = useAuth();
  const { data, loading, reload } = useResource(() => api.get<MfaStatus>("/me/mfa"), []);
  const [choice, setChoice] = useState<MfaMethod>("totp");
  const [step, setStep] = useState<Step | null>(null);
  // Each dialog keeps its last content while it animates out.
  const passwordStep = useLatest(step?.kind === "password" ? step : null);
  const totpStep = useLatest(step?.kind === "totp" ? step : null);
  const emailStep = useLatest(step?.kind === "email" ? step : null);
  const codesStep = useLatest(step?.kind === "codes" ? step : null);

  if (loading && !data) return <Skeleton className="h-48 w-full max-w-2xl" />;
  if (!data) return null;
  const close = () => setStep(null);

  async function afterPassword(password: string) {
    if (step?.kind !== "password") return;
    if (step.purpose === "enroll" && step.method === "totp") {
      const enrollment = await api.post<TotpEnrollment>("/me/mfa/totp/start", { current_password: password });
      setStep({ kind: "totp", enrollment });
    } else if (step.purpose === "enroll" && step.method === "email") {
      const enrollment = await api.post<EmailEnrollment>("/me/mfa/email/start", { current_password: password });
      setStep({ kind: "email", enrollment });
    } else if (step.purpose === "recovery") {
      const result = await api.post<{ recovery_codes: string[] }>("/me/mfa/recovery-codes", { current_password: password });
      setStep({ kind: "codes", codes: result.recovery_codes });
      await reload();
    } else {
      await api.post("/me/mfa/disable", { current_password: password });
      close();
      toast.success("Two-factor is off", "Your other devices were signed out.");
      await Promise.all([reload(), refresh()]);
    }
  }

  async function confirm(token: string, code: string) {
    const result = await api.post<{ recovery_codes: string[] }>("/me/mfa/confirm", { challenge_token: token, code });
    setStep({ kind: "codes", codes: result.recovery_codes });
    toast.success("Two-factor is on", "Your other devices were signed out.");
    await Promise.all([reload(), refresh()]);
  }

  const on = data.method !== null;

  return (
    <div className="max-w-2xl space-y-5">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Two-factor authentication</CardTitle>
            <CardDescription>
              Optional. Adds a second step after your password, so a stolen password alone cannot open your account.
            </CardDescription>
          </div>
          <Badge tone={on ? "success" : "neutral"}>{on ? "On" : "Off"}</Badge>
        </CardHeader>
        <CardContent>
          {on ? (
            <div className="space-y-4">
              <DescriptionList
                items={[
                  { label: "Method", value: METHODS[data.method!].label },
                  { label: "Turned on", value: formatDate(data.enabled_at) },
                  {
                    label: "Recovery codes",
                    value: (
                      <span className={cn(data.recovery_codes_remaining <= 2 && "text-amber-300")}>
                        {data.recovery_codes_remaining} of 10 left
                      </span>
                    ),
                  },
                ]}
              />
              {data.recovery_codes_remaining <= 2 && (
                <Alert tone="warning" title="You are running out of recovery codes">
                  Generate new ones so you can still get in if you lose your {data.method === "totp" ? "phone" : "mailbox"}.
                </Alert>
              )}
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => setStep({ kind: "password", purpose: "recovery" })}>
                  <KeyRound size={13} /> New recovery codes
                </Button>
                <Button variant="danger" onClick={() => setStep({ kind: "password", purpose: "disable" })}>
                  <ShieldOff size={13} /> Turn off
                </Button>
              </div>
              <p className="text-[11px] leading-5 text-[#6f6f6f]">
                To switch methods, turn two-factor off and set it up again.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-2" role="radiogroup" aria-label="Two-factor method">
                {(Object.keys(METHODS) as MfaMethod[]).map((key) => {
                  const method = METHODS[key];
                  const unavailable = key === "email" && !data.email_available;
                  const Icon = method.icon;
                  return (
                    <label
                      key={key}
                      className={cn(
                        "flex cursor-pointer gap-3 rounded-md border border-white/[0.09] p-3 hover:bg-white/[0.025]",
                        choice === key && "border-emerald-400/40 bg-emerald-400/[0.04]",
                        unavailable && "cursor-not-allowed opacity-50",
                      )}
                    >
                      <input
                        type="radio"
                        name="mfa-method"
                        value={key}
                        checked={choice === key}
                        disabled={unavailable}
                        onChange={() => setChoice(key)}
                        className="mt-1 accent-emerald-400"
                      />
                      <Icon size={16} className="mt-0.5 shrink-0 text-[#888]" />
                      <span>
                        <span className="block text-xs font-medium text-[#ddd]">{method.label}</span>
                        <span className="mt-0.5 block text-[11px] text-[#777]">
                          {unavailable ? "Email is not configured on this server." : method.description}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <Button variant="primary" onClick={() => setStep({ kind: "password", purpose: "enroll", method: choice })}>
                <ShieldCheck size={13} /> Set up {METHODS[choice].label.toLowerCase()}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <PasswordDialog
        open={step?.kind === "password"}
        title={
          passwordStep?.purpose === "disable"
            ? "Turn off two-factor?"
            : passwordStep?.purpose === "recovery"
              ? "Generate new recovery codes?"
              : "Confirm it's you"
        }
        description={
          passwordStep?.purpose === "recovery"
            ? "Your current recovery codes will stop working."
            : "Enter your current password to continue."
        }
        confirmLabel={passwordStep?.purpose === "disable" ? "Turn off" : "Continue"}
        danger={passwordStep?.purpose === "disable"}
        onClose={close}
        onSubmit={afterPassword}
      />

      {totpStep && (
        <CodeDialog
          key={totpStep.enrollment.challenge_token}
          open={step?.kind === "totp"}
          title="Scan with your authenticator app"
          onClose={close}
          onSubmit={(code) => confirm(totpStep.enrollment.challenge_token, code)}
        >
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
            <img
              src={totpStep.enrollment.qr_code}
              alt="QR code to add this account to an authenticator app"
              className="size-40 shrink-0 rounded-md bg-white p-1"
            />
            <div className="min-w-0 space-y-2 text-xs text-[#999]">
              <p>Scan the code, or enter this key manually:</p>
              <code className="block rounded-md border border-white/[0.09] bg-[#151515] p-2 font-mono text-[11px] break-all text-[#ddd]">
                {totpStep.enrollment.secret.match(/.{1,4}/g)?.join(" ")}
              </code>
              <CopyButton text={totpStep.enrollment.secret} label="Copy key" />
            </div>
          </div>
        </CodeDialog>
      )}

      {emailStep && (
        <CodeDialog
          key={emailStep.enrollment.challenge_token}
          open={step?.kind === "email"}
          title="Check your email"
          onClose={close}
          onSubmit={(code) => confirm(emailStep.enrollment.challenge_token, code)}
        >
          <p className="text-xs text-[#999]">
            We sent a 6-digit code to <span className="text-[#ddd]">{emailStep.enrollment.destination_hint}</span>.
          </p>
        </CodeDialog>
      )}

      {codesStep && (
        <RecoveryCodesDialog
          key={codesStep.codes[0]}
          open={step?.kind === "codes"}
          codes={codesStep.codes}
          onClose={close}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function PasswordDialog({
  open,
  title,
  description,
  confirmLabel,
  danger,
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  onClose: () => void;
  onSubmit: (password: string) => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onSubmit(String(new FormData(event.currentTarget).get("password") ?? ""));
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title={title} description={description} size="sm">
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger" title={error} />}
        <Field label="Current password">
          <PasswordInput name="password" autoComplete="current-password" maxLength={128} required autoFocus />
        </Field>
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant={danger ? "danger" : "primary"} loading={pending}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function CodeDialog({
  open,
  title,
  children,
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onSubmit: (code: string) => Promise<void>;
}) {
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onSubmit(code);
    } catch (err) {
      setError(message(err));
      setCode("");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title={title}>
      <form onSubmit={submit} className="space-y-4">
        {children}
        {error && <Alert tone="danger" title={error} />}
        <Field label="6-digit code">
          <Input
            name="code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            className="text-center font-mono text-lg tracking-[0.5em]"
            required
            autoFocus
          />
        </Field>
        <div className="flex justify-end gap-2 border-t border-white/[0.08] pt-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending} disabled={code.length !== 6}>
            Turn on two-factor
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function RecoveryCodesDialog({ open, codes, onClose }: { open: boolean; codes: string[]; onClose: () => void }) {
  const [saved, setSaved] = useState(false);
  const text = codes.join("\n");

  function download() {
    const url = URL.createObjectURL(new Blob([`Recovery codes (each works once)\n\n${text}\n`], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
    setSaved(true);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && saved && onClose()}
      title="Save your recovery codes"
      description="Each code works once. Use one if you lose your phone or cannot get the email. You won't see them again."
    >
      <div className="space-y-4">
        <ol className="grid grid-cols-2 gap-2 rounded-md border border-white/[0.09] bg-[#151515] p-3 font-mono text-xs text-[#ddd]">
          {codes.map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-2">
          <CopyButton text={text} label="Copy all" onCopied={() => setSaved(true)} />
          <Button onClick={download}>
            <Download size={13} /> Download
          </Button>
        </div>
        <div className="flex justify-end border-t border-white/[0.08] pt-4">
          <Button variant="primary" disabled={!saved} onClick={onClose}>
            I've saved them
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function CopyButton({ text, label, onCopied }: { text: string; label: string; onCopied?: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          onCopied?.();
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          // clipboard unavailable (insecure context); user can select the text instead
        }
      }}
    >
      <Copy size={12} /> {copied ? "Copied" : label}
    </Button>
  );
}
