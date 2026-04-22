"use client"

import * as React from "react"
import { CheckIcon, ChevronsUpDownIcon, XIcon } from "lucide-react"

import { cn } from "@/lib/utils/cn"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface ComboboxOption {
  value: string
  label: string
  disabled?: boolean
}

interface ComboboxBaseProps {
  options: ComboboxOption[]
  placeholder?: string
  searchPlaceholder?: string
  emptyMessage?: string
  disabled?: boolean
  className?: string
  triggerClassName?: string
  contentClassName?: string
  groupBy?: (option: ComboboxOption) => string
}

interface ComboboxSingleProps extends ComboboxBaseProps {
  multiple?: false
  value: string | null
  onChange: (value: string | null) => void
}

interface ComboboxMultipleProps extends ComboboxBaseProps {
  multiple: true
  value: string[]
  onChange: (value: string[]) => void
}

type ComboboxProps = ComboboxSingleProps | ComboboxMultipleProps

function isMultiple(props: ComboboxProps): props is ComboboxMultipleProps {
  return props.multiple === true
}

function groupOptions(
  options: ComboboxOption[],
  groupBy: ((option: ComboboxOption) => string) | undefined
): Array<{ heading: string | null; items: ComboboxOption[] }> {
  if (!groupBy) {
    return [{ heading: null, items: options }]
  }
  const buckets = new Map<string, ComboboxOption[]>()
  for (const option of options) {
    const key = groupBy(option)
    const bucket = buckets.get(key) ?? []
    bucket.push(option)
    buckets.set(key, bucket)
  }
  return [...buckets.entries()].map(([heading, items]) => ({ heading, items }))
}

function Combobox(props: ComboboxProps) {
  const {
    options,
    placeholder = "Select...",
    searchPlaceholder = "Search...",
    emptyMessage = "No results.",
    disabled,
    className,
    triggerClassName,
    contentClassName,
    groupBy,
  } = props

  const [open, setOpen] = React.useState(false)

  const grouped = groupOptions(options, groupBy)
  const optionByValue = new Map(options.map((o) => [o.value, o]))

  if (isMultiple(props)) {
    const { value, onChange } = props
    const selected = value
      .map((v) => optionByValue.get(v))
      .filter((o): o is ComboboxOption => Boolean(o))

    const toggle = (v: string) => {
      if (value.includes(v)) {
        onChange(value.filter((entry) => entry !== v))
      } else {
        onChange([...value, v])
      }
    }

    const removeChip = (v: string) => {
      onChange(value.filter((entry) => entry !== v))
    }

    return (
      <div data-slot="combobox" className={cn("w-full", className)}>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={open}
              disabled={disabled}
              className={cn(
                "h-auto min-h-9 w-full justify-between gap-2 px-3 py-1.5 font-normal",
                triggerClassName
              )}
            >
              {selected.length === 0 ? (
                <span className="text-muted-foreground">{placeholder}</span>
              ) : (
                <div
                  data-slot="combobox-chips"
                  className="flex flex-1 flex-wrap items-center gap-1"
                >
                  {selected.map((option) => (
                    <Badge
                      key={option.value}
                      variant="secondary"
                      className="gap-1 px-1.5 py-0.5 text-xs font-normal"
                    >
                      <span>{option.label}</span>
                      <span
                        role="button"
                        tabIndex={0}
                        aria-label={`Remove ${option.label}`}
                        className="-mr-0.5 inline-flex size-3.5 cursor-pointer items-center justify-center rounded-sm hover:bg-muted-foreground/20"
                        onPointerDown={(event) => {
                          event.stopPropagation()
                          event.preventDefault()
                          removeChip(option.value)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            removeChip(option.value)
                          }
                        }}
                      >
                        <XIcon className="size-3" />
                      </span>
                    </Badge>
                  ))}
                </div>
              )}
              <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className={cn("w-[var(--radix-popover-trigger-width)] p-0", contentClassName)}
          >
            <ComboboxBody
              grouped={grouped}
              searchPlaceholder={searchPlaceholder}
              emptyMessage={emptyMessage}
              isSelected={(v) => value.includes(v)}
              onPick={toggle}
              closeOnPick={false}
              setOpen={setOpen}
            />
          </PopoverContent>
        </Popover>
      </div>
    )
  }

  const { value, onChange } = props
  const selected = value !== null ? optionByValue.get(value) : undefined

  return (
    <div data-slot="combobox" className={cn("w-full", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              "w-full justify-between gap-2 font-normal",
              !selected && "text-muted-foreground",
              triggerClassName
            )}
          >
            <span className="truncate">
              {selected ? selected.label : placeholder}
            </span>
            <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className={cn("w-[var(--radix-popover-trigger-width)] p-0", contentClassName)}
        >
          <ComboboxBody
            grouped={grouped}
            searchPlaceholder={searchPlaceholder}
            emptyMessage={emptyMessage}
            isSelected={(v) => v === value}
            onPick={(v) => {
              onChange(v === value ? null : v)
            }}
            closeOnPick
            setOpen={setOpen}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

interface ComboboxBodyProps {
  grouped: Array<{ heading: string | null; items: ComboboxOption[] }>
  searchPlaceholder: string
  emptyMessage: string
  isSelected: (value: string) => boolean
  onPick: (value: string) => void
  closeOnPick: boolean
  setOpen: (open: boolean) => void
}

function ComboboxBody({
  grouped,
  searchPlaceholder,
  emptyMessage,
  isSelected,
  onPick,
  closeOnPick,
  setOpen,
}: ComboboxBodyProps) {
  return (
    <Command>
      <CommandInput placeholder={searchPlaceholder} />
      <CommandList>
        <CommandEmpty>{emptyMessage}</CommandEmpty>
        {grouped.map((group, idx) => (
          <CommandGroup
            key={group.heading ?? `__group_${idx}`}
            {...(group.heading !== null && { heading: group.heading })}
          >
            {group.items.map((option) => {
              const selected = isSelected(option.value)
              return (
                <CommandItem
                  key={option.value}
                  value={option.value}
                  disabled={option.disabled ?? false}
                  onSelect={() => {
                    onPick(option.value)
                    if (closeOnPick) {
                      setOpen(false)
                    }
                  }}
                >
                  <CheckIcon
                    className={cn(
                      "size-4",
                      selected ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <span>{option.label}</span>
                </CommandItem>
              )
            })}
          </CommandGroup>
        ))}
      </CommandList>
    </Command>
  )
}

export { Combobox, type ComboboxOption, type ComboboxProps }
