import {
  LayoutDashboard,
  Puzzle,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

/**
 * Sidebar + command-palette entries. To add a screen:
 *   1. add it to app/features/rbac/registry.py (that makes it appear on the Roles page)
 *   2. create src/features/<feature>/<feature>-page.tsx and add a <Route> in src/app/App.tsx
 *   3. add an entry here with the SAME key in `screen`
 * Entries without `screen` are outside role permissions (Settings: every
 * signed-in user has it; the component gallery: development only).
 */
export type NavItem = {
  key: string;
  label: string;
  path: string;
  icon: LucideIcon;
  group: "workspace" | "administration";
  /** Permission key (page) the user needs Read on to see this entry. */
  screen?: string;
  /** Hidden when the server runs with APP_ENV=production. */
  devOnly?: boolean;
};

export const NAVIGATION: NavItem[] = [
  { key: "dashboard", label: "Dashboard", path: "/dashboard", icon: LayoutDashboard, group: "workspace", screen: "dashboard" },
  { key: "users", label: "Users", path: "/users", icon: Users, group: "workspace", screen: "users" },
  { key: "roles", label: "Roles", path: "/roles", icon: ShieldCheck, group: "workspace", screen: "roles" },
  { key: "audit", label: "Audit log", path: "/audit", icon: ScrollText, group: "workspace", screen: "audit" },
  { key: "components", label: "Components", path: "/components", icon: Puzzle, group: "workspace", devOnly: true },
  { key: "settings", label: "Settings", path: "/settings", icon: Settings, group: "administration" },
];

export function visibleNavigation(
  can: (key: string) => boolean,
  environment: string | undefined,
): NavItem[] {
  return NAVIGATION.filter(
    (item) => (!item.screen || can(item.screen)) && (!item.devOnly || environment !== "production"),
  );
}
