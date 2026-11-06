import { Link, useLocation } from "react-router";
import { Hexagon, LogOut, Menu, Search } from "lucide-react";

import { Avatar, cn, Kbd } from "@/components/ui";
import type { NavItem } from "@/app/navigation";

type SidebarProps = {
  collapsed: boolean;
  mobile?: boolean;
  onNavigate?: () => void;
  onToggle: () => void;
  onSearch: () => void;
  items: NavItem[];
  appName: string;
  appTagline: string;
  user: { name: string; roleLabel: string };
  onSignOut: () => void;
};

function SidebarLabel({
  collapsed,
  children,
  className,
}: {
  collapsed: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      aria-hidden={collapsed}
      className={cn(
        "min-w-0 overflow-hidden whitespace-nowrap",
        collapsed && "pointer-events-none",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Sidebar({
  collapsed,
  mobile = false,
  onNavigate,
  onToggle,
  onSearch,
  items,
  appName,
  appTagline,
  user,
  onSignOut,
}: SidebarProps) {
  const { pathname } = useLocation();
  const isCollapsed = mobile ? false : collapsed;
  const workspace = items.filter((item) => item.group === "workspace");
  const administration = items.filter((item) => item.group === "administration");

  const renderNavigation = (list: NavItem[]) =>
    list.map((item) => {
      const active = pathname === item.path || pathname.startsWith(`${item.path}/`);
      const Icon = item.icon;
      return (
        <Link
          key={item.key}
          to={item.path}
          title={isCollapsed ? item.label : undefined}
          aria-label={isCollapsed ? item.label : undefined}
          aria-current={active ? "page" : undefined}
          onClick={onNavigate}
          data-active={active ? "true" : "false"}
          className={cn(
            "grid h-9 w-full grid-cols-[36px_minmax(0,1fr)] items-center overflow-hidden rounded-md text-xs font-medium transition-colors duration-150",
            active
              ? "bg-white/[0.075] text-white"
              : "text-[#8f8f8f] hover:bg-white/[0.04] hover:text-[#d8d8d8]",
          )}
        >
          <span className="flex size-9 items-center justify-center">
            <Icon aria-hidden size={16} strokeWidth={1.8} />
          </span>
          <SidebarLabel collapsed={isCollapsed} className="pr-2.5">
            {item.label}
          </SidebarLabel>
        </Link>
      );
    });

  return (
    <aside className="flex h-full flex-col overflow-hidden border-r border-white/[0.08] bg-[#111111]">
      <div className="grid h-14 w-full shrink-0 grid-cols-[36px_minmax(0,1fr)] items-center border-b border-white/[0.08] px-2">
        <span className="flex size-9 items-center justify-center">
          <button
            type="button"
            onClick={onToggle}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!isCollapsed}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex size-7 items-center justify-center rounded-md text-[#777] transition-colors hover:bg-white/[0.06] hover:text-white"
          >
            <Menu size={15} />
          </button>
        </span>
        <div aria-hidden={isCollapsed} className="flex min-w-0 items-center gap-2.5 overflow-hidden">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-emerald-400 text-[#062a1c]">
            <Hexagon size={16} strokeWidth={2.25} />
          </div>
          <SidebarLabel collapsed={isCollapsed} className="min-w-max">
            <span className="block text-sm font-semibold tracking-tight">{appName}</span>
            <span className="block text-[11px] text-[#8f8f8f]">{appTagline}</span>
          </SidebarLabel>
        </div>
      </div>

      <div className="px-2 py-3">
        <button
          type="button"
          onClick={onSearch}
          title={isCollapsed ? "Search" : undefined}
          aria-label="Search"
          className="grid h-9 w-full grid-cols-[34px_minmax(0,1fr)] items-center overflow-hidden rounded-md border border-white/[0.08] bg-white/[0.035] text-left text-xs text-[#a9a9a9] transition-colors hover:bg-white/[0.06]"
        >
          <span className="flex size-[34px] items-center justify-center">
            <Search size={14} />
          </span>
          <SidebarLabel collapsed={isCollapsed} className="flex items-center gap-2 pr-2.5 pl-px">
            <span className="flex-1">Search</span>
            <Kbd>⌘ K</Kbd>
          </SidebarLabel>
        </button>
      </div>

      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2" aria-label="Primary navigation">
        {renderNavigation(workspace)}
      </nav>

      <div className="space-y-0.5 border-t border-white/[0.08] px-2 py-3">
        {renderNavigation(administration)}
        <div className="mt-2 grid h-9 w-full grid-cols-[34px_minmax(0,1fr)] items-center overflow-hidden rounded-md border border-white/[0.08]">
          <span className="flex size-[34px] items-center justify-center">
            <Avatar name={user.name} size="sm" />
          </span>
          <div className="flex min-w-0 items-center gap-1 overflow-hidden pr-1.5 pl-px">
            <SidebarLabel collapsed={isCollapsed} className="flex-1">
              <span className="block truncate text-xs font-medium text-[#e6e6e6]">{user.name}</span>
              <span className="block truncate text-[10px] text-[#777]">{user.roleLabel}</span>
            </SidebarLabel>
            <button
              type="button"
              onClick={onSignOut}
              aria-label="Sign out"
              aria-hidden={isCollapsed}
              tabIndex={isCollapsed ? -1 : undefined}
              title="Sign out"
              className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded text-[#777] hover:bg-white/[0.05] hover:text-white",
                isCollapsed && "pointer-events-none",
              )}
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
