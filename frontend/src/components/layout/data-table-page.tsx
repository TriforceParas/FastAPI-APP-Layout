import { useRef, useState, type ReactNode, type UIEvent } from "react";

import { cn } from "@/components/ui";
import { PageHeader } from "./page-header";

/**
 * Full-height layout for list pages:
 *
 *   ┌ title + description ┐  ← slides away once the rows are scrolled
 *   ├ toolbar │ actions   ┤  ← filters, search, buttons, Columns menu: always visible
 *   ├ column names        ┤  ← sticky
 *   │ rows… (scroll here) │
 *   └ pagination          ┘
 *
 *   <DataTablePage eyebrow title description toolbar={…filters} actions={…buttons}>
 *     <DataTable … />
 *   </DataTablePage>
 *
 * The page itself never scrolls (except on very short screens): rows scroll
 * inside the table, so its header row and the toolbar stay in view.
 */
export function DataTablePage({
  eyebrow,
  title,
  description,
  toolbar,
  actions,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  /** Left side of the sticky bar: search, filters, counts. */
  toolbar?: ReactNode;
  /** Right side of the sticky bar: buttons, Columns menu. */
  actions?: ReactNode;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const headerRef = useRef<HTMLDivElement>(null);

  // Scroll events don't bubble, but they are visible in the capture phase.
  function onScrollCapture(event: UIEvent) {
    const el = event.target;
    if (!(el instanceof HTMLElement) || !el.hasAttribute("data-table-scroll")) return;
    if (!collapsed) {
      const headerHeight = headerRef.current?.offsetHeight ?? 0;
      // Only collapse when there is enough to scroll; otherwise the table would
      // grow, stop overflowing and bounce the header back.
      if (el.scrollTop > 12 && el.scrollHeight - el.clientHeight > headerHeight + 24) setCollapsed(true);
    } else if (el.scrollTop <= 0) {
      setCollapsed(false);
    }
  }

  return (
    <div data-page-layout="table" className="flex min-h-[460px] flex-1 basis-0 flex-col" onScrollCapture={onScrollCapture}>
      <div
        className={cn(
          "grid transition-[grid-template-rows,opacity] duration-300 ease-out",
          collapsed ? "grid-rows-[0fr] opacity-0" : "grid-rows-[1fr] opacity-100",
        )}
        aria-hidden={collapsed || undefined}
      >
        <div className="min-h-0 overflow-hidden">
          <div ref={headerRef}>
            <PageHeader eyebrow={eyebrow} title={title} description={description} />
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{toolbar}</div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>

      {children}
    </div>
  );
}
