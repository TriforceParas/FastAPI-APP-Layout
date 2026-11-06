import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";

import { useAnchoredPosition, usePresence } from "./presence";
import { cn } from "./primitives";

const MenuContext = createContext<{ close: (focusTrigger?: boolean) => void } | null>(null);

/**
 * Action menu (e.g. a table row's "…" menu).
 *
 *   <DropdownMenu label="Actions for Ada" align="right" trigger={<MoreHorizontal size={15} />}>
 *     <DropdownItem onClick={edit}><Pencil size={13} /> Edit</DropdownItem>
 *   </DropdownMenu>
 *
 * Keyboard: Enter/Space/↓ opens, ↑/↓/Home/End move, Esc closes, Tab leaves.
 * Rendered in a portal so tables and cards with overflow never clip it.
 */
export function DropdownMenu({
  trigger,
  label,
  align = "left",
  className,
  children,
}: {
  /** What the button shows (icon, text). Don't pass a <button>: this already is one. */
  trigger: ReactNode;
  /** Accessible name for icon-only triggers. */
  label?: string;
  align?: "left" | "right";
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const { mounted, state } = usePresence(open, 140);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const position = useAnchoredPosition(triggerRef, open, { align });

  const items = () =>
    Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>(
        '[role="menuitem"]:not([disabled]),[role="menuitemcheckbox"]:not([disabled])',
      ) ?? [],
    );

  const close = useCallback((focusTrigger = true) => {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => items()[0]?.focus());
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target) && !triggerRef.current?.contains(target)) close(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => {
      cancelAnimationFrame(id);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open, close]);

  function onMenuKeyDown(event: KeyboardEvent) {
    const list = items();
    const index = list.indexOf(document.activeElement as HTMLElement);
    const move = (to: number) => {
      event.preventDefault();
      list[(to + list.length) % list.length]?.focus();
    };
    if (event.key === "ArrowDown") move(index + 1);
    else if (event.key === "ArrowUp") move(index - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(list.length - 1);
    else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation(); // don't also close a surrounding dialog
      close(true);
    } else if (event.key === "Tab") close(false);
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className={cn("inline-flex items-center rounded-md", className)}
      >
        {trigger}
      </button>
      {mounted &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            aria-label={label}
            data-state={state}
            data-side={position?.side ?? "bottom"}
            style={position?.style}
            onKeyDown={onMenuKeyDown}
            className={cn(
              "anim-pop z-[70] min-w-44 overflow-y-auto rounded-md border border-white/[0.1] bg-[#202020] p-1 text-left shadow-2xl",
              !position && "invisible",
              state === "closed" && "pointer-events-none",
            )}
          >
            <MenuContext.Provider value={{ close }}>{children}</MenuContext.Provider>
          </div>,
          document.body,
        )}
    </>
  );
}

export function DropdownItem({
  className,
  onClick,
  keepOpen = false,
  checked,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  /** Don't close the menu after clicking (e.g. toggles). */
  keepOpen?: boolean;
  /** Renders a check-box item (role="menuitemcheckbox"). */
  checked?: boolean;
}) {
  const menu = useContext(MenuContext);
  const isCheckbox = checked !== undefined;
  return (
    <button
      type="button"
      role={isCheckbox ? "menuitemcheckbox" : "menuitem"}
      aria-checked={isCheckbox ? checked : undefined}
      data-menu-item=""
      tabIndex={-1}
      onClick={(event) => {
        onClick?.(event);
        if (!keepOpen && !event.defaultPrevented) menu?.close(true);
      }}
      className={cn(
        "flex h-8 w-full items-center gap-2 rounded px-2 text-left text-xs text-[#bbb] transition-colors outline-none hover:bg-white/[0.06] hover:text-white focus-visible:bg-white/[0.06] focus-visible:text-white disabled:pointer-events-none disabled:opacity-45",
        className,
      )}
      {...props}
    >
      {isCheckbox && (
        <span
          aria-hidden
          className={cn(
            "flex size-3.5 shrink-0 items-center justify-center rounded-[3px] border",
            checked ? "border-emerald-400 bg-emerald-400 text-[#06291c]" : "border-white/25",
          )}
        >
          {checked && <Check size={10} strokeWidth={3} />}
        </span>
      )}
      {children}
    </button>
  );
}

/** Non-interactive heading inside a menu. */
export function DropdownLabel({ children }: { children: ReactNode }) {
  return <p className="px-2 pt-1.5 pb-1 text-[10px] font-medium tracking-wider text-[#696969] uppercase">{children}</p>;
}
