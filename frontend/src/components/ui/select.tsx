import {
  Children,
  Fragment,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type OptionHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";

import { useAnchoredPosition, usePresence } from "./presence";
import { cn } from "./primitives";

type Option = { value: string; label: ReactNode; text: string; disabled: boolean };

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

function readOptions(children: ReactNode): Option[] {
  const out: Option[] = [];
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;
    if (child.type === Fragment) {
      out.push(...readOptions((child.props as { children?: ReactNode }).children));
    } else if (child.type === "option") {
      const props = child.props as OptionHTMLAttributes<HTMLOptionElement>;
      const text = textOf(props.children);
      out.push({ value: String(props.value ?? text), label: props.children, text, disabled: Boolean(props.disabled) });
    }
  });
  return out;
}

export type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "value" | "defaultValue" | "onChange"> & {
  value?: string | number;
  defaultValue?: string | number;
  /** Same shape as a native select's change event: use `e.target.value`. */
  onChange?: (event: { target: { value: string; name: string } }) => void;
  /** Simpler alternative to onChange. */
  onValueChange?: (value: string) => void;
  /** Shown when no option matches the value. */
  placeholder?: string;
};

/**
 * Styled single-select. Use it like a native <select>: pass <option> children,
 * `value` + `onChange` (controlled) or `defaultValue` + `name` (inside a form; a
 * hidden input carries the value into FormData).
 *
 * Keyboard: ↓/↑/Enter/Space open; ↑/↓/Home/End move; Enter/Space choose;
 * Esc closes; typing jumps to an option. Implements the ARIA combobox/listbox pattern.
 */
export function Select({
  value,
  defaultValue,
  onChange,
  onValueChange,
  name,
  id,
  disabled,
  className,
  children,
  placeholder,
  ...rest
}: SelectProps) {
  const options = readOptions(children);
  const [internal, setInternal] = useState(String(defaultValue ?? options[0]?.value ?? ""));
  const current = value !== undefined ? String(value) : internal;
  const selectedIndex = options.findIndex((o) => o.value === current);
  const selected = options[selectedIndex];

  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const { mounted, state } = usePresence(open, 140);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const position = useAnchoredPosition(buttonRef, open, { matchWidth: true });
  const autoId = useId();
  const buttonId = id ?? `${autoId}-select`;
  const listId = `${autoId}-listbox`;
  const typed = useRef({ text: "", at: 0 });

  const enabled = (i: number) => i >= 0 && i < options.length && !options[i]!.disabled;
  const step = (from: number, delta: 1 | -1) => {
    for (let i = from + delta; i >= 0 && i < options.length; i += delta) if (enabled(i)) return i;
    return from;
  };
  const first = () => step(-1, 1);
  const last = () => step(options.length, -1);

  function openList() {
    if (disabled) return;
    setActive(enabled(selectedIndex) ? selectedIndex : first());
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    if (value === undefined) setInternal(option.value);
    if (option.value !== current) {
      onChange?.({ target: { value: option.value, name: name ?? "" } });
      onValueChange?.(option.value);
    }
    setOpen(false);
    buttonRef.current?.focus();
  }

  function typeahead(key: string) {
    const now = Date.now();
    typed.current = { text: (now - typed.current.at > 600 ? "" : typed.current.text) + key.toLowerCase(), at: now };
    const start = open ? active : selectedIndex;
    const order = [...options.keys()].map((i) => (i + start + 1) % options.length);
    const match = order.find((i) => enabled(i) && options[i]!.text.toLowerCase().startsWith(typed.current.text));
    if (match === undefined) return;
    if (open) setActive(match);
    else choose(match);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const key = event.key;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(key)) {
        event.preventDefault();
        openList();
      } else if (key.length === 1 && /\S/.test(key)) typeahead(key);
      return;
    }
    if (key === "ArrowDown") setActive((a) => step(a, 1));
    else if (key === "ArrowUp") setActive((a) => step(a, -1));
    else if (key === "Home") setActive(first());
    else if (key === "End") setActive(last());
    else if (key === "Enter" || key === " ") choose(active);
    else if (key === "Escape") {
      event.stopPropagation(); // don't also close a surrounding dialog
      setOpen(false);
    } else if (key === "Tab") {
      setOpen(false);
      return;
    } else if (key.length === 1) {
      typeahead(key);
    } else return;
    event.preventDefault();
  }

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!listRef.current?.contains(target) && !buttonRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // Keep the active option visible.
  useEffect(() => {
    if (open && active >= 0) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active, listId]);

  return (
    <span className="relative block" data-ui="select">
      <button
        ref={buttonRef}
        id={buttonId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        aria-label={rest["aria-label"]}
        aria-invalid={rest["aria-invalid"]}
        aria-describedby={rest["aria-describedby"]}
        disabled={disabled}
        data-select-trigger=""
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKeyDown}
        className={cn(
          "flex h-9 w-full items-center rounded-md border border-white/[0.11] bg-[#151515] px-3 pr-9 text-left text-sm text-[#d8d8d8] transition hover:border-white/[0.16] disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
      >
        <span className={cn("min-w-0 flex-1 truncate", (!selected || selected.value === "") && "text-[#7a7a7a]")}>
          {selected?.label ?? placeholder ?? " "}
        </span>
      </button>
      <ChevronDown
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-[#8f8f8f] transition-transform duration-200",
          open && "rotate-180",
        )}
      />
      {name !== undefined && <input type="hidden" name={name} value={current} disabled={disabled} />}
      {mounted &&
        createPortal(
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-labelledby={buttonId}
            data-state={state}
            data-side={position?.side ?? "bottom"}
            style={position?.style}
            onMouseDown={(event) => event.preventDefault()} // keep focus on the button
            className={cn(
              "anim-pop z-[70] overflow-y-auto rounded-md border border-white/[0.1] bg-[#202020] p-1 shadow-2xl",
              !position && "invisible",
              state === "closed" && "pointer-events-none",
            )}
          >
            {options.map((option, index) => {
              const isSelected = option.value === current;
              return (
                <li
                  key={`${option.value}-${index}`}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={option.disabled || undefined}
                  data-option=""
                  data-active={index === active ? "true" : undefined}
                  onMouseEnter={() => enabled(index) && setActive(index)}
                  onClick={() => choose(index)}
                  className={cn(
                    "flex min-h-8 cursor-pointer items-center gap-2 rounded px-2.5 py-1.5 text-sm text-[#cfcfcf] transition-colors",
                    isSelected && "font-medium text-emerald-300",
                    option.disabled && "cursor-not-allowed opacity-40",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{option.label}</span>
                  {isSelected && <Check aria-hidden size={14} className="shrink-0" />}
                </li>
              );
            })}
          </ul>,
          document.body,
        )}
    </span>
  );
}
