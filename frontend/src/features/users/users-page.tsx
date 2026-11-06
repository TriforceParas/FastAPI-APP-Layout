import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import {
  ChevronDown,
  ChevronUp,
  KeyRound,
  LockOpen,
  LogOut,
  MoreHorizontal,
  Pencil,
  Plus,
  ShieldOff,
  Trash2,
  UserRoundCog,
  X,
} from "lucide-react";

import { DataTablePage } from "@/components/layout/data-table-page";
import {
  Alert,
  AlertDialog,
  Avatar,
  Badge,
  Button,
  Checkbox,
  Dialog,
  DropdownItem,
  DropdownMenu,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  Pagination,
  PasswordInput,
  SearchInput,
  Select,
  Separator,
  Skeleton,
  useToast,
  ColumnToggle,
  DataTable,
  useColumnVisibility,
  useLatest,
  type DataTableColumn,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { formatDate, formatRelative } from "@/lib/format";
import { useLookup } from "@/lib/lookups";
import type { Page, User } from "@/lib/types";
import { useDebounced, useResource } from "@/lib/use-resource";

const PAGE_SIZE = 20;

function message(err: unknown) {
  return err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong.";
}

function str(form: FormData, key: string) {
  const v = form.get(key);
  return typeof v === "string" ? v : "";
}

export function UsersPage() {
  const { user: me, can } = useAuth();
  const canWrite = can("users", "write");
  const { data: roleOptions } = useLookup("roles");
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const q = useDebounced(query);
  const roleId = params.get("role") ?? "";
  const state = params.get("state") ?? "";
  const [page, setPage] = useState(1);

  const [creating, setCreating] = useState(params.get("new") === "1");
  const [editing, setEditing] = useState<User | null>(null);
  const [resetting, setResetting] = useState<User | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);

  useEffect(() => setPage(1), [q, roleId, state]);

  const { data, error, loading, reload } = useResource(
    () => api.get<Page<User>>("/users", { q, role_id: roleId || undefined, state, page, page_size: PAGE_SIZE }),
    [q, roleId, state, page],
  );

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("new");
    setParams(next, { replace: true });
  }

  async function action(fn: () => Promise<unknown>, success: string) {
    try {
      await fn();
      toast.success(success);
      await reload();
    } catch (err) {
      toast.error("Action failed", message(err));
    }
  }

  const columns = useMemo<DataTableColumn<User>[]>(
    () => [
      {
        id: "user",
        header: "User",
        hideable: false,
        cell: (user) => (
          <div className="flex items-center gap-3">
            <Avatar name={user.name} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-medium text-[#dedede]">
                <span className="truncate">{user.name}</span>
                {user.id === me?.id && <Badge tone="info">You</Badge>}
              </div>
              <p className="mt-0.5 truncate text-[11px] text-[#707070]">{user.email}</p>
            </div>
          </div>
        ),
      },
      {
        id: "roles",
        header: "Roles",
        cell: (user) => (
          <div className="flex max-w-xs flex-wrap gap-1.5">
            {user.roles.length === 0 && <Badge tone="danger">No role</Badge>}
            {user.roles.map((r, index) => (
              <Badge key={r.id} tone={index === 0 ? "success" : "neutral"}>
                {r.name}
              </Badge>
            ))}
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (user) => (
          <div className="flex flex-wrap gap-1.5">
            {!user.is_active ? (
              <Badge tone="danger">Deactivated</Badge>
            ) : user.is_locked ? (
              <Badge tone="warning">Locked</Badge>
            ) : (
              <Badge tone="success">Active</Badge>
            )}
            {user.must_change_password && <Badge tone="info">Temp password</Badge>}
            {user.mfa_method && (
              <Badge tone="success" title={user.mfa_method === "totp" ? "Authenticator app" : "Email code"}>
                2FA
              </Badge>
            )}
          </div>
        ),
      },
      {
        id: "last_login",
        header: "Last sign-in",
        className: "whitespace-nowrap text-[#888]",
        cell: (user) => formatRelative(user.last_login_at),
      },
      {
        id: "created",
        header: "Added",
        className: "whitespace-nowrap text-[#777]",
        cell: (user) => formatDate(user.created_at),
      },
      {
        id: "actions",
        header: <span className="sr-only">Actions</span>,
        label: "Actions",
        hideable: false,
        align: "right",
        cell: (user) => (canWrite ? <UserActions user={user} isMe={user.id === me?.id} /> : null),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [me?.id, canWrite],
  );
  const columnState = useColumnVisibility("users", columns);

  function UserActions({ user, isMe }: { user: User; isMe: boolean }) {
    return (
      <DropdownMenu
        align="right"
        label={`Actions for ${user.name}`}
        className="size-8 justify-center text-[#888] hover:bg-white/[0.05] hover:text-white"
        trigger={<MoreHorizontal size={15} />}
      >
        <DropdownItem onClick={() => setEditing(user)}>
          <Pencil size={13} /> Edit details
        </DropdownItem>
        <DropdownItem disabled={isMe} onClick={() => setResetting(user)}>
          <KeyRound size={13} /> Reset password
        </DropdownItem>
        {user.is_locked && (
          <DropdownItem onClick={() => void action(() => api.post(`/users/${user.id}/unlock`), `${user.name} unlocked`)}>
            <LockOpen size={13} /> Unlock account
          </DropdownItem>
        )}
        <DropdownItem
          onClick={() =>
            void action(
              () => api.post(`/users/${user.id}/sessions/revoke`),
              isMe ? "Other sessions signed out" : `${user.name} signed out everywhere`,
            )
          }
        >
          <LogOut size={13} /> Sign out everywhere
        </DropdownItem>
        {user.mfa_method && !isMe && (
          <DropdownItem
            onClick={() =>
              void action(
                () => api.post(`/users/${user.id}/mfa/reset`),
                `Two-factor reset for ${user.name}. They can set it up again in Settings.`,
              )
            }
          >
            <ShieldOff size={13} /> Reset two-factor
          </DropdownItem>
        )}
        <Separator className="my-1" />
        <DropdownItem disabled={isMe} className="text-rose-300 hover:text-rose-200" onClick={() => setDeleting(user)}>
          <Trash2 size={13} /> Delete user
        </DropdownItem>
      </DropdownMenu>
    );
  }

  // Keep showing the last selection while a dialog animates out.
  const shownEditing = useLatest(editing);
  const shownResetting = useLatest(resetting);
  const shownDeleting = useLatest(deleting);

  return (
    <>
      <DataTablePage
        eyebrow="People & access"
        title="Users"
        description="Create accounts, assign roles, reset passwords and revoke access."
        toolbar={
          <>
            <SearchInput
              className="w-full sm:w-64"
              placeholder="Search name or email…"
              aria-label="Search users"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <div className="w-36">
              <Select aria-label="Filter by role" value={roleId} onChange={(e) => setFilter("role", e.target.value)}>
                <option value="">All roles</option>
                {roleOptions?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-36">
              <Select aria-label="Filter by status" value={state} onChange={(e) => setFilter("state", e.target.value)}>
                <option value="">Any status</option>
                <option value="active">Active</option>
                <option value="inactive">Deactivated</option>
                <option value="locked">Locked</option>
              </Select>
            </div>
            <span className="flex items-center gap-2 text-xs text-[#777]">
              <UserRoundCog size={14} />
              {data ? `${data.total} ${data.total === 1 ? "user" : "users"}` : <Skeleton className="h-3 w-14" />}
            </span>
          </>
        }
        actions={
          <>
            <ColumnToggle state={columnState} />
            {canWrite && (
              <Button variant="primary" onClick={() => setCreating(true)}>
                <Plus size={13} /> Add user
              </Button>
            )}
          </>
        }
      >
        {error ? (
          <ErrorState description={error.message} onRetry={reload} />
        ) : (
          <DataTable
            label="Users"
            columns={columnState.visibleColumns}
            rows={data?.items ?? []}
            rowKey={(user) => user.id}
            loading={loading && !data}
            minWidth={760}
            empty={
              <EmptyState
                icon={<UserRoundCog size={22} />}
                title="No users match"
                description="Try a different search or clear the filters."
              />
            }
            footer={
              data && data.total > PAGE_SIZE ? (
                <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
              ) : undefined
            }
          />
        )}
      </DataTablePage>

      <CreateUserDialog
        open={creating}
        onOpenChange={(open) => {
          setCreating(open);
          if (!open && params.get("new")) setFilter("new", "");
        }}
        onCreated={(user) => {
          toast.success("User created", `${user.email} can now sign in.`);
          void reload();
        }}
      />
      {shownEditing && (
        <EditUserDialog
          key={shownEditing.id}
          user={shownEditing}
          open={editing !== null}
          isMe={shownEditing.id === me?.id}
          onClose={() => setEditing(null)}
          onSaved={() => {
            toast.success("Changes saved");
            void reload();
          }}
        />
      )}
      {shownResetting && (
        <ResetPasswordDialog
          key={shownResetting.id}
          user={shownResetting}
          open={resetting !== null}
          onClose={() => setResetting(null)}
          onDone={() => {
            toast.success("Password reset", "All of their sessions were signed out.");
            void reload();
          }}
        />
      )}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${shownDeleting?.name ?? "user"}?`}
        description="This permanently removes the account and signs it out everywhere. Audit history is kept. Consider deactivating instead."
        confirmLabel="Delete user"
        onConfirm={async () => {
          if (deleting) await action(() => api.delete(`/users/${deleting.id}`), "User deleted");
        }}
      />
    </>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * Ordered role picker. Roles come from the `roles` LOOKUP (id + label only), so
 * this works for user managers who have no access to the Roles page.
 * The first role is the primary one: it decides the landing page.
 */
function RolePicker({
  value,
  onChange,
  disabled,
}: {
  value: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
}) {
  const { data: roles, loading } = useLookup("roles");
  const label = (id: number) => roles?.find((r) => r.id === id)?.label ?? "…";
  const available = (roles ?? []).filter((r) => !value.includes(r.id));
  const move = (index: number, delta: number) => {
    const next = [...value];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item!);
    onChange(next);
  };

  return (
    <Field
      label={value.length > 1 ? "Roles" : "Role"}
      hint={
        disabled
          ? "You cannot change your own roles."
          : "Permissions combine across roles. The first role decides where the user lands after signing in."
      }
    >
      <div className="space-y-2">
        {value.length > 0 && (
          <ol className="divide-y divide-white/[0.07] rounded-md border border-white/[0.09]">
            {value.map((id, index) => (
              <li key={id} className="flex items-center gap-2 px-3 py-2 text-xs">
                <span className="w-4 text-[10px] text-[#666] tabular-nums">{index + 1}</span>
                <span className="flex-1 text-[#ddd]">{label(id)}</span>
                {index === 0 && <Badge tone="success">Primary</Badge>}
                {!disabled && (
                  <span className="flex items-center">
                    <IconButton
                      variant="ghost"
                      size="icon"
                      aria-label={`Move ${label(id)} up`}
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                    >
                      <ChevronUp size={13} />
                    </IconButton>
                    <IconButton
                      variant="ghost"
                      size="icon"
                      aria-label={`Move ${label(id)} down`}
                      disabled={index === value.length - 1}
                      onClick={() => move(index, 1)}
                    >
                      <ChevronDown size={13} />
                    </IconButton>
                    <IconButton
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${label(id)}`}
                      onClick={() => onChange(value.filter((v) => v !== id))}
                    >
                      <X size={13} />
                    </IconButton>
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
        {!disabled && loading && <Skeleton className="h-9 w-full" />}
        {!disabled && !loading && (
          <Select
            aria-label="Add a role"
            value=""
            disabled={available.length === 0}
            onChange={(e) => e.target.value && onChange([...value, Number(e.target.value)])}
          >
            <option value="">
              {available.length === 0 ? "All roles assigned" : "Add a role…"}
            </option>
            {available.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </Select>
        )}
      </div>
    </Field>
  )
}

function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (user: User) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [roleIds, setRoleIds] = useState<number[]>([]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      const user = await api.post<User>("/users", {
        name: str(form, "name").trim(),
        email: str(form, "email").trim(),
        role_ids: roleIds,
        password: str(form, "password"),
        must_change_password: form.get("mustChange") === "on",
      });
      onCreated(user);
      setRoleIds([]);
      onOpenChange(false);
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setError(null);
        onOpenChange(next);
      }}
      title="Add user"
      description="Create a sign-in and choose what they can access."
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger" title="Could not create user">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">
            <Input name="name" minLength={2} maxLength={100} required autoFocus />
          </Field>
          <Field label="Email address">
            <Input name="email" type="email" autoComplete="off" maxLength={254} required />
          </Field>
        </div>
        <RolePicker value={roleIds} onChange={setRoleIds} />
        <Field label="Temporary password" hint="At least 12 characters. Share it securely.">
          <PasswordInput name="password" autoComplete="new-password" minLength={12} maxLength={128} required showStrength />
        </Field>
        <Checkbox name="mustChange" defaultChecked label="Require a new password at first sign-in" />
        <div className="flex justify-end gap-2 border-t border-white/[0.08] pt-4">
          <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending} disabled={roleIds.length === 0}>
            <Plus size={13} /> Create user
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function EditUserDialog({
  user,
  open,
  isMe,
  onClose,
  onSaved,
}: {
  user: User;
  open: boolean;
  isMe: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const original = user.roles.map((r) => r.id);
  const [roleIds, setRoleIds] = useState<number[]>(original);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body: Record<string, unknown> = { name: str(form, "name").trim() };
    if (!isMe) {
      if (roleIds.join() !== original.join()) body.role_ids = roleIds;
      body.is_active = str(form, "active") === "true";
    }
    setPending(true);
    setError(null);
    try {
      await api.patch(`/users/${user.id}`, body);
      onSaved();
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()} title={`Edit ${user.name}`} description={user.email}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger" title="Could not save">{error}</Alert>}
        <Field label="Full name">
          <Input name="name" defaultValue={user.name} minLength={2} maxLength={100} required autoFocus />
        </Field>
        <RolePicker value={roleIds} onChange={setRoleIds} disabled={isMe} />
        <Field
          label="Account status"
          hint={isMe ? "You cannot deactivate yourself." : "Deactivation immediately signs the user out everywhere."}
        >
          <Select name="active" defaultValue={String(user.is_active)} disabled={isMe}>
            <option value="true">Active</option>
            <option value="false">Deactivated</option>
          </Select>
        </Field>
        <p className="text-[11px] leading-5 text-[#6f6f6f]">
          Changing a role signs the user out so their new permissions apply immediately.
        </p>
        <div className="flex justify-end gap-2 border-t border-white/[0.08] pt-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending} disabled={roleIds.length === 0}>
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ResetPasswordDialog({
  user,
  open,
  onClose,
  onDone,
}: {
  user: User;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await api.post(`/users/${user.id}/password`, {
        new_password: str(form, "password"),
        must_change_password: form.get("mustChange") === "on",
      });
      onDone();
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => !open && onClose()}
      title={`Reset password for ${user.name}`}
      description="Sets a new password, clears any lockout and signs them out everywhere."
      size="sm"
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger" title="Could not reset password">{error}</Alert>}
        <Field label="New temporary password">
          <PasswordInput
            name="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            autoFocus
            showStrength
          />
        </Field>
        <Checkbox name="mustChange" defaultChecked label="Require a new password at next sign-in" />
        <div className="flex justify-end gap-2 border-t border-white/[0.08] pt-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>
            Reset password
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
