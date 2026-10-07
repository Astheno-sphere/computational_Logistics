import * as React from "react";
import { cn } from "./utils";

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "green" | "amber" | "red" | "teal";
};

const toneClass: Record<NonNullable<BadgeProps["tone"]>, string> = {
  amber: "bg-[var(--u-badge-warning-bg)] text-[var(--u-badge-warning-text)] ring-[var(--u-badge-warning-ring)]",
  green: "bg-[var(--u-badge-success-bg)] text-[var(--u-badge-success-text)] ring-[var(--u-badge-success-ring)]",
  neutral: "bg-[var(--u-badge-neutral-bg)] text-[var(--u-badge-neutral-text)] ring-[var(--u-badge-neutral-ring)]",
  red: "bg-[var(--u-badge-danger-bg)] text-[var(--u-badge-danger-text)] ring-[var(--u-badge-danger-ring)]",
  teal: "bg-[var(--u-badge-info-bg)] text-[var(--u-badge-info-text)] ring-[var(--u-badge-info-ring)]",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium leading-5 ring-1 ring-inset",
        toneClass[tone],
        className,
      )}
      {...props}
    />
  );
}
