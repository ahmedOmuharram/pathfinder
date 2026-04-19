import type { LabelHTMLAttributes, Ref } from "react";
import { cn } from "@/lib/utils/cn";

interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
  ref?: Ref<HTMLLabelElement> | undefined;
}

function Label({ className, children, required, ref, ...props }: LabelProps) {
  return (
    <label
      ref={ref}
      className={cn(
        "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className,
      )}
      {...props}
    >
      {children}
      {(required ?? false) && <span className="ml-0.5 text-destructive">*</span>}
    </label>
  );
}

export { Label };
