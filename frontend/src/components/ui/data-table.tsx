import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Columns3, RotateCcw } from "lucide-react";

import { DropdownItem, DropdownLabel, DropdownMenu } from "./menu";
import { Skeleton, cn } from "./primitives";

export type DataTableColumn<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Name in the Columns menu (defaults to `header` when it is a string). */
  label?: string;
  align?: "left" | "right";
  className?: string;
  headerClassName?: string;
  /** false = always shown (e.g. the main column and actions). Default true. */
  hideable?: boolean;
  /** Hidden until the user turns it on. */
  defaultHidden?: boolean;
};

const storageKey = (tableId: string) => `app_table_columns:${tableId}`;

/**
 * Which columns are visible, remembered per table in this browser.
 *
 *   const columnState = useColumnVisibility("users", columns);
 *   <ColumnToggle state={columnState} />                     // in the toolbar
 *   <DataTable columns={columnState.visibleColumns} … />
 */
export function useColumnVisibility<T>(tableId: string, columns: DataTableColumn<T>[]) {
  const hideableIds = useMemo(() => columns.filter((c) => c.hideable !== false).map((c) => c.id), [columns]);
  const defaults = useMemo(() => columns.filter((c) => c.defaultHidden).map((c) => c.id), [columns]);
  const [hidden, setHidden] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey(tableId));
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed.filter((id): id is string => typeof id === "string");
      }
    } catch {
      // storage unavailable or corrupted: fall back to defaults
    }
    return defaults;
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(tableId), JSON.stringify(hidden));
    } catch {
      // ignore (private mode)
    }
  }, [tableId, hidden]);

  const isVisible = (id: string) => !(hideableIds.includes(id) && hidden.includes(id));
  return {
    columns,
    visibleColumns: columns.filter((c) => isVisible(c.id)),
    isVisible,
    toggle: (id: string) =>
      setHidden((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id])),
    reset: () => setHidden(defaults),
    hiddenCount: hidden.filter((id) => hideableIds.includes(id)).length,
  };
}

export type ColumnVisibility<T> = ReturnType<typeof useColumnVisibility<T>>;

/** "Columns" dropdown with a checkbox per hideable column. */
export function ColumnToggle<T>({ state }: { state: ColumnVisibility<T> }) {
  const hideable = state.columns.filter((c) => c.hideable !== false);
  return (
    <DropdownMenu
      align="right"
      label="Show or hide columns"
      className="h-8 gap-2 border border-white/[0.1] bg-white/[0.04] px-3 text-xs font-medium text-[#dedede] transition hover:bg-white/[0.075]"
      trigger={
        <>
          <Columns3 size={13} /> Columns
          {state.hiddenCount > 0 && (
            <span className="rounded-full bg-white/[0.08] px-1.5 text-[10px] text-[#aaa] tabular-nums">
              {state.hiddenCount} hidden
            </span>
          )}
        </>
      }
    >
      <DropdownLabel>Show columns</DropdownLabel>
      {hideable.map((column) => (
        <DropdownItem key={column.id} keepOpen checked={state.isVisible(column.id)} onClick={() => state.toggle(column.id)}>
          {column.label ?? (typeof column.header === "string" ? column.header : column.id)}
        </DropdownItem>
      ))}
      <div className="my-1 h-px bg-white/[0.08]" />
      <DropdownItem keepOpen onClick={state.reset} disabled={state.hiddenCount === 0 && !hideable.some((c) => c.defaultHidden)}>
        <RotateCcw size={12} /> Reset to default
      </DropdownItem>
    </DropdownMenu>
  );
}

/**
 * Table that fills its container's height: rows scroll inside it (both axes),
 * the header row stays visible, and the scrollbars belong to the table.
 * Put it in a <DataTablePage> (or any flex column with a fixed height).
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  skeletonRows = 8,
  empty,
  footer,
  minWidth,
  className,
  label,
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  /** Shows skeleton rows (use for the first load only, so the table doesn't flash on refresh). */
  loading?: boolean;
  skeletonRows?: number;
  /** Rendered inside the table when there are no rows. */
  empty?: ReactNode;
  /** Pinned below the scroll area (e.g. <Pagination />). */
  footer?: ReactNode;
  /** Minimum table width before it scrolls horizontally, e.g. 760. */
  minWidth?: number;
  className?: string;
  /** Accessible name, e.g. "Users". */
  label?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/[0.09] bg-[#1b1b1b]",
        className,
      )}
    >
      <div data-table-scroll="" className="min-h-0 flex-1 overflow-auto">
        <table
          aria-label={label}
          aria-busy={loading || undefined}
          className="w-full border-separate border-spacing-0 text-left text-xs"
          style={minWidth ? { minWidth } : undefined}
        >
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.id}
                  scope="col"
                  className={cn(
                    "sticky top-0 z-10 border-b border-white/[0.08] bg-[#1b1b1b] px-4 py-2.5 text-[10px] font-medium tracking-wider whitespace-nowrap text-[#696969] uppercase",
                    column.align === "right" && "text-right",
                    column.headerClassName,
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              // One placeholder per cell, shaped like the real columns, so nothing jumps when data arrives.
              Array.from({ length: skeletonRows }, (_, r) => (
                <tr key={r} aria-hidden>
                  {columns.map((column, c) => (
                    <td
                      key={column.id}
                      className={cn("border-b border-white/[0.06] px-4 py-3.5", column.align === "right" && "text-right")}
                    >
                      {c === 0 ? (
                        <div className="flex items-center gap-3">
                          <Skeleton className="size-7 shrink-0 rounded-full" />
                          <div className="flex-1 space-y-1.5">
                            <Skeleton className={cn("h-3", r % 2 ? "w-28" : "w-36")} />
                            <Skeleton className="h-2.5 w-24" />
                          </div>
                        </div>
                      ) : column.align === "right" ? (
                        <Skeleton className="ml-auto h-4 w-6" />
                      ) : (
                        <Skeleton className={cn("h-4", ["w-16", "w-20", "w-14", "w-24"][(r + c) % 4])} />
                      )}
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-6">
                  {empty ?? <p className="py-10 text-center text-xs text-[#777]">Nothing to show.</p>}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={rowKey(row)} className="transition-colors hover:bg-white/[0.025]">
                  {columns.map((column) => (
                    <td
                      key={column.id}
                      className={cn(
                        "border-b border-white/[0.06] px-4 py-3 text-[#aaa]",
                        column.align === "right" && "text-right",
                        column.className,
                      )}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {footer}
    </div>
  );
}
