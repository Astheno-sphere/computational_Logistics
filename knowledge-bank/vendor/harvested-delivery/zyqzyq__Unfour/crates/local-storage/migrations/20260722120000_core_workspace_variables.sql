-- Promote API-owned environment JSON into workspace-scoped, normalized
-- variables and environments. The legacy api_environments table remains in
-- place so already-applied databases and older binaries keep a readable
-- compatibility source; current code reads and writes the new tables.

CREATE TABLE IF NOT EXISTS workspace_variables (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL DEFAULT '',
  is_secret INTEGER NOT NULL DEFAULT 0 CHECK (is_secret IN (0, 1)),
  is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
  description TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  sync_status TEXT NOT NULL DEFAULT 'local',
  remote_id TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_environments (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  sync_status TEXT NOT NULL DEFAULT 'local',
  remote_id TEXT,
  UNIQUE(workspace_id, id),
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_environment_variables (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL DEFAULT '',
  is_secret INTEGER NOT NULL DEFAULT 0 CHECK (is_secret IN (0, 1)),
  is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
  description TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  sync_status TEXT NOT NULL DEFAULT 'local',
  remote_id TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY(workspace_id, environment_id)
    REFERENCES workspace_environments(workspace_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_local_state (
  workspace_id TEXT PRIMARY KEY,
  active_environment_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_variables_key
ON workspace_variables(workspace_id, key)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_variables_workspace
ON workspace_variables(workspace_id, deleted_at, sort_order, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_environments_name
ON workspace_environments(workspace_id, name COLLATE NOCASE)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_environments_workspace
ON workspace_environments(workspace_id, deleted_at, sort_order, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_environment_variables_key
ON workspace_environment_variables(environment_id, key)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_environment_variables_environment
ON workspace_environment_variables(workspace_id, environment_id, deleted_at, sort_order, created_at);

-- Preserve the legacy environment identity and lifecycle metadata.
INSERT OR IGNORE INTO workspace_environments (
  id, workspace_id, name, sort_order, created_at, updated_at, deleted_at,
  revision, sync_status, remote_id
)
SELECT
  id,
  workspace_id,
  name,
  ROW_NUMBER() OVER (
    PARTITION BY workspace_id
    ORDER BY created_at ASC, id ASC
  ) - 1,
  created_at,
  updated_at,
  deleted_at,
  revision,
  sync_status,
  remote_id
FROM api_environments;

-- Split each legacy variables_json array into normalized rows. Existing
-- variables did not carry secret or description metadata, so those fields use
-- their neutral defaults. A valid enabled duplicate is preferred as the
-- canonical key; blank or remaining duplicate rows receive disabled migration
-- keys so their values are retained without changing request resolution.
WITH legacy_variables AS (
  SELECT
    environment.id AS environment_id,
    environment.workspace_id,
    TRIM(COALESCE(json_extract(variable.value, '$.key'), '')) AS original_key,
    COALESCE(json_extract(variable.value, '$.value'), '') AS original_value,
    CASE COALESCE(json_extract(variable.value, '$.enabled'), 1)
      WHEN 0 THEN 0 ELSE 1
    END AS original_enabled,
    CAST(variable.key AS INTEGER) AS original_sort_order,
    environment.created_at,
    environment.updated_at,
    environment.revision,
    environment.sync_status
  FROM api_environments AS environment,
  json_each(
    CASE
      WHEN json_valid(environment.variables_json) THEN environment.variables_json
      ELSE '[]'
    END
  ) AS variable
),
ranked_variables AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY environment_id, original_key
      ORDER BY original_enabled DESC, original_sort_order ASC
    ) AS key_rank
  FROM legacy_variables
)
INSERT OR IGNORE INTO workspace_environment_variables (
  id, workspace_id, environment_id, key, value, is_secret, is_enabled,
  description, sort_order, created_at, updated_at, revision, sync_status
)
SELECT
  environment_id || ':variable:' || printf('%06d', original_sort_order),
  workspace_id,
  environment_id,
  CASE
    WHEN original_key = '' OR key_rank > 1 THEN
      '__UNFOUR_MIGRATED_' || replace(environment_id, '-', '_') || '_' ||
      printf('%06d', original_sort_order)
    ELSE original_key
  END,
  original_value,
  0,
  CASE
    WHEN original_key = '' OR key_rank > 1 THEN 0
    ELSE original_enabled
  END,
  NULL,
  original_sort_order,
  created_at,
  updated_at,
  revision,
  sync_status
FROM ranked_variables;

-- Move the legacy active flag into local workspace state. If malformed legacy
-- data contains more than one active row, the oldest environment wins.
INSERT OR IGNORE INTO workspace_local_state (
  workspace_id, active_environment_id, created_at, updated_at
)
SELECT
  workspace.id,
  (
  SELECT environment.id
  FROM api_environments AS environment
  WHERE environment.workspace_id = workspace.id
    AND environment.is_active = 1
    AND environment.deleted_at IS NULL
  ORDER BY environment.created_at ASC, environment.id ASC
  LIMIT 1
  ),
  workspace.created_at,
  workspace.updated_at
FROM workspaces AS workspace;

-- SQLite cannot add a composite foreign key to an existing table. These
-- triggers enforce the equivalent workspace ownership invariant for the local
-- active environment selection.
CREATE TRIGGER IF NOT EXISTS trg_workspace_local_state_active_environment_insert
BEFORE INSERT ON workspace_local_state
WHEN NEW.active_environment_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM workspace_environments
    WHERE id = NEW.active_environment_id
      AND workspace_id = NEW.workspace_id
      AND deleted_at IS NULL
  )
BEGIN
  SELECT RAISE(ABORT, 'active environment must belong to the same workspace');
END;

CREATE TRIGGER IF NOT EXISTS trg_workspace_local_state_active_environment_update
BEFORE UPDATE OF workspace_id, active_environment_id ON workspace_local_state
WHEN NEW.active_environment_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM workspace_environments
    WHERE id = NEW.active_environment_id
      AND workspace_id = NEW.workspace_id
      AND deleted_at IS NULL
  )
BEGIN
  SELECT RAISE(ABORT, 'active environment must belong to the same workspace');
END;
