use super::*;

// --- SQL validation ---

/// MCP-layer read-only SQL validation. Strips comments, rejects multi-statement
/// SQL, and only allows an explicit allowlist of read-only keywords.
pub(super) fn validate_readonly_sql(sql: &str) -> Result<(), ToolCallError> {
    let trimmed = sql.trim();
    if trimmed.is_empty() {
        return Err(ToolCallError::Execution {
            code: "READONLY_SQL_REJECTED",
            message: "SQL cannot be empty.",
        });
    }

    // Strip leading comments to prevent bypass via `/* ... */ INSERT ...`.
    let stripped = strip_leading_comments(trimmed);
    if stripped.is_empty() {
        return Err(ToolCallError::Execution {
            code: "READONLY_SQL_REJECTED",
            message: "SQL cannot be empty after removing comments.",
        });
    }

    // Reject multi-statement SQL: after removing trailing semicolons, any
    // remaining semicolons indicate multiple statements.
    let without_trailing = stripped.trim_end_matches(';').trim_end();
    if without_trailing.contains(';') {
        return Err(ToolCallError::Execution {
            code: "READONLY_SQL_REJECTED",
            message: "Only one SQL statement is allowed.",
        });
    }

    let keyword = stripped
        .split_whitespace()
        .next()
        .unwrap_or_default()
        .to_ascii_lowercase();

    match keyword.as_str() {
        "select" | "show" | "describe" | "desc" => Ok(()),
        // EXPLAIN and WITH can wrap a statement that actually writes (EXPLAIN
        // ANALYZE <write> and data-modifying CTEs execute in PostgreSQL), so a
        // read-only tool must reject them when they contain a write keyword.
        "with" | "explain" => {
            if statement_has_write(&stripped) {
                Err(ToolCallError::Execution {
                    code: "READONLY_SQL_REJECTED",
                    message:
                        "EXPLAIN/WITH statements that modify data or schema are not allowed in read-only mode.",
                })
            } else {
                Ok(())
            }
        }
        _ => Err(ToolCallError::Execution {
            code: "READONLY_SQL_REJECTED",
            message:
                "Only read-only SQL is permitted (SELECT, WITH, SHOW, DESCRIBE, DESC, EXPLAIN).",
        }),
    }
}

/// Scan a statement's tokens for a data-modifying or schema-changing keyword.
/// Used to reject writes hidden behind an `EXPLAIN`/`WITH` wrapper. Errs toward
/// over-detection: a keyword inside a string literal only causes a rejection,
/// never a missed write.
pub(super) fn statement_has_write(sql: &str) -> bool {
    const WRITE: &[&str] = &[
        "insert", "update", "delete", "replace", "merge", "upsert", "create", "alter", "drop",
        "truncate", "vacuum", "reindex", "grant", "revoke",
    ];
    sql.split(|c: char| !c.is_ascii_alphanumeric() && c != '_')
        .any(|token| !token.is_empty() && WRITE.contains(&token.to_ascii_lowercase().as_str()))
}

pub(super) fn validate_single_statement_for_execute(sql: &str) -> Result<(), ToolCallError> {
    let stripped = strip_leading_comments(sql);
    let without_trailing = stripped.trim_end_matches(';').trim_end();
    if without_trailing.contains(';') {
        return Err(ToolCallError::Execution {
            code: "UNSUPPORTED_OPERATION",
            message: "db_execute accepts exactly one SQL statement; split multi-statement SQL into separate confirmed calls.",
        });
    }
    Ok(())
}

#[derive(Debug, Clone, Copy)]
pub(super) struct SqlRisk {
    pub(super) statement_type: &'static str,
    pub(super) requires_confirmation: bool,
    pub(super) confirmation_code: &'static str,
    pub(super) reason: &'static str,
}

pub(super) fn classify_sql_risk(sql: &str) -> SqlRisk {
    let stripped = strip_leading_comments(sql);
    let lower = stripped.to_ascii_lowercase();
    let keyword = stripped
        .split_whitespace()
        .next()
        .unwrap_or_default()
        .to_ascii_lowercase();

    match keyword.as_str() {
        "delete" if !contains_where(&lower) => SqlRisk {
            statement_type: "mutation",
            requires_confirmation: true,
            confirmation_code: "DELETE_WITHOUT_WHERE",
            reason: "DELETE without WHERE is dangerous and may affect an entire table.",
        },
        "update" if !contains_where(&lower) => SqlRisk {
            statement_type: "mutation",
            requires_confirmation: true,
            confirmation_code: "UPDATE_WITHOUT_WHERE",
            reason: "UPDATE without WHERE is dangerous and may affect an entire table.",
        },
        "drop" => SqlRisk {
            statement_type: "schema-change",
            requires_confirmation: true,
            confirmation_code: "DROP_SQL",
            reason: "DROP can remove schema objects or databases.",
        },
        "truncate" => SqlRisk {
            statement_type: "schema-change",
            requires_confirmation: true,
            confirmation_code: "TRUNCATE_SQL",
            reason: "TRUNCATE can delete all rows in a table.",
        },
        "alter" => SqlRisk {
            statement_type: "schema-change",
            requires_confirmation: true,
            confirmation_code: "ALTER_SQL",
            reason: "ALTER changes table or database structure.",
        },
        "create" | "vacuum" | "reindex" => SqlRisk {
            statement_type: "schema-change",
            requires_confirmation: false,
            confirmation_code: "SCHEMA_SQL",
            reason: "Schema-changing SQL.",
        },
        "insert" | "update" | "delete" | "replace" => SqlRisk {
            statement_type: "mutation",
            requires_confirmation: false,
            confirmation_code: "MUTATION_SQL",
            reason: "Data mutation SQL.",
        },
        "select" | "with" | "show" | "describe" | "desc" | "explain" | "pragma" => SqlRisk {
            statement_type: "read",
            requires_confirmation: false,
            confirmation_code: "READ_SQL",
            reason: "Read-only SQL.",
        },
        _ => SqlRisk {
            statement_type: "unknown",
            requires_confirmation: true,
            confirmation_code: "UNKNOWN_SQL",
            reason: "Unrecognized SQL statement type requires confirmation before execution.",
        },
    }
}

pub(super) fn contains_where(lower_sql: &str) -> bool {
    lower_sql
        .split(|c: char| !c.is_ascii_alphanumeric() && c != '_')
        .any(|token| token == "where")
}

/// Strip leading SQL line comments (`--`) and block comments (`/* ... */`).
pub(super) fn strip_leading_comments(sql: &str) -> String {
    let mut s = sql.trim();
    loop {
        if s.starts_with("--") {
            // Line comment: skip to end of line.
            if let Some(pos) = s.find('\n') {
                s = s[pos + 1..].trim();
            } else {
                return String::new();
            }
        } else if s.starts_with("/*") {
            // Block comment: skip to closing `*/`.
            if let Some(pos) = s.find("*/") {
                s = s[pos + 2..].trim();
            } else {
                return String::new();
            }
        } else {
            break;
        }
    }
    s.to_string()
}
