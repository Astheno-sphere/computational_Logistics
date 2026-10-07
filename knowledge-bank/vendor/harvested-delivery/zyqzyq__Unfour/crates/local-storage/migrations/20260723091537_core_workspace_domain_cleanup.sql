-- The normalized workspace entity tables no longer use embedded transport
-- metadata. Their stable ids and local revisions remain intact.
ALTER TABLE workspace_variables DROP COLUMN sync_status;
ALTER TABLE workspace_variables DROP COLUMN remote_id;

ALTER TABLE workspace_environments DROP COLUMN sync_status;
ALTER TABLE workspace_environments DROP COLUMN remote_id;

ALTER TABLE workspace_environment_variables DROP COLUMN sync_status;
ALTER TABLE workspace_environment_variables DROP COLUMN remote_id;

-- workspaces.sync_status and workspaces.remote_id are intentionally retained
-- as inert compatibility columns for this phase. Rebuilding the highly
-- referenced parent table would be materially riskier for existing databases;
-- current Core models and write paths no longer read or write either column.
