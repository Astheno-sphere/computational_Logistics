import { Settings } from "lucide-react";
import type { Workspace, WorkspaceEnvironment } from "@unfour/command-client";
import { useState, type ReactNode } from "react";
import {
  GlobalToolbar,
  ActiveEnvironmentSelect,
  IconButton,
  useI18n,
} from "@unfour/ui";
import { SettingsDialog } from "./settings/SettingsDialog";
import { WindowControls } from "./WindowControls";
import { WorkspaceMenu } from "./WorkspaceMenu";
import type {
  DesktopAppExtensionContext,
  DesktopAppSettingsSection,
  DesktopAppWorkspaceAction,
  DesktopAppWorkspaceActionsProvider,
  DesktopAppWorkspaceDecoration,
  DesktopAppWorkspaceMenuFooterAction,
} from "../extensions";

export function AppTitleBar({
  activeWorkspace,
  activeEnvironmentId = null,
  environments = [],
  endAccessory,
  extensionContext,
  onActivateWorkspace,
  onManageVariables = () => {},
  onOpenEnvironmentMenu = () => {},
  onSelectEnvironment = () => {},
  settingsSections,
  workspaceActions,
  workspaceDecoration,
  workspaceMenuActions,
  workspaceMenuFooterActions,
  workspaces,
}: {
  activeWorkspace?: Workspace;
  activeEnvironmentId?: string | null;
  environments?: WorkspaceEnvironment[];
  endAccessory?: ReactNode;
  extensionContext: DesktopAppExtensionContext;
  onActivateWorkspace: (workspaceId: string) => void;
  onManageVariables?: () => void;
  onOpenEnvironmentMenu?: () => void;
  onSelectEnvironment?: (environmentId: string | null) => void;
  settingsSections?: readonly DesktopAppSettingsSection[];
  workspaceActions?: readonly DesktopAppWorkspaceAction[];
  workspaceDecoration?: DesktopAppWorkspaceDecoration;
  workspaceMenuActions?: DesktopAppWorkspaceActionsProvider;
  workspaceMenuFooterActions?: readonly DesktopAppWorkspaceMenuFooterAction[];
  workspaces: Workspace[];
}) {
  const { t } = useI18n();
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <GlobalToolbar
        left={
          <div className="flex min-w-0 items-center gap-1">
            <WorkspaceMenu
              activeWorkspace={activeWorkspace}
              decoration={workspaceDecoration}
              extensionContext={extensionContext}
              onActivateWorkspace={onActivateWorkspace}
              workspaceActionProvider={workspaceMenuActions}
              workspaceActions={workspaceActions}
              workspaceMenuFooterActions={workspaceMenuFooterActions}
              workspaces={workspaces}
            />
            <ActiveEnvironmentSelect
              activeEnvironmentId={activeEnvironmentId}
              environments={environments}
              onManage={onManageVariables}
              onOpenChange={(open) => open && onOpenEnvironmentMenu()}
              onSelect={onSelectEnvironment}
            />
          </div>
        }
        right={
          <>
            <IconButton label={t("app.titlebar.settings")} onClick={() => setSettingsOpen(true)}>
              <Settings size={15} />
            </IconButton>
            {endAccessory}
            <WindowControls />
          </>
        }
      />
      <SettingsDialog
        extensionContext={extensionContext}
        extensionSections={settingsSections}
        onOpenChange={setSettingsOpen}
        open={settingsOpen}
      />
    </>
  );
}
