import { PanelLeftOpen } from "lucide-react";
import { IconButton, RightInspector, useI18n } from "@unfour/ui";
import type { WorkspaceTab } from "@unfour/command-client";
import { moduleLabel } from "./module-helpers";

export function RightInspectorPlaceholder({
  activeTab,
  collapsed,
  onCollapse,
  onWidthChange,
  width,
}: {
  activeTab: WorkspaceTab;
  collapsed: boolean;
  onCollapse: () => void;
  onWidthChange: (width: number) => void;
  width: number;
}) {
  const { t } = useI18n();
  const activeModuleLabel = moduleLabel(activeTab, t);

  return (
    <RightInspector
      collapsed={collapsed}
      onWidthChange={onWidthChange}
      resizable
      width={width}
    >
      <div className="flex h-[var(--u-size-section-toolbar)] items-center justify-between border-b border-[var(--u-color-border)] px-2">
        <div className="text-[12px] font-semibold text-[var(--u-color-text)]">
          {t("app.inspector.title")}
        </div>
        <IconButton label={t("app.inspector.collapse")} onClick={onCollapse}>
          <PanelLeftOpen size={14} />
        </IconButton>
      </div>
      <div className="p-2 text-[12px] text-[var(--u-color-text-muted)]">
        {t("app.inspector.description", { module: activeModuleLabel })}
      </div>
    </RightInspector>
  );
}
