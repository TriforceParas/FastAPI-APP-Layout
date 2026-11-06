import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  ReactNode,
  TdHTMLAttributes,
  TextareaHTMLAttributes,
  ThHTMLAttributes,
} from "react";
import { cloneElement, isValidElement, useEffect, useId, useRef } from "react";
import { Link } from "react-router";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Info,
  LoaderCircle,
  XCircle,
} from "lucide-react";

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
  /** Shows a spinner and disables the button. */
  loading?: boolean;
};

/** Class string for styling a router <Link> or <a> exactly like a Button. */
export function buttonClass({
  variant = "secondary",
  size = "md",
  className,
}: Pick<ButtonProps, "variant" | "size" | "className"> = {}) {
  return cn(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-md border font-medium transition disabled:pointer-events-none disabled:opacity-45",
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  );
}

const BUTTON_VARIANTS = {
  primary:
    "border-emerald-300 bg-emerald-400 text-[#06291c] hover:bg-emerald-300",
  secondary:
    "border-white/[0.1] bg-white/[0.04] text-[#dedede] hover:bg-white/[0.075]",
  ghost:
    "border-transparent bg-transparent text-[#aaa] hover:bg-white/[0.05] hover:text-white",
  danger:
    "border-rose-400/20 bg-rose-400/10 text-rose-300 hover:bg-rose-400/15",
};

const BUTTON_SIZES = {
  sm: "h-7 px-2.5 text-[11px]",
  md: "h-8 px-3 text-xs",
  lg: "h-9 px-4 text-sm",
  icon: "size-8 p-0",
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  type = "button",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClass({ variant, size, className })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <LoaderCircle size={13} className="animate-spin" />}
      {children}
    </button>
  );
}

export function IconButton({ children, ...props }: ButtonProps) {
  return (
    <Button size="icon" aria-label={props["aria-label"] ?? "Action"} {...props}>
      {children}
    </Button>
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "min-w-0 rounded-lg border border-white/[0.09] bg-[#1b1b1b]",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("border-b border-white/[0.08] p-4", className)}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-sm font-medium text-[#ededed]", className)}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("mt-1 text-xs leading-relaxed text-[#8f8f8f]", className)}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}

export function CardFooter({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center border-t border-white/[0.08] p-4",
        className,
      )}
      {...props}
    />
  );
}

export function Label({
  className,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "mb-1.5 block text-xs font-medium text-[#b8b8b8]",
        className,
      )}
      {...props}
    />
  );
}

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-md border border-white/[0.11] bg-[#151515] px-3 text-sm text-[#e8e8e8] placeholder:text-[#5f5f5f] hover:border-white/[0.16] focus:border-emerald-400/70 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-24 w-full resize-y rounded-md border border-white/[0.11] bg-[#151515] px-3 py-2 text-sm text-[#e8e8e8] placeholder:text-[#5f5f5f] focus:border-emerald-400/70",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  const generatedId = useId();
  // Only form controls (elements with a `name` or `id`) receive an id; plain
  // wrappers such as <div> are left alone so the label never targets them.
  const control =
    isValidElement<{ id?: string; name?: string }>(children) &&
    (children.props.name !== undefined || children.props.id !== undefined)
      ? children
      : null;
  const controlId = htmlFor ?? control?.props.id ?? (control ? generatedId : undefined);

  return (
    <div className={className}>
      <Label htmlFor={controlId}>{label}</Label>
      {control && controlId && !control.props.id
        ? cloneElement(control, { id: controlId })
        : children}
      {(hint !== undefined || error !== undefined) && (
        <p
          className={cn(
            "mt-1.5 text-[11px]",
            error ? "text-rose-400" : "text-[#8f8f8f]",
          )}
        >
          {error ?? hint}
        </p>
      )}
    </div>
  );
}

export function ErrorSummary({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null;
  return (
    <div
      role="alert"
      tabIndex={-1}
      className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3"
    >
      <p className="text-xs font-medium text-rose-300">
        Check the following fields
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-rose-200/80">
        {errors.map((error) => (
          <li key={error}>{error}</li>
        ))}
      </ul>
    </div>
  );
}

export function CurrencyInput({
  symbol = "₹",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { symbol?: string }) {
  return (
    <div className="relative">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-2.5 left-3 text-sm text-[#777]"
      >
        {symbol}
      </span>
      <Input
        inputMode="decimal"
        pattern="[0-9]+(?:\.[0-9]{1,2})?"
        min="0"
        step="0.01"
        {...props}
        className={cn("pl-8 tabular-nums", props.className)}
      />
    </div>
  );
}

export function Checkbox({
  label,
  className,
  indeterminate = false,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  /** Shows the "some selected" state (for select-all headers). */
  indeterminate?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);

  const input = (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "size-3.5 rounded border-white/20 bg-[#151515] accent-emerald-400",
        className,
      )}
      {...props}
    />
  );

  if (!label) return input;

  return (
    <label className="inline-flex items-center gap-2 text-xs text-[#aaa]">
      {input}
      {label}
    </label>
  );
}

export function Switch({
  label,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 text-xs text-[#aaa]",
        className,
      )}
    >
      <span className="relative h-5 w-9 rounded-full bg-[#343434] has-checked:bg-emerald-400">
        <input type="checkbox" className="peer sr-only" {...props} />
        <span className="absolute top-0.5 left-0.5 size-4 rounded-full bg-white transition-transform peer-checked:translate-x-4" />
      </span>
      {label}
    </label>
  );
}

export function RadioGroup({
  name,
  options,
  defaultValue,
}: {
  name: string;
  options: Array<{ label: string; value: string; description?: string }>;
  defaultValue?: string;
}) {
  return (
    <div className="grid gap-2">
      {options.map((option) => (
        <label
          key={option.value}
          className="flex cursor-pointer gap-3 rounded-md border border-white/[0.09] p-3 hover:bg-white/[0.025]"
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            defaultChecked={option.value === defaultValue}
            className="mt-0.5 accent-emerald-400"
          />
          <span>
            <span className="block text-xs font-medium text-[#ddd]">
              {option.label}
            </span>
            {option.description && (
              <span className="mt-0.5 block text-[11px] text-[#777]">
                {option.description}
              </span>
            )}
          </span>
        </label>
      ))}
    </div>
  );
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  const tones = {
    neutral: "border-white/[0.09] bg-white/[0.04] text-[#aaa]",
    success: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
    warning: "border-amber-400/20 bg-amber-400/10 text-amber-300",
    danger: "border-rose-400/20 bg-rose-400/10 text-rose-300",
    info: "border-sky-400/20 bg-sky-400/10 text-sky-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Alert({
  title,
  children,
  tone = "info",
  className,
}: {
  title: string;
  children?: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
  className?: string;
}) {
  const icon = {
    info: Info,
    success: CheckCircle2,
    warning: AlertCircle,
    danger: XCircle,
  }[tone];
  const colors = {
    info: "border-sky-400/20 bg-sky-400/[0.06] text-sky-300",
    success: "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300",
    warning: "border-amber-400/20 bg-amber-400/[0.06] text-amber-300",
    danger: "border-rose-400/20 bg-rose-400/[0.06] text-rose-300",
  }[tone];
  const Icon = icon;
  return (
    <div
      role="alert"
      className={cn("flex gap-3 rounded-md border p-3", colors, className)}
    >
      <Icon size={15} className="mt-0.5 shrink-0" />
      <div>
        <p className="text-xs font-medium">{title}</p>
        {children && (
          <div className="mt-1 text-[11px] leading-relaxed text-[#999]">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

export function Avatar({
  name,
  image,
  size = "md",
}: {
  name: string;
  image?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  const sizes = {
    sm: "size-6 text-[9px]",
    md: "size-8 text-[10px]",
    lg: "size-10 text-xs",
  };
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(
        "inline-flex items-center justify-center rounded-full bg-[#303030] bg-cover bg-center font-semibold text-[#d8d8d8]",
        sizes[size],
      )}
      style={image ? { backgroundImage: `url(${image})` } : undefined}
    >
      {image ? null : initials}
    </span>
  );
}

export function Progress({
  value,
  className,
  indicatorClassName,
}: {
  value: number;
  className?: string;
  indicatorClassName?: string;
}) {
  const safeValue = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={safeValue}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "h-1.5 overflow-hidden rounded-full bg-white/[0.07]",
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full bg-emerald-400 transition-[width]",
          indicatorClassName,
        )}
        style={{ width: `${safeValue}%` }}
      />
    </div>
  );
}

/** Placeholder block with a shimmer (works in dark and light mode). Size it with className. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton", !className?.includes("rounded") && "rounded-md", className)} />;
}

export function Separator({ className }: { className?: string }) {
  return (
    <div
      role="separator"
      className={cn("h-px w-full bg-white/[0.08]", className)}
    />
  );
}

export function Table({
  className,
  ...props
}: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-left text-xs", className)} {...props} />
    </div>
  );
}
export function TableHeader({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn(
        "bg-white/[0.018] text-[10px] tracking-wider text-[#696969] uppercase",
        className,
      )}
      {...props}
    />
  );
}
export function TableBody({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      className={cn("divide-y divide-white/[0.06]", className)}
      {...props}
    />
  );
}
export function TableRow({
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("transition hover:bg-white/[0.025]", className)}
      {...props}
    />
  );
}
export function TableHead({
  className,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("px-4 py-2.5 font-medium", className)} {...props} />;
}
export function TableCell({
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-3 text-[#aaa]", className)} {...props} />;
}

export function Accordion({
  items,
  className,
}: {
  items: Array<{ title: string; content: ReactNode }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "divide-y divide-white/[0.08] rounded-md border border-white/[0.09]",
        className,
      )}
    >
      {items.map((item) => (
        <details key={item.title} className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between p-3 text-xs font-medium text-[#ccc]">
            {item.title}
            <ChevronDown
              size={13}
              className="transition-transform group-open:rotate-180"
            />
          </summary>
          <div className="px-3 pb-3 text-xs leading-relaxed text-[#888]">
            {item.content}
          </div>
        </details>
      ))}
    </div>
  );
}

export function Breadcrumb({
  items,
}: {
  items: Array<{ label: string; href?: string }>;
}) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-2 text-xs text-[#777]">
        {items.map((item, index) => (
          <li key={item.label} className="flex items-center gap-2">
            {index > 0 && <span className="text-[#444]">/</span>}
            {item.href ? (
              <Link to={item.href} className="hover:text-[#ddd]">
                {item.label}
              </Link>
            ) : (
              <span className="text-[#bbb]">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <span title={label} className="inline-flex">
      {children}
    </span>
  );
}
export function ScrollArea({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("overflow-auto", className)} {...props} />;
}
export function AspectRatio({
  ratio = 16 / 9,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { ratio?: number }) {
  return (
    <div
      className={cn("relative overflow-hidden", className)}
      style={{ aspectRatio: ratio }}
      {...props}
    />
  );
}
export function Slider(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input type="range" className="w-full accent-emerald-400" {...props} />
  );
}
export function Toggle({
  pressed,
  className,
  ...props
}: ButtonProps & { pressed?: boolean }) {
  return (
    <Button
      variant="ghost"
      aria-pressed={pressed}
      className={cn(pressed && "bg-white/[0.08] text-white", className)}
      {...props}
    />
  );
}
export function ToggleGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded-md border border-white/[0.09] p-0.5",
        className,
      )}
    >
      {children}
    </div>
  );
}
export function Collapsible({
  title,
  children,
}: {
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <details>
      <summary className="cursor-pointer list-none">{title}</summary>
      <div>{children}</div>
    </details>
  );
}
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-white/[0.1] bg-white/[0.035] px-1.5 py-0.5 font-sans text-[10px] text-[#777]">
      {children}
    </kbd>
  );
}
export function LoadingLine() {
  return (
    <div className="fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-emerald-400/20">
      <div className="h-full w-1/3 animate-pulse bg-emerald-400" />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-white/[0.11] p-8 text-center">
      <div className="mb-3 text-[#626262]">{icon}</div>
      <h3 className="text-sm font-medium text-[#ddd]">{title}</h3>
      <p className="mt-1 max-w-sm text-xs leading-relaxed text-[#777]">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
