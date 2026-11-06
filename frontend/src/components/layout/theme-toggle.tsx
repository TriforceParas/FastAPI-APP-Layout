import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

import { cn } from "@/components/ui";

type Theme = "dark" | "light";

const THEME_EVENT = "app-theme-change";
const STORAGE_KEY = "app_theme"; // also read by public/theme-init.js

function subscribe(onStoreChange: () => void) {
  window.addEventListener(THEME_EVENT, onStoreChange);
  return () => window.removeEventListener(THEME_EVENT, onStoreChange);
}

function getThemeSnapshot(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // storage unavailable (private mode); theme still applies for this tab
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

export function useTheme() {
  return useSyncExternalStore(subscribe, getThemeSnapshot, () => "dark" as Theme);
}

export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      aria-label={`Switch to ${nextTheme} mode`}
      title={`Switch to ${nextTheme} mode`}
      onClick={() => applyTheme(nextTheme)}
      className={cn(
        "flex size-8 items-center justify-center rounded-md text-[#8a8a8a] transition-colors hover:bg-white/[0.05] hover:text-white",
        className,
      )}
    >
      {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
