import type { ReactNode } from "react";

/** Standard page title block. Use at the top of every page. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        {eyebrow && <p className="mb-1 text-xs font-medium text-emerald-400">{eyebrow}</p>}
        <h1 className="text-2xl font-medium tracking-tight text-[#f4f4f4]">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm leading-6 text-[#858585]">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
