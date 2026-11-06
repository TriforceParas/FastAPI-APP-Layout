import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, Info, Search, X, XCircle, AlertCircle } from "lucide-react";

import { usePresence } from "@/components/ui/presence";
import { Button, cn, Input } from "@/components/ui/primitives";

/* -------------------------------------------------------------------------- */
/* Focus trap shared by Dialog / Sheet                                         */
/* -------------------------------------------------------------------------- */

function useModalFocus(isOpen: boolean, close: () => void) {
  const containerRef = useRef<HTMLElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;

  useEffect(() => {
    if (!isOpen) return;
    const restoreFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const container = containerRef.current;
    const focusable = () =>
      Array.from(
        container?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
    const autoFocus = container?.querySelector<HTMLElement>("[autofocus], [data-autofocus]");
    (autoFocus ?? focusable()[0] ?? container)?.focus();

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) {
        event.preventDefault();
        container?.focus();
        return;
      }
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      restoreFocus?.focus();
    };
  }, [isOpen]);
  return containerRef;
}

/** Controlled-or-uncontrolled open state. */
function useOpenState(open?: boolean, onOpenChange?: (open: boolean) => void) {
  const [internal, setInternal] = useState(false);
  const isControlled = open !== undefined;
  const isOpen = isControlled ? open : internal;
  const setOpen = useCallback(
    (next: boolean) => {
      if (!isControlled) setInternal(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );
  return [isOpen, setOpen] as const;
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                        */
/* -------------------------------------------------------------------------- */

export function Tabs({
  items,
  defaultValue,
  value,
  onValueChange,
}: {
  items: Array<{ value: string; label: string; content: ReactNode }>;
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}) {
  const [internal, setInternal] = useState(defaultValue ?? items[0]?.value);
  const active = value ?? internal;
  const select = (next: string) => {
    setInternal(next);
    onValueChange?.(next);
  };
  return (
    <div>
      <div role="tablist" className="flex gap-1 border-b border-white/[0.08]">
        {items.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active === item.value}
            onClick={() => select(item.value)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-xs transition-colors",
              active === item.value
                ? "border-emerald-400 font-medium text-[#ededed]"
                : "border-transparent text-[#777] hover:text-[#bbb]",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      {items.map(
        (item) =>
          active === item.value && (
            <div key={item.value} role="tabpanel" className="py-4">
              {item.content}
            </div>
          ),
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Dialog                                                                      */
/* -------------------------------------------------------------------------- */

export type DialogProps = {
  /** Element that opens the dialog (uncontrolled mode). Optional when `open` is used. */
  trigger?: ReactNode;
  title: string;
  description?: string;
  /** Content, or a render function receiving `close`. */
  children: ReactNode | ((close: () => void) => ReactNode);
  /** Controlled mode. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  size?: "sm" | "md" | "lg";
  /** Rendered in a bordered footer row. */
  footer?: ReactNode | ((close: () => void) => ReactNode);
};

export function Dialog({
  trigger,
  title,
  description,
  children,
  open,
  onOpenChange,
  size = "md",
  footer,
}: DialogProps) {
  const [isOpen, setOpen] = useOpenState(open, onOpenChange);
  const close = useCallback(() => setOpen(false), [setOpen]);
  const dialogRef = useModalFocus(isOpen, close);
  const { mounted, state } = usePresence(isOpen, 160);
  const widths = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" };

  return (
    <>
      {trigger && (
        <span className="contents" onClick={() => setOpen(true)}>
          {trigger}
        </span>
      )}
      {mounted && (
        <div
          role="presentation"
          data-state={state}
          className={cn(
            "anim-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm",
            state === "closed" && "pointer-events-none",
          )}
          onMouseDown={close}
        >
          <section
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            onMouseDown={(event) => event.stopPropagation()}
            data-state={state}
            className={cn(
              "anim-dialog flex max-h-[90vh] w-full flex-col rounded-lg border border-white/[0.11] bg-[#202020] shadow-2xl",
              widths[size],
            )}
          >
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-white/[0.08] p-4">
              <div>
                <h2 className="text-sm font-medium text-[#ededed]">{title}</h2>
                {description && <p className="mt-1 text-xs text-[#777]">{description}</p>}
              </div>
              <Button size="icon" variant="ghost" aria-label="Close dialog" onClick={close}>
                <X size={15} />
              </Button>
            </div>
            <div className="min-h-0 overflow-y-auto p-4">
              {typeof children === "function" ? children(close) : children}
            </div>
            {footer && (
              <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.08] p-4">
                {typeof footer === "function" ? footer(close) : footer}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Sheet / Drawer                                                              */
/* -------------------------------------------------------------------------- */

export function Sheet({
  trigger,
  title,
  children,
  side = "right",
  open,
  onOpenChange,
}: {
  trigger?: ReactNode;
  title: string;
  children: ReactNode | ((close: () => void) => ReactNode);
  side?: "left" | "right";
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [isOpen, setOpen] = useOpenState(open, onOpenChange);
  const close = useCallback(() => setOpen(false), [setOpen]);
  const sheetRef = useModalFocus(isOpen, close);
  const { mounted, state } = usePresence(isOpen, 240);
  return (
    <>
      {trigger && (
        <span className="contents" onClick={() => setOpen(true)}>
          {trigger}
        </span>
      )}
      {mounted && (
        <div
          data-state={state}
          className={cn(
            "anim-overlay fixed inset-0 z-50 bg-black/60 backdrop-blur-sm",
            state === "closed" && "pointer-events-none",
          )}
          onMouseDown={close}
        >
          <aside
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            onMouseDown={(event) => event.stopPropagation()}
            data-state={state}
            className={cn(
              "absolute inset-y-0 flex w-full max-w-md flex-col border-white/[0.1] bg-[#1c1c1c] shadow-2xl",
              side === "right" ? "anim-sheet-right right-0 border-l" : "anim-sheet-left left-0 border-r",
            )}
          >
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.08] px-4">
              <h2 className="text-sm font-medium">{title}</h2>
              <Button size="icon" variant="ghost" aria-label="Close panel" onClick={close}>
                <X size={15} />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {typeof children === "function" ? children(close) : children}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

export function Drawer(props: Omit<Parameters<typeof Sheet>[0], "side">) {
  return <Sheet {...props} side="right" />;
}

/* -------------------------------------------------------------------------- */
/* AlertDialog (confirmation)                                                  */
/* -------------------------------------------------------------------------- */

export function AlertDialog({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "danger",
  onConfirm,
  open,
  onOpenChange,
}: {
  trigger?: ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  /** May be async; the dialog shows a spinner and closes when it resolves. */
  onConfirm?: () => void | Promise<void>;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog
      trigger={trigger}
      title={title}
      description={description}
      open={open}
      onOpenChange={onOpenChange}
      size="sm"
    >
      {(close) => (
        <div className="flex justify-end gap-2">
          <Button onClick={close} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone}
            loading={busy}
            data-autofocus
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm?.();
                close();
              } finally {
                setBusy(false);
              }
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      )}
    </Dialog>
  );
}

/* -------------------------------------------------------------------------- */
/* CommandMenu (⌘K palette body)                                               */
/* -------------------------------------------------------------------------- */

export type Command = {
  label: string;
  section: string;
  icon?: ReactNode;
  keywords?: string;
  onSelect?: () => void;
};

export function CommandMenu({
  commands,
  onDone,
}: {
  commands: Command[];
  onDone?: () => void;
}) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return commands.filter((c) =>
      `${c.label} ${c.section} ${c.keywords ?? ""}`.toLowerCase().includes(q),
    );
  }, [commands, query]);

  const run = (command?: Command) => {
    if (!command) return;
    command.onSelect?.();
    onDone?.();
  };

  return (
    <div className="overflow-hidden rounded-lg border border-white/[0.1] bg-[#1d1d1d] shadow-2xl">
      <div className="flex items-center gap-2 border-b border-white/[0.08] px-3">
        <Search size={14} className="text-[#666]" />
        <Input
          autoFocus
          value={query}
          aria-label="Search commands"
          onChange={(event) => {
            setQuery(event.target.value);
            setCursor(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setCursor((c) => Math.min(c + 1, visible.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setCursor((c) => Math.max(c - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              run(visible[cursor]);
            }
          }}
          placeholder="Type a command or search…"
          data-bare=""
          className="border-0 bg-transparent px-0 hover:border-0 focus:border-0"
        />
      </div>
      <div className="max-h-72 overflow-auto p-1" role="listbox">
        {visible.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-[#666]">No results</p>
        )}
        {visible.map((command, index) => (
          <button
            key={`${command.section}-${command.label}`}
            type="button"
            role="option"
            aria-selected={index === cursor}
            onMouseEnter={() => setCursor(index)}
            onClick={() => run(command)}
            className={cn(
              "flex h-9 w-full items-center gap-2 rounded px-2 text-left text-xs text-[#bbb]",
              index === cursor && "bg-white/[0.06] text-white",
            )}
          >
            {command.icon && <span className="text-[#777]">{command.icon}</span>}
            <span>{command.label}</span>
            <span className="ml-auto text-[10px] text-[#5f5f5f]">{command.section}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Full-screen ⌘K palette. */
export function CommandPalette({
  open,
  onOpenChange,
  commands,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  commands: Command[];
}) {
  const close = useCallback(() => onOpenChange(false), [onOpenChange]);
  const ref = useModalFocus(open, close);
  const { mounted, state } = usePresence(open, 160);
  if (!mounted) return null;
  return (
    <div
      role="presentation"
      data-state={state}
      className={cn(
        "anim-overlay fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[14vh] backdrop-blur-sm",
        state === "closed" && "pointer-events-none",
      )}
      onMouseDown={close}
    >
      <section
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        tabIndex={-1}
        data-state={state}
        className="anim-dialog w-full max-w-lg"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <CommandMenu commands={commands} onDone={close} />
      </section>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Toasts                                                                      */
/* -------------------------------------------------------------------------- */

type ToastTone = "success" | "danger" | "info" | "warning";
type ToastItem = { id: number; title: string; description?: string; tone: ToastTone; leaving?: boolean };
const TOAST_EXIT_MS = 220;
type ToastApi = {
  toast: (toast: { title: string; description?: string; tone?: ToastTone }) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  // Play the exit animation first, then remove the toast.
  const dismiss = useCallback((id: number) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, leaving: true } : item)));
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), TOAST_EXIT_MS);
  }, []);

  const api = useMemo<ToastApi>(() => {
    const toast: ToastApi["toast"] = ({ title, description, tone = "info" }) => {
      const id = nextId.current++;
      setItems((current) => [...current.filter((item) => !item.leaving).slice(-3), { id, title, description, tone }]);
      window.setTimeout(() => dismiss(id), tone === "danger" ? 7000 : 4000);
    };
    return {
      toast,
      success: (title, description) => toast({ title, description, tone: "success" }),
      error: (title, description) => toast({ title, description, tone: "danger" }),
    };
  }, [dismiss]);

  const icons = { success: CheckCircle2, danger: XCircle, info: Info, warning: AlertCircle };
  const colors = {
    success: "text-emerald-400",
    danger: "text-rose-400",
    info: "text-sky-400",
    warning: "text-amber-300",
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2"
      >
        {items.map((item) => {
          const Icon = icons[item.tone];
          return (
            <div
              key={item.id}
              role={item.tone === "danger" ? "alert" : "status"}
              data-state={item.leaving ? "closed" : "open"}
              className={cn(
                "anim-toast pointer-events-auto grid",
                item.leaving && "pointer-events-none",
              )}
            >
              <div className="min-h-0 overflow-hidden">
                <div className="flex gap-3 rounded-lg border border-white/[0.1] bg-[#202020] p-3 shadow-2xl">
              <Icon size={15} className={cn("mt-0.5 shrink-0", colors[item.tone])} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-[#e8e8e8]">{item.title}</p>
                {item.description && (
                  <p className="mt-0.5 text-[11px] leading-relaxed text-[#888]">
                    {item.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                aria-label="Dismiss"
                onClick={() => dismiss(item.id)}
                className="flex size-5 shrink-0 items-center justify-center rounded text-[#666] hover:text-[#ccc]"
              >
                <X size={12} />
              </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
