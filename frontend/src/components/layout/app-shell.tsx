import { useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { LogOut, Moon, ShieldAlert, X } from "lucide-react";

import { Badge, cn, CommandPalette, usePresence, type Command } from "@/components/ui";
import { visibleNavigation } from "@/app/navigation";
import { useAuth } from "@/features/auth/auth-context";
import { Sidebar } from "@/components/layout/sidebar";
import { applyTheme } from "@/components/layout/theme-toggle";
import { Topbar } from "@/components/layout/topbar";

const COLLAPSE_KEY = "app_sidebar_collapsed";

function readCollapsed() {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "true";
  } catch {
    return false;
  }
}

/** Authenticated layout: sidebar + topbar + routed page content. */
export function AppShell() {
  const { status, user, logout, can } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const mobileNav = usePresence(mobileOpen, 220);
  const mainRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  // The content area (not the window) scrolls, so reset it when the page changes.
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [pathname]);

  const items = useMemo(
    () => visibleNavigation((key) => can(key), status?.environment),
    [can, status?.environment],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const commands = useMemo<Command[]>(
    () => [
      ...items.map((item) => {
        const Icon = item.icon;
        return {
          label: item.label,
          section: "Go to",
          icon: <Icon size={14} />,
          onSelect: () => navigate(item.path),
        };
      }),
      {
        label: "Toggle theme",
        section: "Preferences",
        icon: <Moon size={14} />,
        onSelect: () =>
          applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"),
      },
      { label: "Sign out", section: "Account", icon: <LogOut size={14} />, onSelect: () => void logout() },
    ],
    [items, navigate, logout],
  );

  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(COLLAPSE_KEY, String(next));
    } catch {
      // ignore
    }
  }

  const sidebarProps = {
    items,
    appName: status?.app_name ?? "Workspace",
    appTagline: status?.app_tagline ?? "",
    user: { name: user?.name ?? "", roleLabel: user?.roles.map((r) => r.name).join(", ") || "No role" },
    onSignOut: () => void logout(),
    onSearch: () => setPaletteOpen(true),
  };

  return (
    <div className="h-dvh overflow-hidden bg-[#171717] text-[#ededed]">
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden overflow-hidden transition-[width] duration-300 ease-in-out lg:block",
          collapsed ? "w-[52px]" : "w-52",
        )}
      >
        <Sidebar collapsed={collapsed} onToggle={toggleSidebar} {...sidebarProps} />
      </div>

      {mobileNav.mounted && (
        <div
          data-state={mobileNav.state}
          onMouseDown={(event) => event.target === event.currentTarget && setMobileOpen(false)}
          className={cn(
            "anim-overlay fixed inset-0 z-40 bg-black/65 backdrop-blur-sm lg:hidden",
            mobileNav.state === "closed" && "pointer-events-none",
          )}
        >
          <div data-state={mobileNav.state} className="anim-sheet-left h-full w-52 shadow-2xl">
            <Sidebar
              collapsed={false}
              mobile
              onToggle={() => setMobileOpen(false)}
              onNavigate={() => setMobileOpen(false)}
              {...sidebarProps}
            />
          </div>
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute top-4 right-4 flex size-9 items-center justify-center rounded-md border border-white/10 bg-[#1b1b1b] text-[#aaa]"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Full-height column: banner + topbar on top, the content area scrolls below them.
          Table pages (DataTablePage) fill exactly the remaining height. */}
      <div
        className={cn(
          "flex h-full flex-col transition-[padding-left] duration-300 ease-in-out",
          collapsed ? "lg:pl-[52px]" : "lg:pl-52",
        )}
      >
        {status?.auth_bypass && (
          <div
            role="alert"
            className="callout-warning flex items-center justify-center gap-2 border-b border-amber-300/20 bg-amber-300/[0.08] px-4 py-1.5 text-[11px] font-medium text-amber-200"
          >
            <ShieldAlert size={13} />
            Authentication is bypassed for development. Delete the .auth-bypass file to re-enable it.
          </div>
        )}
        <Topbar
          onOpenMobile={() => setMobileOpen(true)}
          appName={status?.app_name ?? "Workspace"}
          actions={
            status && status.environment !== "production" ? (
              <Badge tone="warning" className="mr-1 hidden sm:inline-flex">
                {status.environment}
              </Badge>
            ) : undefined
          }
        />
        <main ref={mainRef} className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[1500px] flex-col p-4 md:p-6 lg:p-8 has-[[data-page-layout=table]]:max-w-none">
            <Outlet />
          </div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} commands={commands} />
    </div>
  );
}
