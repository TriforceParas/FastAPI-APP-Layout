import { Fragment, useEffect, useMemo, useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, Eye, Lock, Pencil, Plus, RotateCcw, Save, Trash2, Users } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import {
  Alert,
  AlertDialog,
  Badge,
  Button,
  Card,
  CardContent,
  Checkbox,
  Dialog,
  ErrorState,
  Field,
  Input,
  PageSkeleton,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
  useToast,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import type { RoleDetail, RoleSummary, Screen } from "@/features/roles/types";
import { useResource } from "@/lib/use-resource";

type Access = { read: boolean; write: boolean };
type Kind = "read" | "write";
type Tri = "all" | "some" | "none";
/** Permissions are stored per LEAF screen id (a page's features, or a page without features). */
type Draft = { access: Record<number, Access>; landing: number | null };

const toDraft = (role: RoleDetail): Draft => ({
  access: Object.fromEntries(role.access.map((a) => [a.screen_id, { read: a.can_read, write: a.can_write }])),
  landing: role.default_screen_id,
});

const sameDraft = (a: Draft, b: Draft) =>
  a.landing === b.landing &&
  Object.keys({ ...a.access, ...b.access }).every((id) => {
    const x = a.access[Number(id)];
    const y = b.access[Number(id)];
    return !!x?.read === !!y?.read && !!x?.write === !!y?.write;
  });

const message = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong.");

export function RolesPage() {
  const toast = useToast();
  const { can } = useAuth();
  const canWrite = can("roles", "write");

  const screensRes = useResource(() => api.get<Screen[]>("/screens"), []);
  const rolesRes = useResource(() => api.get<RoleSummary[]>("/roles"), []);
  const screens = useMemo(() => screensRes.data ?? [], [screensRes.data]);
  const roles = useMemo(() => rolesRes.data ?? [], [rolesRes.data]);

  const [roleId, setRoleId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, RoleDetail>>({});
  // Unsaved edits are kept per role, so switching roles never loses work.
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<"create" | "edit" | "delete" | null>(null);

  // Select the first role when nothing (or a deleted role) is selected. A just-created role is
  // already in `details` before the list reloads, so it is never treated as gone.
  useEffect(() => {
    const known = roleId !== null && (roles.some((r) => r.id === roleId) || details[roleId] !== undefined);
    if (!known && roles.length > 0) setRoleId(roles[0]!.id);
  }, [roles, roleId, details]);

  // Load every role's permissions up front (roles are few), so switching roles is instant.
  useEffect(() => {
    const missing = roles.filter((r) => !details[r.id]).map((r) => r.id);
    if (missing.length === 0) return;
    let cancelled = false;
    Promise.all(missing.map((id) => api.get<RoleDetail>(`/roles/${id}`)))
      .then((loaded) => {
        if (!cancelled) setDetails((all) => ({ ...all, ...Object.fromEntries(loaded.map((d) => [d.id, d])) }));
      })
      .catch((err) => !cancelled && toast.error("Could not load roles", message(err)));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roles, toast]);

  // --- screen tree helpers -------------------------------------------------
  const pages = useMemo(() => screens.filter((s) => s.parent_screen_id === null), [screens]);
  const childrenOf = (page: Screen) => screens.filter((s) => s.parent_screen_id === page.id);
  const leavesOf = (page: Screen) => {
    const children = childrenOf(page);
    return children.length > 0 ? children : [page];
  };
  const allLeafIds = pages.flatMap(leavesOf).map((s) => s.id);

  if (screensRes.error || rolesRes.error) {
    return (
      <ErrorState
        description={(screensRes.error ?? rolesRes.error)!.message}
        onRetry={() => {
          void screensRes.reload();
          void rolesRes.reload();
        }}
      />
    );
  }
  const role = roleId !== null ? details[roleId] : undefined;
  if (!role || screens.length === 0) return <PageSkeleton variant="table" label="Loading roles" />;

  // --- current draft ----------------------------------------------------------
  const baseline = toDraft(role);
  const draft = drafts[role.id] ?? baseline;
  const dirty = !sameDraft(draft, baseline);
  const locked = role.is_system || !canWrite;

  const get = (id: number): Access => draft.access[id] ?? { read: false, write: false };
  const tri = (ids: number[], kind: Kind): Tri => {
    const n = ids.filter((id) => get(id)[kind]).length;
    return n === 0 ? "none" : n === ids.length ? "all" : "some";
  };
  const canOpen = (page: Screen) => leavesOf(page).some((l) => get(l.id).read);
  const openablePages = pages.filter(canOpen);
  const needsLanding = openablePages.length > 0 && draft.landing === null;
  const canSave = dirty && !needsLanding && !locked && !saving;

  /**
   * The ONE place permissions change. Every checkbox (feature, page master
   * checkbox, column header) calls this with the leaf ids it controls.
   * Write implies Read: ticking Write ticks Read; unticking Read unticks Write.
   */
  function apply(ids: number[], kind: Kind, checked: boolean) {
    const access = { ...draft.access };
    for (const id of ids) {
      const cur = get(id);
      access[id] =
        kind === "write"
          ? { read: checked ? true : cur.read, write: checked }
          : { read: checked, write: checked ? cur.write : false };
    }
    // The landing page must stay a page this role can open.
    const landingPage = pages.find((p) => p.id === draft.landing);
    const stillOpen = landingPage !== undefined && leavesOf(landingPage).some((l) => access[l.id]?.read);
    setDrafts((d) => ({ ...d, [role!.id]: { access, landing: stillOpen ? draft.landing : null } }));
  }

  const selectLanding = (value: string) =>
    setDrafts((d) => ({ ...d, [role.id]: { ...draft, landing: value ? Number(value) : null } }));

  const toggle = (id: number) =>
    setExpanded((cur) => {
      const next = new Set(cur);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const clearDraft = (id = role.id) => setDrafts(({ [id]: _discarded, ...rest }) => rest);

  const body = (name: string, description: string | null, d: Draft) => ({
    name,
    description,
    default_screen_id: d.landing,
    access: allLeafIds.map((id) => ({
      screen_id: id,
      can_read: !!d.access[id]?.read,
      can_write: !!d.access[id]?.write,
    })),
  });

  async function save() {
    setSaving(true);
    try {
      const saved = await api.put<RoleDetail>(`/roles/${role!.id}`, body(role!.name, role!.description, draft));
      setDetails((all) => ({ ...all, [saved.id]: saved }));
      clearDraft(saved.id);
      void rolesRes.reload();
      toast.success(`${saved.name} updated`, "Users with this role get the new permissions immediately.");
    } catch (err) {
      toast.error("Could not save role", message(err));
    } finally {
      setSaving(false);
    }
  }

  const unsavedElsewhere = Object.keys(drafts)
    .map(Number)
    .filter((id) => id !== role.id && details[id] && !sameDraft(drafts[id]!, toDraft(details[id]!)));

  const cell = (ids: number[], kind: Kind, label: string) => {
    const state = tri(ids, kind);
    return (
      <Checkbox
        className="size-4"
        aria-label={label}
        disabled={locked}
        checked={state === "all"}
        indeterminate={state === "some"}
        onChange={(e) => apply(ids, kind, e.target.checked)}
      />
    );
  };

  return (
    <>
      <PageHeader
        eyebrow="People & access"
        title="Roles"
        description="Choose what each role can see and change, and where its users land after signing in."
        actions={
          canWrite && (
            <>
              {dirty && (
                <Badge tone="warning" className="self-center">
                  Unsaved changes
                </Badge>
              )}
              <Button onClick={() => setDialog("create")}>
                <Plus size={13} /> New role
              </Button>
              <Button onClick={() => clearDraft()} disabled={!dirty || saving}>
                <RotateCcw size={13} /> Discard
              </Button>
              <Button variant="primary" onClick={() => void save()} disabled={!canSave} loading={saving}>
                <Save size={13} /> Save changes
              </Button>
            </>
          )
        }
      />

      {!canWrite && (
        <Alert tone="info" title="View only" className="mb-5">
          <span className="inline-flex items-center gap-1.5">
            <Eye size={11} /> You can see roles but not change them.
          </span>
        </Alert>
      )}

      <Card>
        <CardContent className="grid gap-4 border-b border-white/[0.08] sm:grid-cols-2">
          <Field
            label="Role"
            htmlFor="role-select"
            hint={
              unsavedElsewhere.length > 0
                ? `${unsavedElsewhere.length} other role(s) have unsaved changes.`
                : (role.description ?? undefined)
            }
          >
            <Select id="role-select" value={role.id} onChange={(e) => setRoleId(Number(e.target.value))}>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                  {r.is_system ? " (system)" : ""}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Default landing page"
            htmlFor="landing-select"
            hint={
              needsLanding
                ? undefined
                : "Where users with this role land after signing in. If a user has several roles, their first role decides."
            }
            error={needsLanding ? "Choose a landing page for this role." : undefined}
          >
            <Select
              id="landing-select"
              value={draft.landing ?? ""}
              disabled={locked || openablePages.length === 0}
              onChange={(e) => selectLanding(e.target.value)}
              aria-invalid={needsLanding || undefined}
            >
              <option value="">
                {openablePages.length === 0 ? "Grant Read access to a page first" : "Select a page…"}
              </option>
              {openablePages.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.path})
                </option>
              ))}
            </Select>
          </Field>
        </CardContent>

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.08] bg-white/[0.02] px-4 py-2.5 text-[11px] text-[#999]">
          <span className="inline-flex items-center gap-2">
            {role.is_system ? (
              <>
                <Lock size={12} /> System role: it always has full access and cannot be edited.
              </>
            ) : (
              <>
                <Users size={12} /> Assigned to {role.user_count} {role.user_count === 1 ? "user" : "users"}
              </>
            )}
          </span>
          {canWrite && !role.is_system && (
            <span className="flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setDialog("edit")}>
                <Pencil size={12} /> Edit details
              </Button>
              <Button size="sm" variant="ghost" className="text-rose-300" onClick={() => setDialog("delete")}>
                <Trash2 size={12} /> Delete role
              </Button>
            </span>
          )}
        </div>

        <Table className="min-w-[600px]">
          <TableHeader>
            <tr>
              <TableHead>Page</TableHead>
              <TableHead className="w-40">
                <label className="inline-flex cursor-pointer items-center gap-2">
                  {cell(allLeafIds, "read", "Grant Read on all pages")}
                  Read permission
                </label>
              </TableHead>
              <TableHead className="w-44">
                <label className="inline-flex cursor-pointer items-center gap-2">
                  {cell(allLeafIds, "write", "Grant Write on all pages")}
                  Write permission
                </label>
              </TableHead>
            </tr>
          </TableHeader>
          <TableBody>
            {pages.map((page) => {
              const features = childrenOf(page);
              const leafIds = leavesOf(page).map((l) => l.id);
              const open = expanded.has(page.id);
              const readCount = leafIds.filter((id) => get(id).read).length;
              return (
                <Fragment key={page.id}>
                  <TableRow>
                    <TableCell>
                      <div className="flex items-start gap-2">
                        {features.length > 0 ? (
                          <button
                            type="button"
                            aria-expanded={open}
                            aria-label={`${open ? "Collapse" : "Expand"} ${page.name} features`}
                            onClick={() => toggle(page.id)}
                            className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded text-[#888] hover:bg-white/[0.06] hover:text-white"
                          >
                            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </button>
                        ) : (
                          <span className="size-5 shrink-0" />
                        )}
                        <div>
                          <div className="flex flex-wrap items-center gap-2 font-medium text-[#dedede]">
                            {page.name}
                            {draft.landing === page.id && <Badge tone="info">Landing page</Badge>}
                            {features.length > 0 && (
                              <Badge tone={readCount === 0 ? "neutral" : "success"}>
                                {readCount} of {features.length} features
                              </Badge>
                            )}
                          </div>
                          <p className="mt-0.5 text-[11px] text-[#707070]">
                            <span className="font-mono">{page.path}</span>
                            {page.description ? ` · ${page.description}` : ""}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>{cell(leafIds, "read", `Read access for ${page.name}`)}</TableCell>
                    <TableCell>{cell(leafIds, "write", `Write access for ${page.name}`)}</TableCell>
                  </TableRow>

                  {open &&
                    features.map((f) => (
                      <TableRow key={f.id} className="bg-white/[0.012]">
                        <TableCell>
                          <div className="ml-7 border-l border-white/[0.08] pl-4">
                            <p className="text-xs text-[#cfcfcf]">{f.name}</p>
                            {f.description && <p className="mt-0.5 text-[11px] text-[#707070]">{f.description}</p>}
                          </div>
                        </TableCell>
                        <TableCell>{cell([f.id], "read", `Read access for feature ${f.name} on ${page.name}`)}</TableCell>
                        <TableCell>{cell([f.id], "write", `Write access for feature ${f.name} on ${page.name}`)}</TableCell>
                      </TableRow>
                    ))}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>

        <p className="border-t border-white/[0.08] px-4 py-3 text-[11px] leading-5 text-[#6f6f6f]">
          Tick a page to give full access to everything on it, or expand it to choose individual features. Write
          always includes Read, because nobody can change what they cannot open. Removing Read also removes Write.
          Settings (own profile, password and devices) is always available to every signed-in user.
        </p>
      </Card>

      <RoleDetailsDialog
        open={dialog === "create" || dialog === "edit"}
        mode={dialog === "edit" ? "edit" : "create"}
        role={dialog === "edit" ? role : undefined}
        onClose={() => setDialog(null)}
        onSubmit={async (name, description) => {
          if (dialog === "edit") {
            const saved = await api.put<RoleDetail>(`/roles/${role.id}`, body(name, description, baseline));
            setDetails((all) => ({ ...all, [saved.id]: saved }));
            toast.success("Role updated");
          } else {
            const created = await api.post<RoleDetail>("/roles", {
              name,
              description,
              default_screen_id: null,
              access: [],
            });
            setDetails((all) => ({ ...all, [created.id]: created }));
            setRoleId(created.id);
            toast.success(`${created.name} created`, "Now choose its pages and a landing page.");
          }
          await rolesRes.reload();
        }}
      />

      <AlertDialog
        open={dialog === "delete"}
        onOpenChange={(open) => !open && setDialog(null)}
        title={`Delete ${role.name}?`}
        description={
          role.user_count > 0
            ? `This role is assigned to ${role.user_count} user(s). Reassign them on the Users page first.`
            : "This permanently removes the role and its permissions."
        }
        confirmLabel="Delete role"
        onConfirm={async () => {
          try {
            await api.delete(`/roles/${role.id}`);
            clearDraft(role.id);
            setDetails(({ [role.id]: _gone, ...rest }) => rest);
            setRoleId(null);
            await rolesRes.reload();
            toast.success("Role deleted");
          } catch (err) {
            toast.error("Could not delete role", message(err));
          }
        }}
      />
    </>
  );
}

function RoleDetailsDialog({
  open,
  mode,
  role,
  onClose,
  onSubmit,
}: {
  open: boolean;
  mode: "create" | "edit";
  role?: RoleDetail;
  onClose: () => void;
  onSubmit: (name: string, description: string | null) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim() || null;
    setPending(true);
    setError(null);
    try {
      await onSubmit(name, description);
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
      onOpenChange={(next) => {
        setError(null);
        if (!next) onClose();
      }}
      title={mode === "create" ? "New role" : `Edit ${role?.name ?? "role"}`}
      description={mode === "create" ? "You can choose its pages after creating it." : undefined}
    >
      <form key={`${mode}-${role?.id ?? "new"}`} onSubmit={submit} className="space-y-4">
        {error && (
          <Alert tone="danger" title="Could not save">
            {error}
          </Alert>
        )}
        <Field label="Name">
          <Input name="name" defaultValue={role?.name} minLength={2} maxLength={100} required autoFocus />
        </Field>
        <Field label="Description" hint="Optional">
          <Textarea name="description" defaultValue={role?.description ?? ""} maxLength={255} className="min-h-16" />
        </Field>
        <div className="flex justify-end gap-2 border-t border-white/[0.08] pt-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>
            {mode === "create" ? (
              <>
                <Plus size={13} /> Create role
              </>
            ) : (
              "Save details"
            )}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
