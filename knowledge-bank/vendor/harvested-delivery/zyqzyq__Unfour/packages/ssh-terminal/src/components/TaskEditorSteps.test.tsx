// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SshTaskStepInput } from "@unfour/command-client";
import { StepRow } from "./TaskEditorSteps";

vi.mock("@unfour/ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@unfour/ui")>();
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key }),
  };
});

afterEach(cleanup);

describe("StepRow keyboard editing", () => {
  it("does not toggle the step when spaces are typed in text editors", () => {
    const onToggleExpand = vi.fn();
    renderStep({ expanded: true, onToggleExpand });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "ssh.tasks.editor.stepName" }), {
      key: " ",
    });
    fireEvent.keyDown(screen.getByRole("textbox", { name: "ssh.tasks.editor.command" }), {
      key: " ",
    });

    expect(onToggleExpand).not.toHaveBeenCalled();
  });

  it("keeps keyboard toggling available from the step header", () => {
    const onToggleExpand = vi.fn();
    renderStep({ expanded: false, onToggleExpand });

    const header = screen
      .getByText("ssh.tasks.stepTypes.command")
      .closest('[role="button"]');
    expect(header).not.toBeNull();

    fireEvent.keyDown(header!, { key: "Enter" });

    expect(onToggleExpand).toHaveBeenCalledOnce();
  });
});

function renderStep({
  expanded,
  onToggleExpand,
}: {
  expanded: boolean;
  onToggleExpand: () => void;
}) {
  const step: SshTaskStepInput = {
    name: "Run command",
    stepType: "command",
    position: 0,
    enabled: true,
    configVersion: 1,
    configJson: {
      command: "echo hello",
      workingDirectory: "",
      timeoutSeconds: 300,
      continueOnError: false,
    },
  };

  return render(
    <StepRow
      advancedOpen={false}
      dragOver={false}
      dragging={false}
      expanded={expanded}
      index={0}
      onConfigChange={vi.fn()}
      onDragHandlePointerDown={vi.fn()}
      onDuplicate={vi.fn()}
      onMove={vi.fn()}
      onRemove={vi.fn()}
      onToggleAdvanced={vi.fn()}
      onToggleExpand={onToggleExpand}
      onUpdate={vi.fn()}
      step={step}
      stepCount={1}
    />,
  );
}
