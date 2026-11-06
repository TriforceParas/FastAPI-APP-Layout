import { useLocation } from "react-router";
import { Building2, Menu } from "lucide-react";

import { NAVIGATION } from "@/app/navigation";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export function Topbar({
  onOpenMobile,
  appName,
  actions,
}: {
  onOpenMobile: () => void;
  appName: string;
  actions?: React.ReactNode;
}) {
  const { pathname } = useLocation();
  const current = NAVIGATION.find(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  );

  return (
    <header className="relative z-10 flex h-14 shrink-0 items-center border-b border-white/[0.08] bg-[#171717]/95 px-4 backdrop-blur md:px-6">
      <button
        type="button"
        aria-label="Open navigation"
        onClick={onOpenMobile}
        className="mr-3 flex size-8 items-center justify-center rounded-md text-[#999] hover:bg-white/[0.05] hover:text-white lg:hidden"
      >
        <Menu size={17} />
      </button>
      <div className="flex min-w-0 items-center gap-2 text-xs text-[#858585]">
        <Building2 size={14} className="shrink-0" />
        <span className="hidden sm:inline">{appName}</span>
        <span className="hidden text-[#4e4e4e] sm:inline">/</span>
        <span className="truncate font-medium text-[#d4d4d4]">{current?.label ?? "Workspace"}</span>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        {actions}
        <ThemeToggle />
      </div>
    </header>
  );
}
