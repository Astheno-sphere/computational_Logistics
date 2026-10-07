use unfour_core::{AppError, AppResult};

pub(crate) fn empty_to_none(value: Option<String>) -> Option<String> {
    value
        .map(|item| item.trim().to_string())
        .filter(|item| !item.is_empty())
}

pub(crate) fn validate_workspace_id(workspace_id: &str) -> AppResult<()> {
    if workspace_id.trim().is_empty() {
        return Err(AppError::Validation(
            "workspace id cannot be empty".to_string(),
        ));
    }
    Ok(())
}

pub(crate) fn validate_connection_id(connection_id: &str) -> AppResult<()> {
    if connection_id.trim().is_empty() {
        return Err(AppError::Validation(
            "ssh connection id cannot be empty".to_string(),
        ));
    }
    Ok(())
}

pub(crate) fn validate_session_id(session_id: &str) -> AppResult<()> {
    if session_id.trim().is_empty() {
        return Err(AppError::Validation(
            "ssh session id cannot be empty".to_string(),
        ));
    }
    Ok(())
}

pub(crate) fn validate_pty_size(cols: u16, rows: u16) -> AppResult<()> {
    if !(20..=300).contains(&cols) || !(8..=100).contains(&rows) {
        return Err(AppError::Validation(
            "ssh pty size must be between 20x8 and 300x100".to_string(),
        ));
    }
    Ok(())
}
