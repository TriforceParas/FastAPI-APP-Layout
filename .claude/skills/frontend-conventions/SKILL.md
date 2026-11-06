---
name: frontend-conventions
description: Conventions for the React 19 + TypeScript + Tailwind v4 frontend of this template (compiled to static files, served by FastAPI) - feature folders, components, data loading, forms, permissions in the UI, styling and theming, accessibility, CSP limits. Load before creating or changing anything under frontend/src.
---

# Frontend Conventions

The UI is a single-page app compiled by Vite into `frontend/dist` and served by FastAPI. There is no Node server at runtime. Where code goes is defined in `project-structure`; API usage in `api-conventions`.

## 1. Files and modules

- One feature per folder in `src/features/<feature>/`: `<feature>-page.tsx`, `components/`, `types.ts`, and optional `api.ts` and `hooks.ts`.
- Kebab-case file names, PascalCase components, named exports (`export function UsersPage()`), no default exports.
- Import with the `@/` alias, never long `../../` chains.
- `components/ui` and `components/layout` are shared and never import from `features/`. Features import `@/components/ui`, `@/lib/*`, `@/features/auth/auth-context`, and other features' `types.ts`, nothing else.
- Keep files focused. Split a page over ~400 lines into `components/` inside the feature (dialogs, tables, pickers).

## 2. Components and the design system

- **Build screens only from `@/components/ui`** (Button, Card, Field, Input, Select, PasswordInput, Table, Pagination, Badge, Dialog, AlertDialog, DropdownMenu, Tabs, StatGrid/StatCard, EmptyState/ErrorState/LoadingState/Skeleton, useToast…) and `@/components/layout` (PageHeader…). The live gallery is at `/components`.
- A missing building block becomes a new reusable component in `components/ui`. Export it from `index.ts` and add it to the gallery, rather than one-off markup in a page.
- Every page starts with `<PageHeader eyebrow title description actions />`, except list pages (next point).
- **List pages** use `<DataTablePage eyebrow title description toolbar actions>` (from `@/components/layout/data-table-page`) with a `<DataTable>` inside:
  - The table fills the remaining screen height. Rows scroll inside it, the column header stays pinned and the scrollbars belong to the table.
  - The title and description slide away once the rows scroll. `toolbar` (search, filters) and `actions` (buttons, `<ColumnToggle>`) always stay visible.
  - Define the columns as `DataTableColumn<T>[]` (`hideable: false` for the main and actions columns, `defaultHidden` for optional ones). Pass them through `useColumnVisibility("<table-id>", columns)` and give `<ColumnToggle state={…} />` to `actions`; the user's choice is remembered per table.
  - Put `<Pagination>` in the table's `footer`, and pass `loading` only for the first load.
  - Reference implementations: `features/users/users-page.tsx` and `features/audit/audit-log-page.tsx`.
- **Selects:** `<Select>` from `@/components/ui` is a styled listbox (keyboard and ARIA complete) used exactly like a native select: `<option>` children, `value` + `onChange(e => e.target.value)`, or `defaultValue` + `name` inside forms. Never use a raw `<select>`, whose native option list can't be styled.
- **Menus:** `<DropdownMenu label="…" trigger={<Icon />} className="…">` with `<DropdownItem>`. Use `checked` for toggles, `keepOpen` to stay open after a click, and `<DropdownLabel>` for headings. The trigger is already a button, so don't nest one.
- Props are typed inline or with a local `type Props`. Prefer composition (children, render props such as `Dialog`'s `(close) => …`) over boolean-flag explosions.

## 3. Overlays and motion

- Dialogs, sheets/drawers, menus, select lists, the command palette and toasts animate both in **and out**. They stay mounted while closing (`usePresence`) and play CSS animations keyed on `data-state` (`.anim-*` in `styles/globals.css`). Reduced-motion users get instant transitions.
- Open dialogs with the `open` / `onOpenChange` props rather than `{open && <Dialog …>}`: conditional rendering unmounts the dialog instantly and skips the exit animation. When the dialog shows a selected record, keep the content while it closes:
  ```tsx
  const shown = useLatest(editing);               // last non-null value
  {shown && <EditDialog key={shown.id} user={shown} open={editing !== null} onClose={() => setEditing(null)} />}
  ```
- New animated components should follow the same pattern: `usePresence(open, exitMs)` plus an `anim-*` class with an enter and an exit keyframe of matching length.
- Popovers (menus, select lists) render in a portal positioned with `useAnchoredPosition`, so tables and dialogs never clip them.

## 4. Data loading and state

- Load data with `useResource(() => api.get<T>(...), [deps])`. It gives you `data`, `error`, `loading` and `reload`, and it ignores stale responses.
- Always render all three states: a **skeleton** while loading, `<ErrorState onRetry={reload}>` on error, and `<EmptyState>` when the list is empty.
- **Loading is shown with skeletons shaped like the content, never spinners.** Use `<DataTable loading>` for the first load of a table (it draws one placeholder per column), `<PageSkeleton variant="table|dashboard|form">` for a page waiting on its data, and `<CardSkeleton>`, `<TableSkeleton>`, `<SkeletonText>` or `<Skeleton className="h-4 w-24">` for smaller parts. `AppShellSkeleton` covers app start-up. Spinners are only for actions in progress: `<Button loading>`.
- Skeletons only cover the first load. On refresh, keep showing the old data (`loading && !data`) so the screen doesn't flash. Prefetch small related data, such as every role's permissions, so switching views doesn't show a loader.
- Mutations: `await api.post/patch/put/delete(...)`, then `toast.success(...)` and `reload()`. On error, show `toast.error(title, err.message)` or an `<Alert>`.
- Dropdowns with another page's data use `useLookup("<entity>")`, never that page's endpoint.
- State: local `useState` first. Lift it to the page when siblings need it. Use URL search params (`useSearchParams`) for filters and pagination that should survive a reload or be shareable. No global store until there's a proven need.
- Debounce search inputs with `useDebounced`.
- Put API types in the feature's `types.ts` (or `lib/types.ts` if shared), mirroring the backend schemas, and update both sides in the same change.

## 5. Forms

- Use `<form onSubmit>` with `FormData` for simple forms, or controlled state when fields depend on each other.
- Labels go through `<Field label hint error>`; never a bare `<input>`.
- Set HTML constraints that match the backend (`required`, `minLength`, `maxLength`, `type="email"`), plus `autoComplete` (`username`, `current-password`, `new-password`, `one-time-code`).
- Show pending state with `<Button loading>`. Show server errors in `<Alert tone="danger">` above the form, and keep what the user typed.
- Client validation is for UX only; the server is the authority.

## 6. Permissions in the UI

- Gate routes with `<RequireScreen screen="key">` in `src/app/App.tsx`, and nav entries with `screen: "key"` in `src/app/navigation.ts`.
- Hide or disable write actions with `useAuth().can("key", "write")`, and feature sections with `can("page.feature")`.
- The UI only mirrors the backend: every action must still be enforced by `require_screen` on the server.

## 7. Styling and theming

- Use Tailwind utility classes with the existing palette: page `bg-[#171717]`, cards `bg-[#1b1b1b]`, borders `border-white/[0.08–0.11]`, text `text-[#ededed]` / `#888` / `#777`, the emerald accent, and `text-xs`/`text-[11px]` for UI chrome.
- **Light mode works by remapping those exact classes in `styles/globals.css`.** Reuse them; a new hex value won't adapt to light mode. If you need a new colour, add its light-mode mapping in `globals.css` too.
- Don't write inline styles except for dynamic values (React's `style={{}}` is allowed by the CSP; HTML `style="…"` attributes are not).
- No CSS-in-JS and no external fonts or CDNs.
- Layouts must work at a phone width of 390px: use `sm:`/`lg:` breakpoints, wrap wide tables in the existing `Table` (which scrolls horizontally), and use `min-w-0` / `truncate` for long text.

## 8. Accessibility

- Use semantic elements (`button` for actions, `a`/`Link` for navigation, `table` for tabular data).
- Every input has a label. Icon-only buttons have an `aria-label`. Decorative icons get `aria-hidden`.
- Everything works with the keyboard: dialogs trap focus and close on Escape (built into `Dialog`/`Sheet`), and focus is visible.
- Status changes are announced: toasts are live regions, and errors use `role="alert"` (`Alert` does this).
- Don't rely on colour alone (badges carry text), and keep the existing contrast in both themes.

## 9. Security in the browser

- Never use `dangerouslySetInnerHTML`, `eval`, `new Function` or string `setTimeout`.
- No secrets in code or `VITE_*` variables. Tokens live in HttpOnly cookies, never in `localStorage`/`sessionStorage` (local storage is only for UI preferences like theme and sidebar state).
- Strip sensitive values from the URL right after reading them, as the reset page does with its token. Validate any redirect target against internal paths.
- The CSP allows only same-origin scripts and styles, plus Cloudflare Turnstile when enabled. Anything new from another origin needs a deliberate CSP change (see `fastapi-security`).

## 10. Performance

- Build with `npm run build` (typecheck + Vite). `main.py --dev` rebuilds on save.
- Lazy-load heavy, rarely used routes with `React.lazy` + `<Suspense fallback={<LoadingState />}>`, and keep large libraries out of the main bundle.
- Paginate lists on the server; don't fetch everything and filter in the browser.
- Memoise only when profiling shows a need (`useMemo`/`useCallback` for expensive work or stable dependencies).

## 11. Checklist

- [ ] Code lives in the right feature folder; imports respect the boundaries; only `@/` paths.
- [ ] Only design-system components; new building blocks added to `components/ui` and the gallery.
- [ ] Skeleton (not spinner) loading, error and empty states all handled; list pages use `DataTablePage` + `DataTable` with a Columns menu.
- [ ] Dialogs are controlled with `open` (not mounted conditionally), so they animate out; no raw `<select>`.
- [ ] Forms labelled with matching constraints and `autoComplete`; errors shown and input kept.
- [ ] Routes, nav and actions gated with `RequireScreen` / `can()`, and the server enforces the same.
- [ ] Works in dark and light mode and at 390px width; keyboard-accessible.
- [ ] Types updated with the backend; `npm run build` passes with no errors.
