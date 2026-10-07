import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { Badge, EmptyState, cn, useI18n } from "@unfour/ui";
import type {
  ScriptConsoleEntry,
  ScriptExecutionResult,
  ScriptTestResult,
} from "@unfour/command-client";

export function ScriptTestsView({
  post,
  pre,
}: {
  post: ScriptExecutionResult;
  pre: ScriptExecutionResult;
}) {
  const { t } = useI18n();
  const tests = [...phaseTests("pre", pre.tests), ...phaseTests("post", post.tests)];
  const passed = tests.filter((item) => item.test.passed).length;
  const failed = tests.length - passed;

  return (
    <div className="h-full overflow-auto p-3">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px]">
        <Badge tone="green">{t("api.scripts.testsPassed", { count: passed })}</Badge>
        <Badge tone={failed ? "red" : "neutral"}>
          {t("api.scripts.testsFailed", { count: failed })}
        </Badge>
        <span className="ml-auto font-mono text-[var(--u-color-text-soft)]">
          {t("api.scripts.executionTime", {
            pre: pre.durationMs,
            post: post.durationMs,
          })}
        </span>
      </div>
      <ScriptErrors post={post} pre={pre} />
      {!tests.length ? (
        <EmptyState className="h-32">{t("api.scripts.noTests")}</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-[var(--u-radius-sm)] border border-[var(--u-color-border)]">
          {tests.map(({ phase, test }, index) => (
            <div
              className="grid min-h-[var(--u-size-table-row)] grid-cols-[18px_minmax(0,1fr)_auto] items-start gap-2 border-b border-[var(--u-color-border)] px-2 py-1.5 last:border-b-0"
              key={`${phase}-${test.name}-${index}`}
            >
              {test.passed ? (
                <CheckCircle2 className="mt-0.5 text-[var(--u-color-success)]" size={14} />
              ) : (
                <XCircle className="mt-0.5 text-[var(--u-color-danger)]" size={14} />
              )}
              <div className="min-w-0">
                <div className="break-words text-[12px] text-[var(--u-color-text)]">
                  {test.name}
                </div>
                {test.errorMessage && (
                  <div className="mt-0.5 break-words font-mono text-[11px] text-[var(--u-color-danger)]">
                    {test.errorMessage}
                  </div>
                )}
              </div>
              <span className="font-mono text-[11px] text-[var(--u-color-text-soft)]">
                {test.durationMs}ms
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ScriptConsoleView({
  post,
  pre,
}: {
  post: ScriptExecutionResult;
  pre: ScriptExecutionResult;
}) {
  const { t } = useI18n();
  const entries = [...phaseLogs("pre", pre.console), ...phaseLogs("post", post.console)];
  return (
    <div className="h-full overflow-auto bg-[var(--u-color-bg)] p-3">
      <ScriptErrors post={post} pre={pre} />
      {!entries.length ? (
        <EmptyState className="h-32">{t("api.scripts.noConsole")}</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-[var(--u-radius-sm)] border border-[var(--u-color-border)] font-mono text-[12px]">
          {entries.map(({ entry, phase }, index) => (
            <div
              className="grid grid-cols-[42px_38px_minmax(0,1fr)] gap-2 border-b border-[var(--u-color-border)] px-2 py-1.5 last:border-b-0"
              key={`${phase}-${entry.sequence}-${index}`}
            >
              <span className="text-[10px] uppercase text-[var(--u-color-text-soft)]">
                {phase === "pre" ? t("api.scripts.preShort") : t("api.scripts.postShort")}
              </span>
              <span
                className={cn(
                  "text-[10px] uppercase",
                  entry.level === "error"
                    ? "text-[var(--u-color-danger)]"
                    : entry.level === "warn"
                      ? "text-[var(--u-color-warning)]"
                      : "text-[var(--u-color-text-soft)]",
                )}
              >
                {entry.level}
              </span>
              <span className="min-w-0 whitespace-pre-wrap break-words text-[var(--u-color-text-muted)]">
                {entry.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ScriptErrors({
  post,
  pre,
}: {
  post: ScriptExecutionResult;
  pre: ScriptExecutionResult;
}) {
  const { t } = useI18n();
  const errors = [
    { label: t("api.scripts.preRequest"), result: pre },
    { label: t("api.scripts.postResponse"), result: post },
  ].filter((item) => item.result.error);
  if (!errors.length) return null;
  return (
    <div className="mb-3 space-y-2">
      {errors.map(({ label, result }) => (
        <div
          className="flex gap-2 rounded-[var(--u-radius-sm)] border border-[color:color-mix(in_srgb,var(--u-color-danger)_45%,var(--u-color-border))] bg-[color:color-mix(in_srgb,var(--u-color-danger)_7%,var(--u-color-surface))] px-2 py-2"
          key={label}
        >
          <AlertCircle className="mt-0.5 shrink-0 text-[var(--u-color-danger)]" size={14} />
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-[var(--u-color-danger)]">
              {label} · {result.status === "timeout" ? t("api.scripts.timeout") : t("api.scripts.error")}
            </div>
            <div className="mt-0.5 break-words font-mono text-[11px] text-[var(--u-color-text-muted)]">
              {result.error?.message}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function phaseTests(phase: "pre" | "post", tests: ScriptTestResult[]) {
  return tests.map((test) => ({ phase, test }));
}

function phaseLogs(phase: "pre" | "post", console: ScriptConsoleEntry[]) {
  return console.map((entry) => ({ entry, phase }));
}
