import { useState, useMemo, useRef, useEffect } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "./ui/command";
import { Check, ChevronsUpDown, Type as TypeIcon, X } from "lucide-react";
import { cn } from "../lib/utils";

/**
 * SearchableCombo — Dual-mode input for proxy targeting fields.
 *
 * Behavior:
 *   • Renders like a Select trigger with the current value.
 *   • Opens a Command palette on click (searchable + keyboard nav).
 *   • Shows all `options`; the user can filter by typing.
 *   • If typed text doesn't match any option, a "Use custom: …" item
 *     appears at the bottom so any provider-accepted string can be
 *     entered without leaving the picker.
 *   • A tiny × button clears the value.
 *
 * Props:
 *   value       string — current selected value (matches option.value or custom)
 *   onChange    (value: string) => void
 *   options     Array<{ value: string, label: string, hint?: string }>
 *   placeholder string
 *   allowCustom boolean (default true) — if false, only listed options
 *   emptyText   string — shown when zero matches and custom disabled
 *   testid      string — data-testid prefix for the trigger & items
 *   disabled    boolean
 *   className   string — extra classes for the trigger
 */
export default function SearchableCombo({
  value,
  onChange,
  options = [],
  placeholder = "Select or type…",
  allowCustom = true,
  emptyText = "No matches",
  testid = "searchable-combo",
  disabled = false,
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const triggerRef = useRef(null);

  // Reset query when popover closes so re-opening starts fresh.
  useEffect(() => { if (!open) setQuery(""); }, [open]);

  const norm = (s) => String(s || "").toLowerCase().trim();
  const filtered = useMemo(() => {
    const q = norm(query);
    if (!q) return options;
    return options.filter((o) =>
      norm(o.value).includes(q) ||
      norm(o.label).includes(q) ||
      norm(o.hint).includes(q)
    );
  }, [options, query]);

  const currentLabel = useMemo(() => {
    if (!value) return "";
    const m = options.find((o) => norm(o.value) === norm(value));
    return m ? m.label : value; // custom typed value → show raw
  }, [options, value]);

  const trimmedQuery = query.trim();
  const showCustomRow =
    allowCustom &&
    trimmedQuery.length > 0 &&
    !filtered.some((o) => norm(o.value) === norm(trimmedQuery));

  const pick = (v) => {
    onChange?.(v);
    setOpen(false);
  };

  const clear = (e) => {
    e.stopPropagation();
    onChange?.("");
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          ref={triggerRef}
          type="button"
          disabled={disabled}
          data-testid={`${testid}-trigger`}
          className={cn(
            "w-full h-10 px-3 rounded-md bg-zinc-900/60 border border-zinc-700 text-white text-sm text-left flex items-center gap-2 hover:border-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed transition",
            className
          )}
        >
          <span className={cn("flex-1 truncate", !currentLabel && "text-zinc-500")}>
            {currentLabel || placeholder}
          </span>
          {value && !disabled && (
            <span
              role="button"
              tabIndex={-1}
              onClick={clear}
              onKeyDown={(e) => { if (e.key === "Enter") clear(e); }}
              className="text-zinc-500 hover:text-red-400 shrink-0"
              data-testid={`${testid}-clear`}
              aria-label="Clear"
            >
              <X size={14} />
            </span>
          )}
          <ChevronsUpDown size={14} className="text-zinc-500 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="p-0 w-[min(90vw,380px)] bg-zinc-950 border-zinc-700"
        align="start"
        sideOffset={4}
      >
        <Command shouldFilter={false} className="bg-zinc-950">
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={placeholder}
            className="text-white"
            data-testid={`${testid}-input`}
          />
          <CommandList className="max-h-72">
            {filtered.length === 0 && !showCustomRow && (
              <CommandEmpty className="text-zinc-500 text-xs py-6 text-center">
                {emptyText}
              </CommandEmpty>
            )}
            {filtered.length > 0 && (
              <CommandGroup>
                {filtered.slice(0, 200).map((o) => {
                  const isActive = norm(o.value) === norm(value);
                  return (
                    <CommandItem
                      key={o.value}
                      value={o.value}
                      onSelect={() => pick(o.value)}
                      className="text-zinc-200 aria-selected:bg-blue-500/20 aria-selected:text-white cursor-pointer"
                      data-testid={`${testid}-item-${o.value}`}
                    >
                      <Check
                        size={14}
                        className={cn("mr-2 shrink-0", isActive ? "text-emerald-400" : "opacity-0")}
                      />
                      <span className="flex-1 truncate">{o.label}</span>
                      {o.hint && (
                        <span className="text-[10px] text-zinc-500 ml-2 shrink-0">{o.hint}</span>
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}
            {showCustomRow && (
              <CommandGroup heading="Custom">
                <CommandItem
                  value={`__custom__${trimmedQuery}`}
                  onSelect={() => pick(trimmedQuery)}
                  className="text-amber-200 aria-selected:bg-amber-500/15 cursor-pointer"
                  data-testid={`${testid}-item-custom`}
                >
                  <TypeIcon size={14} className="mr-2 text-amber-300 shrink-0" />
                  <span className="flex-1 truncate">
                    Use custom: <b className="font-mono text-white">{trimmedQuery}</b>
                  </span>
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
