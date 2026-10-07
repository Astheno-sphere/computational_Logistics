-- Add request-level pre-request and post-response scripts. Empty scripts stay
-- nullable so existing requests retain their previous send behavior. The
-- schema version is stable syncable business data reserved for future script
-- model upgrades.

ALTER TABLE api_requests ADD COLUMN pre_request_script TEXT;
ALTER TABLE api_requests ADD COLUMN post_response_script TEXT;
ALTER TABLE api_requests
  ADD COLUMN script_schema_version INTEGER NOT NULL DEFAULT 1
  CHECK (script_schema_version >= 1);
