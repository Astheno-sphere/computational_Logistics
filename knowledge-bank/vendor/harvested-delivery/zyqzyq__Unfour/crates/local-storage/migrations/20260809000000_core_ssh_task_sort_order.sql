-- Preserve the existing updated-at task order as the initial manual order.
-- Future task saves keep this position stable; explicit reorder commands update it.

ALTER TABLE ssh_task
ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;

WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY workspace_id
      ORDER BY updated_at DESC, name COLLATE NOCASE, id
    ) - 1 AS position
  FROM ssh_task
)
UPDATE ssh_task
SET sort_order = (
  SELECT ranked.position
  FROM ranked
  WHERE ranked.id = ssh_task.id
);

CREATE INDEX IF NOT EXISTS idx_ssh_task_workspace_sort
ON ssh_task(workspace_id, deleted_at, sort_order, name COLLATE NOCASE, id);
