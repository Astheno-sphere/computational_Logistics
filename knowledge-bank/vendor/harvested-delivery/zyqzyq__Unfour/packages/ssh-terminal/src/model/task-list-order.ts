import type { SshTask } from "@unfour/command-client";

export type TaskSortMode = "manual" | "name" | "updated";

export function sortTasksForView(tasks: SshTask[], mode: TaskSortMode): SshTask[] {
  const sorted = tasks.slice();
  if (mode === "name") {
    return sorted.sort((left, right) =>
      left.name.localeCompare(right.name, undefined, { sensitivity: "base", numeric: true }),
    );
  }
  if (mode === "updated") {
    return sorted.sort(
      (left, right) =>
        right.updatedAt.localeCompare(left.updatedAt) ||
        left.name.localeCompare(right.name, undefined, { sensitivity: "base" }),
    );
  }
  return sorted.sort(
    (left, right) =>
      left.sortOrder - right.sortOrder ||
      left.name.localeCompare(right.name, undefined, { sensitivity: "base" }) ||
      left.id.localeCompare(right.id),
  );
}

export function reorderTaskIds(
  taskIds: string[],
  sourceId: string,
  targetId: string,
  position: "before" | "after",
): string[] {
  if (sourceId === targetId) return taskIds;
  const next = taskIds.filter((taskId) => taskId !== sourceId);
  const targetIndex = next.indexOf(targetId);
  if (targetIndex < 0 || next.length === taskIds.length) return taskIds;
  next.splice(position === "before" ? targetIndex : targetIndex + 1, 0, sourceId);
  return next;
}
