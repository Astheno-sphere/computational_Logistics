import * as React from "react";

export function CommandPaletteAction({
  children,
  onSelect,
}: {
  children: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <button
      className="flex h-[var(--u-size-sidebar-row)] w-full items-center rounded-[var(--u-radius-sm)] px-2 text-left text-[13px] text-[var(--u-color-text-muted)] hover:bg-[var(--u-color-surface-hover)] hover:text-[var(--u-color-text)]"
      onClick={onSelect}
      type="button"
    >
      {children}
    </button>
  );
}
