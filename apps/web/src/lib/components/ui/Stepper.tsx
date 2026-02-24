import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface StepperProps {
  steps: string[];
  currentStep: number;
  onStepClick?: (index: number) => void;
  className?: string;
}

export function Stepper({ steps, currentStep, onStepClick, className }: StepperProps) {
  return (
    <nav aria-label="Progress" className={cn("flex items-center gap-2", className)}>
      {steps.map((label, i) => {
        const isCompleted = i < currentStep;
        const isActive = i === currentStep;
        const isClickable = onStepClick && i <= currentStep;

        return (
          <React.Fragment key={label}>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => isClickable && onStepClick(i)}
                disabled={!isClickable}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-all duration-200",
                  isCompleted && "bg-success text-success-foreground",
                  isActive && "bg-primary text-primary-foreground shadow-sm",
                  !isCompleted && !isActive && "bg-muted text-muted-foreground",
                  isClickable &&
                    "cursor-pointer hover:ring-2 hover:ring-ring hover:ring-offset-2 hover:ring-offset-background",
                  !isClickable && "cursor-default",
                )}
                aria-current={isActive ? "step" : undefined}
              >
                {isCompleted ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </button>
              <span
                className={cn(
                  "text-sm font-medium transition-colors duration-200",
                  isActive ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={cn(
                  "mx-1 h-px w-8 transition-colors duration-200",
                  i < currentStep ? "bg-success" : "bg-border",
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
