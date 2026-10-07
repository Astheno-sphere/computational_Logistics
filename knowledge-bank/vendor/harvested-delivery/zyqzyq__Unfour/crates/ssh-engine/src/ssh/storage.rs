use super::*;

pub(super) fn stored_to_ssh_connection(row: StoredSshConnection) -> AppResult<SshConnection> {
    let config = parse_ssh_config(&row.id, &row.config_json)?;
    let port = decode_ssh_port(row.port)?;
    Ok(SshConnection {
        id: row.id,
        workspace_id: row.workspace_id,
        name: row.name,
        host: row.host,
        port,
        username: row.username,
        auth_kind: row.auth_method,
        key_path: config.key_path,
        credential_ref: row.credential_ref,
        created_at: row.created_at,
        updated_at: row.updated_at,
        deleted_at: row.deleted_at,
        revision: row.revision,
        sync_status: row.sync_status,
        remote_id: row.remote_id,
    })
}

pub(super) fn input_to_storage(input: &SshConnectionInput) -> AppResult<SshConnectionStorageInput> {
    let host = normalize_required(&input.host, "ssh host")?;
    let username = normalize_required(&input.username, "ssh username")?;
    let auth_method = input.auth_kind.trim().to_ascii_lowercase();
    if !matches!(auth_method.as_str(), "password" | "private-key" | "none") {
        return Err(AppError::Validation(format!(
            "unsupported ssh auth kind: {}",
            input.auth_kind
        )));
    }

    let port = input.port.unwrap_or(22);
    if port == 0 {
        return Err(AppError::Validation("ssh port cannot be 0".to_string()));
    }

    let key_path = empty_to_none(input.key_path.clone());
    if auth_method == "private-key" && key_path.is_none() {
        return Err(AppError::Validation(
            "private-key ssh auth requires a key path".to_string(),
        ));
    }

    Ok(SshConnectionStorageInput {
        host,
        port,
        username,
        auth_method,
        config: SshConnectionConfig { key_path },
    })
}

pub(super) fn ssh_config_to_json(config: &SshConnectionConfig) -> AppResult<String> {
    serde_json::to_string(config).map_err(AppError::from)
}

pub(super) fn parse_ssh_config(
    connection_id: &str,
    config_json: &str,
) -> AppResult<SshConnectionConfig> {
    serde_json::from_str::<SshConnectionConfig>(config_json).map_err(|error| {
        AppError::Config(format!(
            "invalid ssh_connections.config_json for connection {connection_id}: {error}"
        ))
    })
}

pub(super) fn decode_ssh_port(port: i64) -> AppResult<u16> {
    if (1..=u16::MAX as i64).contains(&port) {
        Ok(port as u16)
    } else {
        Err(AppError::Config(format!(
            "ssh connection port out of range: {port}"
        )))
    }
}

pub(super) fn validate_connection_ready_for_session(connection: &SshConnection) -> AppResult<()> {
    if connection.auth_kind == "password" && connection.credential_ref.is_none() {
        return Err(AppError::Validation(
            "password ssh session requires a stored password".to_string(),
        ));
    }
    if connection.auth_kind == "private-key" && connection.key_path.is_none() {
        return Err(AppError::Validation(
            "private-key ssh session requires a key path".to_string(),
        ));
    }
    Ok(())
}

/// Remove potentially sensitive details from SSH errors before surfacing them.
#[cfg(feature = "ssh-native")]
pub(super) fn sanitize_ssh_error(error: &russh::Error) -> String {
    let msg = error.to_string();
    let lower = msg.to_ascii_lowercase();
    // Strip anything that could contain a password, passphrase, or key material.
    if lower.contains("password") || lower.contains("passphrase") || lower.contains("private key") {
        "ssh transport error".to_string()
    } else {
        msg
    }
}

/// Maximum bytes captured per stream (stdout/stderr) for a diagnostic command.
#[cfg(feature = "ssh-native")]
const SSH_DIAGNOSTIC_MAX_OUTPUT_BYTES: usize = 64 * 1024;

/// Append `data` to `buf`, capping at the diagnostic output limit and marking
/// `truncated` when the limit is reached.
#[cfg(feature = "ssh-native")]
pub(super) fn append_capped(buf: &mut Vec<u8>, data: &[u8], truncated: &mut bool) {
    let remaining = SSH_DIAGNOSTIC_MAX_OUTPUT_BYTES.saturating_sub(buf.len());
    if remaining == 0 {
        *truncated = true;
        return;
    }
    if data.len() > remaining {
        buf.extend_from_slice(&data[..remaining]);
        *truncated = true;
    } else {
        buf.extend_from_slice(data);
    }
}

pub(super) fn normalize_name(name: &str) -> AppResult<String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err(AppError::Validation(
            "ssh connection name cannot be empty".to_string(),
        ));
    }
    if trimmed.chars().count() > 80 {
        return Err(AppError::Validation(
            "ssh connection name must be 80 characters or fewer".to_string(),
        ));
    }
    Ok(trimmed.to_string())
}

pub(super) fn normalize_required(value: &str, label: &str) -> AppResult<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(AppError::Validation(format!("{} cannot be empty", label)));
    }
    if trimmed.chars().any(char::is_control) {
        return Err(AppError::Validation(format!(
            "{} cannot contain control characters",
            label
        )));
    }
    Ok(trimmed.to_string())
}
