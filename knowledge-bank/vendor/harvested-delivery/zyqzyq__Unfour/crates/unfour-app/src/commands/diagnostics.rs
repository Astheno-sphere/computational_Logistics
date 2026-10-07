use crate::AppState;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};
use tauri_plugin_opener::OpenerExt;
use unfour_core::{models::SystemHealth, AppResult};

use super::trace_command;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticBundleCommandResult {
    pub bundle_dir: String,
    pub manifest_path: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FrontendLogEntry {
    pub level: String,
    pub event: String,
    pub module: String,
    pub operation: String,
    pub fields: serde_json::Value,
}

#[tauri::command]
pub async fn system_health(state: State<'_, AppState>) -> AppResult<SystemHealth> {
    trace_command("system_health", state.command_bus.system_health()).await
}

#[tauri::command]
pub async fn open_log_dir(app: AppHandle) -> AppResult<()> {
    trace_command("open_log_dir", async move {
        let paths = unfour_paths::initialize_unfour_storage()?;
        app.opener()
            .open_path(paths.logs_dir.to_string_lossy().to_string(), None::<&str>)
            .map_err(|error| {
                unfour_core::AppError::Config(format!("failed to open log directory: {error}"))
            })?;
        Ok(())
    })
    .await
}

#[tauri::command]
pub async fn open_diagnostics_dir(app: AppHandle) -> AppResult<()> {
    trace_command("open_diagnostics_dir", async move {
        let paths = unfour_paths::initialize_unfour_storage()?;
        app.opener()
            .open_path(
                paths.diagnostics_dir.to_string_lossy().to_string(),
                None::<&str>,
            )
            .map_err(|error| {
                unfour_core::AppError::Config(format!(
                    "failed to open diagnostics directory: {error}"
                ))
            })?;
        Ok(())
    })
    .await
}

#[tauri::command]
pub async fn export_diagnostics_bundle(
    state: State<'_, AppState>,
) -> AppResult<DiagnosticBundleCommandResult> {
    trace_command("export_diagnostics_bundle", async move {
        let paths = unfour_paths::initialize_unfour_storage()?;
        let request = crate::diagnostic_bundle_request(&state.config, paths);
        let bundle = unfour_diag::export_diagnostics_bundle(&request)?;

        Ok(DiagnosticBundleCommandResult {
            bundle_dir: bundle.bundle_dir.to_string_lossy().to_string(),
            manifest_path: bundle.manifest_path.to_string_lossy().to_string(),
        })
    })
    .await
}

#[tauri::command]
pub async fn frontend_log(entry: FrontendLogEntry) -> AppResult<()> {
    let status = if entry.level == "error" {
        "error"
    } else {
        "ok"
    };
    unfour_diag::log_operation_event(
        &entry.event,
        &entry.module,
        &entry.operation,
        status,
        None,
        None,
        entry.fields,
    );
    Ok(())
}
