import { useState, type FormEvent } from "react";
import { Monitor } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { applyTheme, useTheme } from "@/components/layout/theme-toggle";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DescriptionList,
  Field,
  Input,
  PasswordInput,
  RadioGroup,
  Skeleton,
  Tabs,
  useToast,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { describeUserAgent, formatDate, formatRelative } from "@/lib/format";
import type { SessionInfo } from "@/features/settings/types";
import type { User } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { TwoFactorSection } from "@/features/settings/two-factor-section";

function message(err: unknown) {
  return err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong.";
}

export function SettingsPage() {
  const { status } = useAuth();
  return (
    <>
      <PageHeader eyebrow="Account" title="Settings" description="Manage your profile, password and signed-in devices." />
      {status?.auth_bypass ? (
        <Alert tone="warning" title="Account settings are unavailable while authentication is bypassed">
          Delete the <code>.auth-bypass</code> file (or set AUTH_ENABLED=true) and sign in with a real account.
        </Alert>
      ) : (
        <Tabs
          items={[
            { value: "profile", label: "Profile", content: <ProfileSection /> },
            { value: "security", label: "Password", content: <PasswordSection /> },
            { value: "two-factor", label: "Two-factor", content: <TwoFactorSection /> },
            { value: "sessions", label: "Sessions", content: <SessionsSection /> },
            { value: "appearance", label: "Appearance", content: <AppearanceSection /> },
          ]}
        />
      )}
    </>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [pending, setPending] = useState(false);
  if (!user) return null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
    setPending(true);
    try {
      setUser(await api.patch<User>("/me", { name }));
      toast.success("Profile updated");
    } catch (err) {
      toast.error("Could not update profile", message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.6fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your name is shown to other members of the workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="max-w-md space-y-4">
            <Field label="Full name">
              <Input name="name" defaultValue={user.name} minLength={2} maxLength={100} required />
            </Field>
            <Field label="Email address" hint="Ask an administrator to change your email.">
              <Input value={user.email} disabled readOnly />
            </Field>
            <Button type="submit" variant="primary" loading={pending}>
              Save profile
            </Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="py-1">
          <DescriptionList
            items={[
              {
                label: user.roles.length > 1 ? "Roles" : "Role",
                value: (
                  <span className="flex flex-wrap gap-1.5">
                    {user.roles.length === 0 && <Badge>No role</Badge>}
                    {user.roles.map((role, index) => (
                      <Badge key={role.id} tone={index === 0 ? "success" : "neutral"}>
                        {role.name}
                      </Badge>
                    ))}
                  </span>
                ),
              },
              { label: "Member since", value: formatDate(user.created_at) },
              { label: "Last sign-in", value: formatRelative(user.last_login_at) },
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function PasswordSection() {
  const toast = useToast();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    if (form.get("new") !== form.get("confirm")) {
      setError("New passwords do not match.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api.post("/me/password", { current_password: form.get("current"), new_password: form.get("new") });
      formEl.reset();
      toast.success("Password changed", "Your other devices were signed out.");
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>Changing your password signs out every other device.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert tone="danger" title="Could not change password">{error}</Alert>}
          <Field label="Current password">
            <PasswordInput name="current" autoComplete="current-password" maxLength={128} required />
          </Field>
          <Field label="New password" hint="At least 12 characters. A passphrase works well.">
            <PasswordInput name="new" autoComplete="new-password" minLength={12} maxLength={128} required showStrength />
          </Field>
          <Field label="Confirm new password">
            <PasswordInput name="confirm" autoComplete="new-password" minLength={12} maxLength={128} required />
          </Field>
          <Button type="submit" variant="primary" loading={pending}>
            Update password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function SessionsSection() {
  const toast = useToast();
  const { data, loading, reload } = useResource(() => api.get<SessionInfo[]>("/me/sessions"), []);

  async function revoke(id: string) {
    try {
      await api.delete(`/me/sessions/${id}`);
      toast.success("Session signed out");
      await reload();
    } catch (err) {
      toast.error("Could not revoke session", message(err));
    }
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>Signed-in devices</CardTitle>
        <CardDescription>Sign out any session you don't recognise, then change your password.</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {loading && !data ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <div className="divide-y divide-white/[0.07]">
            {data?.map((session) => (
              <div key={session.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-white/[0.04] text-[#888]">
                    <Monitor size={15} />
                  </span>
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xs font-medium text-[#ddd]">
                      {describeUserAgent(session.user_agent)}
                      {session.current && <Badge tone="success">This device</Badge>}
                    </p>
                    <p className="mt-0.5 truncate text-[10px] text-[#666]">
                      {session.ip_address ?? "Unknown IP"} · active {formatRelative(session.last_seen_at)} · signed
                      in {formatRelative(session.created_at)}
                    </p>
                  </div>
                </div>
                {!session.current && (
                  <Button size="sm" variant="danger" onClick={() => void revoke(session.id)}>
                    Sign out
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AppearanceSection() {
  const theme = useTheme();
  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Appearance</CardTitle>
        <CardDescription>Saved on this device.</CardDescription>
      </CardHeader>
      <CardContent>
        <div
          onChange={(event) => {
            const target = event.target as HTMLInputElement;
            if (target.name === "theme") applyTheme(target.value as "dark" | "light");
          }}
        >
          <RadioGroup
            key={theme}
            name="theme"
            defaultValue={theme}
            options={[
              { value: "dark", label: "Dark", description: "Low-glare neutral greys." },
              { value: "light", label: "Light", description: "High-contrast for bright rooms." },
            ]}
          />
        </div>
      </CardContent>
    </Card>
  );
}
