import { Button, useI18n } from "@unfour/ui";
import { Plus, Workflow } from "lucide-react";

export function TaskWorkspaceEmpty({
  hasTasks,
  loading,
  onExample,
  onNew,
}: {
  hasTasks: boolean;
  loading?: boolean;
  onExample: () => void;
  onNew: () => void;
}) {
  const { t } = useI18n();

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-[12px] text-[var(--u-color-text-muted)]">
        {t("ssh.tasks.list.loading")}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <Workflow className="text-[var(--u-color-text-soft)]" size={28} />
      <div className="max-w-[360px]">
        <p className="text-[13px] font-medium text-[var(--u-color-text)]">
          {hasTasks ? t("ssh.tasks.list.selectTitle") : t("ssh.tasks.list.emptyTitle")}
        </p>
        <p className="mt-1 text-[12px] text-[var(--u-color-text-muted)]">
          {hasTasks
            ? t("ssh.tasks.list.selectTask")
            : t("ssh.tasks.list.emptyDescription")}
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button onClick={onNew} size="sm">
          <Plus size={13} />
          {t("ssh.tasks.actions.new")}
        </Button>
        {!hasTasks ? (
          <Button onClick={onExample} size="sm" variant="secondary">
            {t("ssh.tasks.actions.dockerExample")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
