"use client"

import * as React from "react"
import { Label as LabelPrimitive, Slot } from "radix-ui"
import type { AnyFieldApi, AnyFormApi } from "@tanstack/form-core"
import type { ReactFormApi } from "@tanstack/react-form"

import { cn } from "@/lib/utils/cn"

type AnyReactFormApi = AnyFormApi &
  ReactFormApi<any, any, any, any, any, any, any, any, any, any, any, any>

interface FormFieldContextValue {
  name: string
  fieldId: string
  descriptionId: string
  errorId: string
  hasError: boolean
}

const FormFieldContext = React.createContext<FormFieldContextValue | null>(null)

function useFormFieldContext() {
  const ctx = React.useContext(FormFieldContext)
  if (!ctx) {
    throw new Error(
      "Form primitives (FormLabel/FormControl/FormDescription/FormError) must be used inside <FormField>"
    )
  }
  return ctx
}

interface FormProps<TFormApi extends AnyReactFormApi>
  extends Omit<React.ComponentProps<"form">, "onSubmit"> {
  form: TFormApi
}

function Form<TFormApi extends AnyReactFormApi>({
  form,
  className,
  children,
  ...props
}: FormProps<TFormApi>) {
  return (
    <form
      data-slot="form"
      className={cn("flex flex-col gap-4", className)}
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
        void form.handleSubmit()
      }}
      {...props}
    >
      {children}
    </form>
  )
}

type FormFieldRenderApi = AnyFieldApi

interface FormFieldProps {
  form: AnyReactFormApi
  name: string
  validators?: Record<string, unknown>
  children: (field: FormFieldRenderApi) => React.ReactNode
}

function FormField({ form, name, validators, children }: FormFieldProps) {
  const FieldComponent = form.Field as unknown as React.ComponentType<{
    name: string
    validators?: Record<string, unknown>
    children: (field: FormFieldRenderApi) => React.ReactNode
  }>

  return (
    <FieldComponent
      name={name}
      {...(validators !== undefined && { validators })}
    >
      {(field: FormFieldRenderApi) => (
        <FormFieldProvider field={field}>{children(field)}</FormFieldProvider>
      )}
    </FieldComponent>
  )
}

function FormFieldProvider({
  field,
  children,
}: {
  field: FormFieldRenderApi
  children: React.ReactNode
}) {
  const reactId = React.useId()
  const value: FormFieldContextValue = {
    name: field.name,
    fieldId: `${reactId}-field`,
    descriptionId: `${reactId}-description`,
    errorId: `${reactId}-error`,
    hasError: field.state.meta.errors.length > 0,
  }

  return (
    <FormFieldContext.Provider value={value}>
      {children}
    </FormFieldContext.Provider>
  )
}

function FormItem({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="form-item"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

function FormLabel({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  const { fieldId, hasError } = useFormFieldContext()
  return (
    <LabelPrimitive.Root
      data-slot="form-label"
      data-error={hasError}
      htmlFor={props.htmlFor ?? fieldId}
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none peer-disabled:cursor-not-allowed peer-disabled:opacity-50 data-[error=true]:text-destructive",
        className
      )}
      {...props}
    />
  )
}

function FormControl({
  ...props
}: React.ComponentProps<typeof Slot.Root>) {
  const { fieldId, descriptionId, errorId, hasError } = useFormFieldContext()
  return (
    <Slot.Root
      data-slot="form-control"
      id={fieldId}
      aria-describedby={hasError ? `${descriptionId} ${errorId}` : descriptionId}
      aria-invalid={hasError}
      {...props}
    />
  )
}

function FormDescription({
  className,
  ...props
}: React.ComponentProps<"p">) {
  const { descriptionId } = useFormFieldContext()
  return (
    <p
      data-slot="form-description"
      id={descriptionId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

function FormError({
  className,
  children,
  ...props
}: React.ComponentProps<"p">) {
  const { errorId } = useFormFieldContext()
  if (children === undefined || children === null || children === false) {
    return null
  }
  return (
    <p
      data-slot="form-error"
      id={errorId}
      className={cn("text-sm font-medium text-destructive", className)}
      {...props}
    >
      {children}
    </p>
  )
}

export {
  Form,
  FormControl,
  FormDescription,
  FormError,
  FormField,
  FormItem,
  FormLabel,
}
