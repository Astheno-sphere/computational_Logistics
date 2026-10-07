import * as React from "react";
import { cn } from "./utils";

export type SegmentedControlOption<T extends string> = {
  icon?: React.ReactNode;
  label: React.ReactNode;
  value: T;
};

/**
 * Compact segmented (toggle group) control. Use for small, mutually-exclusive
 * choices where a dropdown would be heavier than warranted (e.g. auth kind).
 */
export function SegmentedControl<T extends string>({
  className,
  onChange,
  options,
  value,
}: {
  className?: string;
  onChange: (value: T) => void;
  options: SegmentedControlOption<T>[];
  value: T;
}) {
  return (
    <div
      className={cn(
        "flex overflow-hidden rounded-[var(--u-radius-md)] border border-[var(--u-color-input)] bg-[var(--u-color-bg)]",
        className,
      )}
      role="radiogroup"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            aria-checked={selected}
            className={cn(
              "flex h-[var(--u-size-input)] flex-1 items-center justify-center gap-1.5 text-[12px] font-semibold transition-colors first:border-l-0 [&+button]:border-l [&+button]:border-[var(--u-color-input)]",
              selected
                ? "bg-[var(--u-color-primary-soft)] text-[var(--u-color-primary)]"
                : "text-[var(--u-color-text-muted)] hover:bg-[var(--u-color-surface-hover)] hover:text-[var(--u-color-text)]",
            )}
            key={option.value}
            onClick={() => !selected && onChange(option.value)}
            role="radio"
            type="button"
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
