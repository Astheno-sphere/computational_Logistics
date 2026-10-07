use unfour_core::redaction::redact_sensitive_lines;

pub(crate) fn command_activity_kind(command: &str) -> (String, bool) {
    let head = command
        .split_whitespace()
        .next()
        .unwrap_or("unknown")
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_' || *c == '.')
        .collect::<String>();
    let (_, redacted) = redact_sensitive_lines(command);
    (
        if head.is_empty() {
            "unknown".to_string()
        } else {
            head
        },
        redacted,
    )
}

pub(crate) fn truncate_url_preview(url: &str) -> String {
    const MAX_LEN: usize = 200;
    if url.len() <= MAX_LEN {
        url.to_string()
    } else {
        let mut truncated: String = url.chars().take(MAX_LEN).collect();
        truncated.push_str("...");
        truncated
    }
}
