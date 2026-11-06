import type { ReactNode } from "react";
import { Link } from "react-router";
import {
  Activity,
  ArrowRight,
  KeyRound,
  LockKeyhole,
  MonitorSmartphone,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import {
  Badge,
  buttonClass,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ErrorState,
  Skeleton,
  StatCard,
  StatGrid,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { formatAuditAction, formatNumber, formatRelative } from "@/lib/format";
import type { DashboardSummary } from "@/features/dashboard/types";
import { useResource } from "@/lib/use-resource";

const OUTCOME_TONE = { success: "success", failure: "danger", denied: "warning" } as const;

/**
 * Every section is a dashboard FEATURE (app/features/rbac/registry.py) with its own
 * permission. The API only returns the numbers the user may read; the page
 * only renders the sections they may read.
 */
export function DashboardPage() {
  const { user, can } = useAuth();
  const { data, error, loading, reload } = useResource(() => api.get<DashboardSummary>("/dashboard/summary"), []);

  const today = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "2-digit", month: "long" }).format(
    new Date(),
  );
  const value = (v: number | null | undefined, width = "w-16") =>
    loading ? <Skeleton className={`h-8 ${width}`} /> : formatNumber(v);

  const stats: ReactNode[] = [];
  if (can("dashboard.user_stats")) {
    stats.push(
      <StatCard
        key="users"
        label="Total users"
        icon={Users}
        value={value(data?.users_total)}
        note={`${formatNumber(data?.users_active)} active`}
        href={can("users") ? "/users" : undefined}
      />,
      <StatCard
        key="admins"
        label="Administrators"
        icon={ShieldCheck}
        value={value(data?.admins)}
        note="Users with the Administrator role"
      />,
    );
  }
  if (can("dashboard.locked_accounts")) {
    stats.push(
      <StatCard
        key="locked"
        label="Locked accounts"
        icon={LockKeyhole}
        value={value(data?.users_locked)}
        note="Temporarily locked after failed sign-ins"
        href={can("users") ? "/users?state=locked" : undefined}
      />,
    );
  }
  if (can("dashboard.active_sessions")) {
    stats.push(
      <StatCard
        key="sessions"
        label="Active sessions"
        icon={MonitorSmartphone}
        value={value(data?.sessions_active)}
        note={`${formatNumber(data?.my_sessions)} of them are yours · last sign-in ${formatRelative(data?.my_last_login_at)}`}
        href="/settings"
      />,
    );
  }

  const showActivity = can("dashboard.recent_activity");
  const showQuickActions = can("dashboard.quick_actions");

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={today}
        title={`Good to see you, ${user?.name.split(" ")[0] ?? "there"}`}
        description="Here's what is happening in your workspace."
        actions={
          can("users", "write") && (
            <Link to="/users?new=1" className={buttonClass({ variant: "primary" })}>
              <UserPlus size={13} /> Add user
            </Link>
          )
        }
      />

      {error ? (
        <ErrorState description={error.message} onRetry={reload} />
      ) : (
        <>
          {stats.length > 0 && (
            <StatGrid columns={Math.min(stats.length, 4) as 1 | 2 | 3 | 4}>{stats}</StatGrid>
          )}

          {(showActivity || showQuickActions) && (
            <section
              className={
                showActivity && showQuickActions
                  ? "grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.65fr)]"
                  : "grid gap-5"
              }
            >
              {showActivity && (
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Recent activity</CardTitle>
                      <p className="mt-1 text-xs text-[#737373]">
                        {can("audit") ? "Latest security events across the workspace." : "Your latest account events."}
                      </p>
                    </div>
                    {can("audit") && (
                      <Link to="/audit" className="text-xs font-medium text-emerald-400 hover:text-emerald-300">
                        View all
                      </Link>
                    )}
                  </CardHeader>
                  <CardContent className="p-0">
                    {loading ? (
                      <div className="space-y-3 p-4">
                        {[0, 1, 2, 3].map((i) => (
                          <Skeleton key={i} className="h-9 w-full" />
                        ))}
                      </div>
                    ) : !data?.recent_events?.length ? (
                      <div className="px-4 py-12 text-center text-xs text-[#777]">No activity yet.</div>
                    ) : (
                      <div className="divide-y divide-white/[0.07]">
                        {data.recent_events.map((event) => (
                          <div key={event.id} className="flex items-center justify-between gap-4 px-4 py-3">
                            <div className="min-w-0">
                              <p className="truncate text-xs font-medium text-[#ddd]">
                                {formatAuditAction(event.action)}
                              </p>
                              <p className="mt-1 truncate text-[10px] text-[#666]">
                                {event.actor_email ?? "System"}
                                {event.ip_address ? ` · ${event.ip_address}` : ""}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-3">
                              <Badge tone={OUTCOME_TONE[event.outcome] ?? "neutral"}>{event.outcome}</Badge>
                              <span className="hidden w-20 text-right text-[10px] text-[#777] sm:inline">
                                {formatRelative(event.created_at)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {showQuickActions && (
                <div className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle>Quick actions</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {can("users") && <QuickLink to="/users" icon={Users} label="Manage users" />}
                      {can("roles") && <QuickLink to="/roles" icon={ShieldCheck} label="Manage roles and permissions" />}
                      {can("audit") && <QuickLink to="/audit" icon={Activity} label="Review the audit log" />}
                      <QuickLink to="/settings" icon={KeyRound} label="Change your password" />
                      <QuickLink to="/settings" icon={MonitorSmartphone} label="Review signed-in devices" />
                    </CardContent>
                  </Card>
                  <div className="callout-warning rounded-lg border border-amber-300/15 bg-amber-300/[0.04] p-4 text-xs leading-5 text-amber-100/70">
                    This dashboard is a starting point. Add your own features in <code>src/features</code> and register
                    them in <code>src/app/navigation.ts</code> and <code>app/features/rbac/registry.py</code>.
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}

function QuickLink({ to, icon: Icon, label }: { to: string; icon: typeof Users; label: string }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between rounded-md border border-white/[0.08] px-3 py-2.5 text-xs text-[#bbb] hover:bg-white/[0.03] hover:text-white"
    >
      <span className="flex items-center gap-2.5">
        <Icon size={14} className="text-[#777]" />
        {label}
      </span>
      <ArrowRight size={13} className="text-[#666]" />
    </Link>
  );
}
