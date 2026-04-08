import * as React from "react";
import {
  Controller,
  FormProvider,
  useFormContext,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
  type FieldError,
} from "react-hook-form";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils/cn";
import { Label } from "@/lib/components/ui/Label";

// ---------------------------------------------------------------------------
// Context: FormField passes the field name down to child components
// ---------------------------------------------------------------------------

interface FormFieldContextValue<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  name: TName;
}

const FormFieldContext = React.createContext<FormFieldContextValue | null>(null);

// ---------------------------------------------------------------------------
// Context: FormItem generates a unique id for aria wiring
// ---------------------------------------------------------------------------

interface FormItemContextValue {
  id: string;
}

const FormItemContext = React.createContext<FormItemContextValue | null>(null);

// ---------------------------------------------------------------------------
// useFormField — reads both contexts + react-hook-form state
// ---------------------------------------------------------------------------

function useFormField() {
  const fieldContext = React.useContext(FormFieldContext);
  const itemContext = React.useContext(FormItemContext);

  if (fieldContext === null) {
    throw new Error("useFormField must be used within a <FormField>");
  }
  if (itemContext === null) {
    throw new Error("useFormField must be used within a <FormItem>");
  }

  const { getFieldState, formState } = useFormContext();
  const fieldState = getFieldState(fieldContext.name, formState);

  return {
    id: itemContext.id,
    name: fieldContext.name,
    formItemId: `${itemContext.id}-form-item`,
    formDescriptionId: `${itemContext.id}-form-item-description`,
    formMessageId: `${itemContext.id}-form-item-message`,
    ...fieldState,
  };
}

// ---------------------------------------------------------------------------
// Form — re-export of FormProvider
// ---------------------------------------------------------------------------

const Form = FormProvider;

// ---------------------------------------------------------------------------
// FormField — wraps Controller, provides field name via context
// ---------------------------------------------------------------------------

function FormField<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>(props: ControllerProps<TFieldValues, TName>) {
  const contextValue: FormFieldContextValue<TFieldValues, TName> = { name: props.name };

  return (
    <FormFieldContext.Provider value={contextValue}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// FormItem — container div with generated id for aria wiring
// ---------------------------------------------------------------------------

function FormItem({
  className,
  ref,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { ref?: React.Ref<HTMLDivElement> }) {
  const id = React.useId();

  const contextValue: FormItemContextValue = { id };

  return (
    <FormItemContext.Provider value={contextValue}>
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    </FormItemContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// FormLabel — label wired to the form control via htmlFor
// ---------------------------------------------------------------------------

function FormLabel({
  className,
  ref,
  ...props
}: React.ComponentPropsWithoutRef<typeof Label> & { ref?: React.Ref<HTMLLabelElement> }) {
  const { error, formItemId } = useFormField();

  return (
    <Label
      ref={ref}
      className={cn(error !== undefined && "text-destructive", className)}
      htmlFor={formItemId}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// FormControl — Slot that sets id + aria attributes on its single child
// ---------------------------------------------------------------------------

function FormControl({
  ref,
  ...props
}: React.ComponentPropsWithoutRef<typeof Slot> & { ref?: React.Ref<HTMLElement> }) {
  const { error, formItemId, formDescriptionId, formMessageId } =
    useFormField();

  const hasError = error !== undefined;

  const ariaDescribedBy = hasError
    ? `${formDescriptionId} ${formMessageId}`
    : formDescriptionId;

  return (
    <Slot
      ref={ref}
      id={formItemId}
      aria-describedby={ariaDescribedBy}
      aria-invalid={hasError || undefined}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// FormDescription — help text wired via aria-describedby
// ---------------------------------------------------------------------------

function FormDescription({
  className,
  ref,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & { ref?: React.Ref<HTMLParagraphElement> }) {
  const { formDescriptionId } = useFormField();

  return (
    <p
      ref={ref}
      id={formDescriptionId}
      className={cn("text-[0.8rem] text-muted-foreground", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// FormMessage — displays validation error with role="alert"
// ---------------------------------------------------------------------------

function FormMessage({
  className,
  children,
  ref,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & { ref?: React.Ref<HTMLParagraphElement> }) {
  const { error, formMessageId } = useFormField();
  const body = extractErrorMessage(error) ?? children;

  if (body === undefined) {
    return null;
  }

  return (
    <p
      ref={ref}
      id={formMessageId}
      className={cn("text-[0.8rem] font-medium text-destructive", className)}
      role="alert"
      {...props}
    >
      {body}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractErrorMessage(error: FieldError | undefined): string | undefined {
  if (error === undefined) {
    return undefined;
  }
  return typeof error.message === "string" ? error.message : undefined;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  useFormField,
};
