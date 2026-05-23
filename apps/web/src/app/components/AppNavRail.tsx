"use client";

import { useSuspenseQuery } from "@tanstack/react-query";
import {
  Bookmark,
  Layers,
  MessageCircle,
  PanelLeft,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

const ACTIVE_PILL =
  "bg-primary/15 text-primary hover:bg-primary/20 hover:text-primary";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SiteIcon } from "@/features/sites/components/SiteIcon";
import { sitesOptions } from "@/lib/api/sites";
import { useSessionStore } from "@/state/useSessionStore";

interface AppNavRailProps {
  siteId: string;
  onSiteChange: (siteId: string) => void;
  onOpenSettings: () => void;
  onToggleSidebar: () => void;
  sidebarExpanded: boolean;
}

interface NavSpec {
  slug: "conversation" | "workbench" | "saved";
  icon: LucideIcon;
  label: string;
}

const NAV: NavSpec[] = [
  { slug: "conversation", icon: MessageCircle, label: "Chat" },
  { slug: "workbench", icon: Layers, label: "Workbench" },
  { slug: "saved", icon: Bookmark, label: "Saved strategies" },
];

export function AppNavRail({
  siteId,
  onSiteChange,
  onOpenSettings,
  onToggleSidebar,
  sidebarExpanded,
}: AppNavRailProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex h-full w-11 shrink-0 flex-col items-center gap-1 border-r border-border bg-sidebar py-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleSidebar}
              aria-label={
                sidebarExpanded
                  ? "Collapse conversation sidebar"
                  : "Open conversation sidebar"
              }
              aria-pressed={sidebarExpanded}
              className={cn(sidebarExpanded && ACTIVE_PILL)}
            >
              <PanelLeft className="h-4 w-4" aria-hidden />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {sidebarExpanded ? "Hide conversations" : "Show conversations"}
          </TooltipContent>
        </Tooltip>

        <div className="my-1 h-px w-6 bg-border" />

        {NAV.map((item) => {
          const href = `/${siteId}/${item.slug}`;
          const active = pathname.startsWith(href);
          const Icon = item.icon;
          return (
            <Tooltip key={item.slug}>
              <TooltipTrigger asChild>
                <Link
                  href={href}
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    buttonVariants({ variant: "ghost", size: "icon" }),
                    active && ACTIVE_PILL,
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">{item.label}</TooltipContent>
            </Tooltip>
          );
        })}

        <div className="mt-auto flex flex-col items-center gap-1">
          <SiteSwitcherButton siteId={siteId} onChange={onSiteChange} />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onOpenSettings}
                aria-label="Settings"
                data-testid="nav-rail-settings-button"
              >
                <Settings className="h-4 w-4" aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Settings</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  );
}

function SiteSwitcherButton({
  siteId,
  onChange,
}: {
  siteId: string;
  onChange: (id: string) => void;
}) {
  const { data: sites } = useSuspenseQuery(sitesOptions());
  const setSelectedSite = useSessionStore((s) => s.setSelectedSite);

  const components = sites.filter((s) => !s.isPortal);
  const portal = sites.filter((s) => s.isPortal);

  const pick = (id: string) => {
    setSelectedSite(id);
    onChange(id);
  };

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Switch database"
              className="p-0"
            >
              <SiteIcon siteId={siteId} size={22} />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="right">Switch database</TooltipContent>
      </Tooltip>
      <DropdownMenuContent
        side="right"
        align="end"
        sideOffset={8}
        className="min-w-[220px]"
      >
        <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Component sites
        </DropdownMenuLabel>
        <DropdownMenuGroup>
          {components.map((site) => (
            <SiteMenuItem
              key={site.id}
              id={site.id}
              label={site.displayName}
              active={site.id === siteId}
              onPick={pick}
            />
          ))}
        </DropdownMenuGroup>
        {portal.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Portal
            </DropdownMenuLabel>
            <DropdownMenuGroup>
              {portal.map((site) => (
                <SiteMenuItem
                  key={site.id}
                  id={site.id}
                  label={site.displayName}
                  active={site.id === siteId}
                  onPick={pick}
                />
              ))}
            </DropdownMenuGroup>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SiteMenuItem({
  id,
  label,
  active,
  onPick,
}: {
  id: string;
  label: string;
  active: boolean;
  onPick: (id: string) => void;
}) {
  return (
    <DropdownMenuItem
      onSelect={() => onPick(id)}
      data-testid={`site-menu-item-${id}`}
      className={cn(active && "bg-primary/15 text-primary")}
    >
      <SiteIcon siteId={id} size={16} />
      <span className="flex-1 truncate">{label}</span>
    </DropdownMenuItem>
  );
}
