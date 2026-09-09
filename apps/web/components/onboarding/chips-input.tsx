"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// Editable list-of-strings as removable chips, with optional one-click AI suggestions.
export function ChipsInput({
  value,
  onChange,
  placeholder,
  prefix,
  suggestions = [],
  mono,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  prefix?: string; // e.g. "@" for handles
  suggestions?: string[];
  mono?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const norm = (s: string) => s.trim().replace(/^@/, "");
  const has = (s: string) => value.some((v) => v.toLowerCase() === s.toLowerCase());

  const add = (raw: string) => {
    const v = norm(raw);
    if (v && !has(v)) onChange([...value, v]);
    setDraft("");
  };
  const remove = (v: string) => onChange(value.filter((x) => x !== v));

  const open = suggestions.filter((s) => !has(norm(s)));

  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          "border-input bg-background/40 flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border px-2 py-1.5",
          "focus-within:border-ring focus-within:ring-ring/30 focus-within:ring-[3px] transition-shadow",
        )}
      >
        {value.map((v) => (
          <span
            key={v}
            className={cn(
              "bg-secondary text-secondary-foreground group inline-flex items-center gap-1 rounded-md py-0.5 pl-2 pr-1 text-xs font-medium",
              mono && "font-mono",
            )}
          >
            {prefix}
            {v}
            <button
              type="button"
              onClick={() => remove(v)}
              className="hover:bg-foreground/10 rounded p-0.5 opacity-60 transition-opacity group-hover:opacity-100"
              aria-label={`Remove ${v}`}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && value.length) {
              remove(value[value.length - 1]!);
            }
          }}
          onBlur={() => draft && add(draft)}
          placeholder={value.length ? "" : placeholder}
          className={cn("min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground", mono && "font-mono")}
        />
      </div>

      {open.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground text-[11px] font-medium">Suggested:</span>
          {open.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="border-input text-muted-foreground hover:border-ring hover:text-foreground inline-flex items-center gap-1 rounded-md border border-dashed px-2 py-0.5 text-xs transition-colors"
            >
              <Plus className="size-3" />
              {prefix}
              {norm(s)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
