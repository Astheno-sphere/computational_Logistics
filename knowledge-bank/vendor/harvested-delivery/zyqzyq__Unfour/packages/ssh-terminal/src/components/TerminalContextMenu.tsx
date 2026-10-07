import { useState, type ReactNode, type RefObject } from "react";
import type { Terminal as XTerm } from "@xterm/xterm";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
  useFeedbackErrorHandler,
  useI18n,
  usePlatform,
} from "@unfour/ui";

export function TerminalContextMenu({
  canPaste,
  children,
  terminalRef,
}: {
  canPaste: boolean;
  children: ReactNode;
  terminalRef: RefObject<XTerm | null>;
}) {
  const [hasSelection, setHasSelection] = useState(false);
  const handleError = useFeedbackErrorHandler();
  const { t } = useI18n();
  const platform = usePlatform();
  const copyShortcut = platform === "macos" ? "⌘C" : "Ctrl+Shift+C";
  const pasteShortcut = platform === "macos" ? "⌘V" : "Ctrl+V";
  const hasClipboard = typeof navigator !== "undefined" && Boolean(navigator.clipboard);

  function copySelection() {
    const selection = terminalRef.current?.getSelection() ?? "";
    if (!selection || !navigator.clipboard) {
      return;
    }
    void navigator.clipboard
      .writeText(selection)
      .catch((error) => handleError(error, { key: "feedback.ssh.clipboardWriteFailed" }));
  }

  function pasteSelection() {
    const selection = terminalRef.current?.getSelection() ?? "";
    if (!canPaste || !selection) {
      return;
    }
    terminalRef.current?.paste(selection);
  }

  function pasteClipboard() {
    if (!canPaste || !navigator.clipboard) {
      return;
    }
    void navigator.clipboard
      .readText()
      .then((text) => {
        if (text) {
          terminalRef.current?.paste(text);
        }
      })
      .catch((error) => handleError(error, { key: "feedback.ssh.clipboardReadFailed" }));
  }

  return (
    <ContextMenu
      onOpenChange={(open) => {
        if (open) {
          setHasSelection(Boolean(terminalRef.current?.hasSelection()));
        } else {
          window.requestAnimationFrame(() => terminalRef.current?.focus());
        }
      }}
    >
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem
          disabled={!hasSelection || !hasClipboard}
          onSelect={copySelection}
          shortcut={copyShortcut}
        >
          {t("ssh.actions.copySelection")}
        </ContextMenuItem>
        <ContextMenuItem
          disabled={!canPaste || !hasSelection}
          onSelect={pasteSelection}
        >
          {t("ssh.actions.pasteSelection")}
        </ContextMenuItem>
        <ContextMenuItem
          disabled={!canPaste || !hasClipboard}
          onSelect={pasteClipboard}
          shortcut={pasteShortcut}
        >
          {t("ssh.actions.pasteClipboard")}
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuItem onSelect={() => terminalRef.current?.selectAll()}>
          {t("ssh.actions.selectAll")}
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
