"use client";

import type { ComponentPropsWithoutRef, ComponentRef, HTMLAttributes, Ref } from "react";
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import { cn } from "@/lib/utils/cn";

const AlertDialog = AlertDialogPrimitive.Root;
const AlertDialogPortal = AlertDialogPrimitive.Portal;

function AlertDialogOverlay({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Overlay> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Overlay>>;
}) {
  return (
    <AlertDialogPrimitive.Overlay
      ref={ref}
      className={cn("fixed inset-0 z-50 bg-black/80 animate-fade-in", className)}
      {...props}
    />
  );
}

function AlertDialogContent({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Content> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Content>>;
}) {
  return (
    <AlertDialogPortal>
      <AlertDialogOverlay />
      <AlertDialogPrimitive.Content
        ref={ref}
        className={cn(
          "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-background p-6 shadow-lg duration-200 animate-fade-in sm:rounded-lg",
          className,
        )}
        {...props}
      />
    </AlertDialogPortal>
  );
}

function AlertDialogHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-2 text-center sm:text-left", className)}
      {...props}
    />
  );
}

function AlertDialogFooter({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
        className,
      )}
      {...props}
    />
  );
}

function AlertDialogTitle({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Title> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Title>>;
}) {
  return (
    <AlertDialogPrimitive.Title
      ref={ref}
      className={cn("text-lg font-semibold", className)}
      {...props}
    />
  );
}

function AlertDialogDescription({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Description> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Description>>;
}) {
  return (
    <AlertDialogPrimitive.Description
      ref={ref}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

function AlertDialogAction({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Action> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Action>>;
}) {
  return (
    <AlertDialogPrimitive.Action
      ref={ref}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground ring-offset-background transition-colors",
        "hover:bg-primary/90",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

function AlertDialogCancel({
  className,
  ref,
  ...props
}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Cancel> & {
  ref?: Ref<ComponentRef<typeof AlertDialogPrimitive.Cancel>>;
}) {
  return (
    <AlertDialogPrimitive.Cancel
      ref={ref}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-semibold ring-offset-background transition-colors",
        "hover:bg-accent hover:text-accent-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        "mt-2 sm:mt-0",
        className,
      )}
      {...props}
    />
  );
}

export {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
};
