import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight, Search, type LucideIcon } from "lucide-react";
import { Link } from "react-router";

import { Button, cn, Input } from "@/components/ui/primitives";

const STAT_COLUMNS = {
  1: "sm:grid-cols-1",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-2 xl:grid-cols-3",
  4: "sm:grid-cols-2 xl:grid-cols-4",
} as const;

/** Grid of KPI tiles separated by hairlines (dashboard style). `columns` = number of tiles per row on wide screens. */
export function StatGrid({
  children,
  className,
  columns = 4,
}: {
  children: ReactNode;
  className?: string;
  columns?: 1 | 2 | 3 | 4;
}) {
  return (
    <section
      className={cn(
        "grid gap-px overflow-hidden rounded-lg border border-white/[0.09] bg-white/[0.09]",
        STAT_COLUMNS[columns],
        className,
      )}
    >
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  note,
  icon: Icon,
  href,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  icon?: LucideIcon;
  href?: string;
}) {
  const body = (
    <>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-medium text-[#929292]">{label}</p>
        {Icon && <Icon size={15} className="text-[#626262]" />}
      </div>
      <p className="text-2xl font-medium tracking-tight text-[#f0f0f0] tabular-nums">{value}</p>
      {note && (
        <p className="mt-2 text-[11px] leading-4 text-[#696969] group-hover:text-[#858585]">
          {note}
        </p>
      )}
    </>
  );
  const className = "group block bg-[#1b1b1b] p-4";
  return href ? (
    <Link to={href} className={cn(className, "hover:bg-[#202020]")}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** Search box with a leading icon. */
export function SearchInput({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn("relative", className)}>
      <Search
        size={14}
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[#666]"
      />
      <Input type="search" {...props} className="pl-8" />
    </div>
  );
}

/** Toolbar row above tables: filters on the left, actions on the right. */
export function Toolbar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mb-4 flex flex-wrap items-center justify-between gap-3", className)}>
      {children}
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-white/[0.08] px-4 py-3 text-[11px] text-[#777]">
      <span className="tabular-nums">
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <Button
          size="icon"
          variant="ghost"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft size={14} />
        </Button>
        <span className="px-1 tabular-nums">
          {page} / {pages}
        </span>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}

/** Label/value rows for detail panels. */
export function DescriptionList({
  items,
}: {
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <dl className="divide-y divide-white/[0.06]">
      {items.map((item) => (
        <div key={item.label} className="grid grid-cols-[140px_minmax(0,1fr)] gap-3 py-2.5 text-xs">
          <dt className="text-[#777]">{item.label}</dt>
          <dd className="min-w-0 text-[#ccc]">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
