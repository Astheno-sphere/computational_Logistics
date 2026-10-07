import type { SshConnection, SshTaskDetail } from "@unfour/command-client";
import {
  Badge,
  Button,
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  useI18n,
} from "@unfour/ui";
import { detectTaskInputs } from "../model/task-template";

export function TaskRunDialog({
  activeEnvironmentName,
  connectionId,
  connections,
  environmentId,
  environmentLoadFailed,
  environments,
  error,
  filledFromWorkspace,
  inputValues,
  onConnectionChange,
  onEnvironmentChange,
  onInputChange,
  onOpenChange,
  onRun,
  open,
  pending,
  secretInputNames,
  task,
}: {
  activeEnvironmentName: string | null;
  connectionId: string;
  connections: SshConnection[];
  environmentId: string;
  environmentLoadFailed: boolean;
  environments: Array<{ id: string; name: string }>;
  error: Error | null;
  filledFromWorkspace: boolean;
  inputValues: Record<string, string>;
  onConnectionChange: (connectionId: string) => void;
  onEnvironmentChange: (environmentId: string) => void;
  onInputChange: (name: string, value: string) => void;
  onOpenChange: (open: boolean) => void;
  onRun: () => void;
  open: boolean;
  pending: boolean;
  secretInputNames: string[];
  task: SshTaskDetail | null;
}) {
  const { t } = useI18n();
  const detectedInputs = task ? detectTaskInputs(task.steps, true) : [];
  const connection = connections.find((item) => item.id === connectionId) ?? null;
  const missing = detectedInputs.some((name) => !inputValues[name]?.trim());
  const canRun = Boolean(task && connection && !missing && task.steps.some((step) => step.enabled));
  const title = t("ssh.tasks.run.title");
  const secretNames = new Set(secretInputNames);

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="w-[min(680px,calc(100vw-32px))]" title={title}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <DialogBody className="max-h-[70vh] overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <Summary label={t("ssh.tasks.run.taskName")} value={task?.task.name ?? "—"} />
              <Summary label={t("ssh.tasks.run.host")} value={connection ? `${connection.username}@${connection.host}:${connection.port}` : "—"} />
            </div>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--u-color-text-muted)]">
                {t("ssh.tasks.run.connection")}
              </span>
              <Select onChange={(event) => onConnectionChange(event.target.value)} value={connectionId}>
                <option value="">{t("ssh.tasks.run.selectConnection")}</option>
                {connections.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.host}
                  </option>
                ))}
              </Select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[var(--u-color-text-muted)]">
                {t("ssh.tasks.run.environment")}
              </span>
              <Select
                onChange={(event) => onEnvironmentChange(event.target.value)}
                value={environmentId}
              >
                <option value="">{t("ssh.tasks.run.workspaceOnly")}</option>
                {environments.map((environment) => (
                  <option key={environment.id} value={environment.id}>
                    {environment.name}
                  </option>
                ))}
              </Select>
            </label>
            {environmentLoadFailed && (
              <p className="text-[12px] text-[var(--u-color-warning)]" role="alert">
                {t("ssh.tasks.run.environmentLoadFailed")}
              </p>
            )}

            <section>
              <h3 className="mb-2 text-[12px] font-semibold text-[var(--u-color-text)]">
                {t("ssh.tasks.run.inputs")}
              </h3>
              {filledFromWorkspace && (
                <p className="mb-2 text-[11px] text-[var(--u-color-text-muted)]">
                  {activeEnvironmentName
                    ? t("ssh.tasks.run.workspaceDefaultsWithEnv", {
                        name: activeEnvironmentName,
                      })
                    : t("ssh.tasks.run.workspaceDefaults")}
                </p>
              )}
              {detectedInputs.length ? (
                <div className="grid grid-cols-2 gap-2">
                  {detectedInputs.map((name, index) => (
                    <label className="flex flex-col gap-1" key={name}>
                      <span className="font-mono text-[11px] text-[var(--u-color-text-muted)]">{name}</span>
                      <Input
                        autoFocus={index === 0}
                        onChange={(event) => onInputChange(name, event.target.value)}
                        type={secretNames.has(name) ? "password" : "text"}
                        value={inputValues[name] ?? ""}
                      />
                    </label>
                  ))}
                </div>
              ) : (
                <p className="text-[12px] text-[var(--u-color-text-muted)]">
                  {t("ssh.tasks.run.noInputs")}
                </p>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-[12px] font-semibold text-[var(--u-color-text)]">
                {t("ssh.tasks.run.steps")}
              </h3>
              <ol className="divide-y divide-[var(--u-color-border)] border border-[var(--u-color-border)]">
                {task?.steps.map((step) => (
                  <li className="flex h-8 items-center gap-2 px-2 text-[12px]" key={step.id}>
                    <span className="w-5 text-right font-mono text-[var(--u-color-text-soft)]">{step.position + 1}</span>
                    <Badge>{t(`ssh.tasks.stepTypes.${step.stepType}`)}</Badge>
                    <span className="min-w-0 flex-1 truncate text-[var(--u-color-text)]">{step.name}</span>
                    {!step.enabled && <span className="text-[var(--u-color-text-soft)]">{t("ssh.tasks.run.disabled")}</span>}
                  </li>
                ))}
              </ol>
            </section>
            {missing && (
              <p className="text-[12px] text-[var(--u-color-danger)]" role="alert">
                {t("ssh.tasks.run.missingInputs")}
              </p>
            )}
            {error && (
              <p className="whitespace-pre-wrap text-[12px] text-[var(--u-color-danger)]" role="alert">
                {error.message}
              </p>
            )}
          </div>
        </DialogBody>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="secondary">
              {t("ssh.tasks.actions.cancel")}
            </Button>
          </DialogClose>
          <Button disabled={!canRun || pending} onClick={onRun} type="button">
            {pending ? t("ssh.tasks.run.starting") : t("ssh.tasks.actions.run")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-[11px] text-[var(--u-color-text-muted)]">{label}</span>
      <span className="mt-0.5 block truncate text-[var(--u-color-text)]">{value}</span>
    </div>
  );
}
