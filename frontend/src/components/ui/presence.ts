import { useEffect, useLayoutEffect, useState, type CSSProperties, type RefObject } from "react";

/**
 * Keeps an element mounted while it animates out.
 *
 *   const { mounted, state } = usePresence(open);
 *   {mounted && <div data-state={state} className="anim-dialog">…</div>}
 *
 * `state` is "open" or "closed"; CSS (globals.css, `.anim-*`) plays the enter
 * animation for "open" and the exit animation for "closed". The element is
 * unmounted `exitMs` after closing; keep it equal to the CSS exit duration.
 */
export function usePresence(open: boolean, exitMs = 180) {
  const [present, setPresent] = useState(open);
  if (open && !present) setPresent(true); // mount in the same render that opens

  useEffect(() => {
    if (open || !present) return;
    const id = window.setTimeout(() => setPresent(false), exitMs);
    return () => window.clearTimeout(id);
  }, [open, present, exitMs]);

  return { mounted: open || present, state: (open ? "open" : "closed") as "open" | "closed" };
}

/**
 * Remembers the last non-null value, so a dialog can keep showing its content
 * while it animates out after the parent cleared the selection:
 *
 *   const shown = useLatest(editing);
 *   {shown && <EditDialog user={shown} open={editing !== null} … />}
 */
export function useLatest<T>(value: T | null | undefined): T | null {
  const [latest, setLatest] = useState<T | null>(value ?? null);
  if (value != null && value !== latest) setLatest(value);
  return value ?? latest;
}

/**
 * Viewport position for a popover (menu, select list) anchored to an element.
 * Opens below the anchor, or above when there is not enough room; follows the
 * anchor on scroll and resize. Returns null until measured.
 */
export function useAnchoredPosition(
  anchor: RefObject<HTMLElement | null>,
  open: boolean,
  { align = "left", matchWidth = false, maxHeight = 288 }: { align?: "left" | "right"; matchWidth?: boolean; maxHeight?: number } = {},
) {
  const [position, setPosition] = useState<{ style: CSSProperties; side: "top" | "bottom" } | null>(null);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const el = anchor.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const below = window.innerHeight - r.bottom - 12;
      const above = r.top - 12;
      const side = below < Math.min(maxHeight, 220) && above > below ? "top" : "bottom";
      const style: CSSProperties = {
        position: "fixed",
        maxHeight: Math.max(120, Math.min(maxHeight, side === "bottom" ? below : above)),
      };
      if (side === "bottom") style.top = r.bottom + 4;
      else style.bottom = window.innerHeight - r.top + 4;
      if (align === "right") style.right = Math.max(8, window.innerWidth - r.right);
      else style.left = Math.max(8, r.left);
      if (matchWidth) style.minWidth = r.width;
      setPosition({ style, side });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [anchor, open, align, matchWidth, maxHeight]);

  return position;
}
