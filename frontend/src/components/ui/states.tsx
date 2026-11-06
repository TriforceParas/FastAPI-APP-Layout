import { Link } from "react-router";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileQuestion,
  LoaderCircle,
  ShieldX,
  WifiOff,
} from "lucide-react";

import { Button, Card, cn, Skeleton } from "@/components/ui/primitives";

/**
 * Spinner + text. Prefer the skeletons below for content that is loading; use
 * this only where the shape of the content is unknown.
 */
export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-48 items-center justify-center gap-2 text-sm text-[#888]"
    >
      <LoaderCircle className="animate-spin" size={18} />
      <span>{label}</span>
    </div>
  );
}

/* --- Skeletons ---------------------------------------------------------------
   Shaped like the content they stand in for, so the page doesn't jump when the
   data arrives. Each wrapper announces "Loading" to screen readers once. */

function Loading({ label = "Loading", className, children }: { label?: string; className?: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className={className}>
      <span className="sr-only">{label}…</span>
      {children}
    </div>
  );
}

/** A few lines of text; the last one is shorter. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div aria-hidden className={cn("space-y-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

/** Stands in for <PageHeader>: eyebrow, title, description. */
export function PageHeaderSkeleton({ actions = 0 }: { actions?: number }) {
  return (
    <div aria-hidden className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="space-y-2.5">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      {actions > 0 && (
        <div className="flex gap-2">
          {Array.from({ length: actions }, (_, i) => (
            <Skeleton key={i} className="h-8 w-24" />
          ))}
        </div>
      )}
    </div>
  );
}

/** A card with a title row and some text. */
export function CardSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <Card aria-hidden className={className}>
      <div className="space-y-2 border-b border-white/[0.08] p-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-64 max-w-full" />
      </div>
      <SkeletonText lines={lines} className="p-4" />
    </Card>
  );
}

/** A table: header cells plus rows. */
export function TableSkeleton({ rows = 6, columns = 4, className }: { rows?: number; columns?: number; className?: string }) {
  const widths = ["w-40", "w-24", "w-20", "w-28", "w-16", "w-24"];
  return (
    <Card aria-hidden className={cn("overflow-hidden", className)}>
      <div className="flex gap-6 border-b border-white/[0.08] px-4 py-3">
        {Array.from({ length: columns }, (_, c) => (
          <Skeleton key={c} className={cn("h-2.5", c === 0 ? "w-32 flex-1" : "w-16")} />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex items-center gap-6 border-b border-white/[0.06] px-4 py-3.5 last:border-b-0">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className={cn("h-4", c === 0 ? "flex-1" : widths[(c + r) % widths.length])} />
          ))}
        </div>
      ))}
    </Card>
  );
}

/** Whole-page placeholder for a page that is still loading its data. */
export function PageSkeleton({ variant = "table", label }: { variant?: "table" | "dashboard" | "form"; label?: string }) {
  return (
    <Loading label={label}>
      <PageHeaderSkeleton actions={variant === "form" ? 0 : 1} />
      {variant === "dashboard" && (
        <div className="space-y-5">
          <div className="grid gap-px overflow-hidden rounded-lg border border-white/[0.09] sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="space-y-3 bg-[#1b1b1b] p-4">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))}
          </div>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.65fr)]">
            <CardSkeleton lines={6} />
            <CardSkeleton lines={3} />
          </div>
        </div>
      )}
      {variant === "table" && (
        <>
          <div aria-hidden className="mb-4 flex flex-wrap gap-2">
            <Skeleton className="h-9 w-64" />
            <Skeleton className="h-9 w-36" />
            <Skeleton className="h-9 w-36" />
          </div>
          <TableSkeleton rows={8} columns={5} />
        </>
      )}
      {variant === "form" && <CardSkeleton lines={5} className="max-w-2xl" />}
    </Loading>
  );
}

/** Placeholder for the whole app (sidebar, top bar, page) while the session loads. */
export function AppShellSkeleton() {
  return (
    <Loading label="Loading workspace" className="flex h-dvh overflow-hidden bg-[#171717]">
      <div aria-hidden className="hidden w-52 shrink-0 flex-col border-r border-white/[0.08] bg-[#111111] lg:flex">
        <div className="flex h-14 items-center gap-2.5 border-b border-white/[0.08] px-3">
          <Skeleton className="size-7" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-2.5 w-16" />
          </div>
        </div>
        <div className="space-y-2 p-2 pt-3">
          <Skeleton className="h-9 w-full" />
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-full opacity-70" />
          ))}
        </div>
        <div className="mt-auto border-t border-white/[0.08] p-2">
          <Skeleton className="h-9 w-full" />
        </div>
      </div>
      <div aria-hidden className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.08] px-4 md:px-6">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="ml-auto size-8" />
        </div>
        <div className="mx-auto w-full max-w-[1500px] p-4 md:p-6 lg:p-8">
          <PageHeaderSkeleton actions={1} />
          <div className="grid gap-px overflow-hidden rounded-lg border border-white/[0.09] sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="space-y-3 bg-[#1b1b1b] p-4">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-7 w-16" />
              </div>
            ))}
          </div>
          <CardSkeleton lines={5} className="mt-5" />
        </div>
      </div>
    </Loading>
  );
}

export function RouteEmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex min-h-56 flex-col items-center justify-center border-dashed p-8 text-center">
      <FileQuestion size={22} className="text-[#666]" />
      <h2 className="mt-3 text-sm font-medium">{title}</h2>
      <p className="mt-1 max-w-md text-xs leading-5 text-[#777]">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <Card role="alert" className={cn("p-6", className)}>
      <AlertTriangle size={20} className="text-amber-300" />
      <h2 className="mt-3 text-sm font-medium">{title}</h2>
      <p className="mt-1 text-xs leading-5 text-[#888]">{description}</p>
      {onRetry && (
        <Button className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  );
}

export function ForbiddenState() {
  return (
    <Card className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
      <ShieldX size={24} className="text-rose-300" />
      <h1 className="mt-3 text-base font-medium">Access denied</h1>
      <p className="mt-1 max-w-md text-xs leading-5 text-[#888]">
        Your account does not have permission to view this resource.
      </p>
      <Link
        to="/"
        className="mt-4 inline-flex h-8 items-center rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-medium text-[#dedede] hover:bg-white/[0.075]"
      >
        Return to your workspace
      </Link>
    </Card>
  );
}

export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  return (
    <Card className="flex min-h-56 flex-col items-center justify-center p-8 text-center">
      <WifiOff size={22} className="text-amber-300" />
      <h2 className="mt-3 text-sm font-medium">You are offline</h2>
      <p className="mt-1 max-w-md text-xs leading-5 text-[#777]">
        Reconnect to continue. Valid draft data should remain on this device.
      </p>
      {onRetry && (
        <Button className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  );
}

export function SuccessState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Card className="flex min-h-56 flex-col items-center justify-center p-8 text-center">
      <CheckCircle2 size={22} className="text-emerald-400" />
      <h2 className="mt-3 text-sm font-medium">{title}</h2>
      <p className="mt-1 max-w-md text-xs leading-5 text-[#777]">
        {description}
      </p>
    </Card>
  );
}
