"use client";

import type { ComponentPropsWithoutRef, ComponentRef, Ref } from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils/cn";

const DropdownMenu = DropdownMenuPrimitive.Root;
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

function DropdownMenuContent({
  className,
  sideOffset = 4,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content> & {
  ref?: Ref<ComponentRef<typeof DropdownMenuPrimitive.Content>>;
}) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-[8rem] overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md animate-fade-in",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

function DropdownMenuItem({
  className,
  inset,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {
  inset?: boolean;
  ref?: Ref<ComponentRef<typeof DropdownMenuPrimitive.Item>>;
}) {
  return (
    <DropdownMenuPrimitive.Item
      ref={ref}
      className={cn(
        "relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors",
        "focus:bg-accent focus:text-accent-foreground",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        (inset ?? false) && "pl-8",
        className,
      )}
      {...props}
    />
  );
}

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem };
