use std::collections::{HashMap, HashSet};

use chrono::Utc;
use sqlx::SqliteConnection;
use unfour_core::domain::{CommandContext, DomainEntityType, DomainMutation, MutationOperation};
use unfour_core::models::{
    WorkspaceEnvironmentVariable, WorkspaceVariable, WorkspaceVariableInput,
};
use unfour_core::{AppError, AppResult};

use super::variable_executor::entity_mutation;
use super::variables::{
    get_environment_variable_on, get_variable_on, list_environment_variables_on, list_variables_on,
    non_empty_optional, normalize_description,
};

pub(super) async fn replace_workspace_variables_exact(
    connection: &mut SqliteConnection,
    context: &CommandContext,
    workspace_id: &str,
    variables: Vec<WorkspaceVariableInput>,
) -> AppResult<Vec<DomainMutation>> {
    let current = list_variables_on(connection, workspace_id, false).await?;
    let current_by_id: HashMap<_, _> = current
        .iter()
        .map(|variable| (variable.id.clone(), variable))
        .collect();
    let desired_ids: HashSet<String> = variables
        .iter()
        .filter_map(|input| non_empty_optional(input.id.clone()))
        .collect();
    let now = Utc::now().to_rfc3339();

    // Temporarily remove renamed rows from the partial unique index so one
    // exact-replace transaction can swap keys between existing ids. The
    // upsert phase restores each row and records the single business revision.
    for input in &variables {
        if let Some(id) = non_empty_optional(input.id.clone()) {
            let existing = get_variable_on(connection, workspace_id, &id, true).await?;
            if existing.deleted_at.is_none() && existing.key != input.key.trim() {
                mark_temporarily_deleted(connection, "workspace_variables", &id, &now).await?;
            }
        }
    }

    let mut mutations = Vec::new();
    for variable in &current {
        if desired_ids.contains(&variable.id) {
            continue;
        }
        let revision = soft_delete(
            connection,
            "workspace_variables",
            workspace_id,
            None,
            &variable.id,
            &now,
        )
        .await?;
        mutations.push(entity_mutation(
            context,
            DomainEntityType::WorkspaceVariable,
            MutationOperation::Delete,
            workspace_id,
            &variable.id,
            revision,
        ));
    }

    for (index, input) in variables.into_iter().enumerate() {
        let sort_order = i64::try_from(index).unwrap_or(i64::MAX);
        if let Some(id) = non_empty_optional(input.id.clone()) {
            let existing = get_variable_on(connection, workspace_id, &id, true).await?;
            if existing.deleted_at.is_none()
                && current_by_id.contains_key(&id)
                && same_workspace_variable(&existing, &input, sort_order)
            {
                continue;
            }
            let revision =
                update_workspace_variable(connection, workspace_id, &id, &input, sort_order, &now)
                    .await?;
            mutations.push(entity_mutation(
                context,
                DomainEntityType::WorkspaceVariable,
                MutationOperation::Upsert,
                workspace_id,
                &id,
                revision,
            ));
        } else {
            let id = unfour_core::id::new_id();
            insert_workspace_variable(connection, workspace_id, &id, &input, sort_order, &now)
                .await?;
            mutations.push(entity_mutation(
                context,
                DomainEntityType::WorkspaceVariable,
                MutationOperation::Upsert,
                workspace_id,
                &id,
                1,
            ));
        }
    }
    Ok(mutations)
}

pub(super) async fn replace_environment_variables_exact(
    connection: &mut SqliteConnection,
    context: &CommandContext,
    workspace_id: &str,
    environment_id: &str,
    variables: Vec<WorkspaceVariableInput>,
) -> AppResult<Vec<DomainMutation>> {
    let current =
        list_environment_variables_on(connection, workspace_id, environment_id, false).await?;
    let current_by_id: HashMap<_, _> = current
        .iter()
        .map(|variable| (variable.id.clone(), variable))
        .collect();
    let desired_ids: HashSet<String> = variables
        .iter()
        .filter_map(|input| non_empty_optional(input.id.clone()))
        .collect();
    let now = Utc::now().to_rfc3339();
    // See the workspace-variable pass above: this is uniqueness staging, not
    // a tombstone, and must not emit a delete mutation or revision of its own.
    for input in &variables {
        if let Some(id) = non_empty_optional(input.id.clone()) {
            let existing =
                get_environment_variable_on(connection, workspace_id, environment_id, &id, true)
                    .await?;
            if existing.deleted_at.is_none() && existing.key != input.key.trim() {
                mark_temporarily_deleted(connection, "workspace_environment_variables", &id, &now)
                    .await?;
            }
        }
    }

    let mut mutations = Vec::new();
    for variable in &current {
        if desired_ids.contains(&variable.id) {
            continue;
        }
        let revision = soft_delete(
            connection,
            "workspace_environment_variables",
            workspace_id,
            Some(environment_id),
            &variable.id,
            &now,
        )
        .await?;
        mutations.push(
            entity_mutation(
                context,
                DomainEntityType::WorkspaceEnvironmentVariable,
                MutationOperation::Delete,
                workspace_id,
                &variable.id,
                revision,
            )
            .with_parent_entity_id(environment_id),
        );
    }

    for (index, input) in variables.into_iter().enumerate() {
        let sort_order = i64::try_from(index).unwrap_or(i64::MAX);
        if let Some(id) = non_empty_optional(input.id.clone()) {
            let existing =
                get_environment_variable_on(connection, workspace_id, environment_id, &id, true)
                    .await?;
            if existing.deleted_at.is_none()
                && current_by_id.contains_key(&id)
                && same_environment_variable(&existing, &input, sort_order)
            {
                continue;
            }
            let revision = update_environment_variable(
                connection,
                workspace_id,
                environment_id,
                &id,
                &input,
                sort_order,
                &now,
            )
            .await?;
            mutations.push(
                entity_mutation(
                    context,
                    DomainEntityType::WorkspaceEnvironmentVariable,
                    MutationOperation::Upsert,
                    workspace_id,
                    &id,
                    revision,
                )
                .with_parent_entity_id(environment_id),
            );
        } else {
            let id = unfour_core::id::new_id();
            insert_environment_variable(
                connection,
                workspace_id,
                environment_id,
                &id,
                &input,
                sort_order,
                &now,
            )
            .await?;
            mutations.push(
                entity_mutation(
                    context,
                    DomainEntityType::WorkspaceEnvironmentVariable,
                    MutationOperation::Upsert,
                    workspace_id,
                    &id,
                    1,
                )
                .with_parent_entity_id(environment_id),
            );
        }
    }
    Ok(mutations)
}

pub(super) async fn insert_workspace_variable(
    connection: &mut SqliteConnection,
    workspace_id: &str,
    id: &str,
    input: &WorkspaceVariableInput,
    sort_order: i64,
    now: &str,
) -> AppResult<()> {
    sqlx::query(
        r#"
        INSERT INTO workspace_variables (
          id, workspace_id, key, value, is_secret, is_enabled, description,
          sort_order, created_at, updated_at, revision
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?9, 1)
        "#,
    )
    .bind(id)
    .bind(workspace_id)
    .bind(input.key.trim())
    .bind(&input.value)
    .bind(input.is_secret)
    .bind(input.is_enabled)
    .bind(normalize_description(input.description.clone()))
    .bind(sort_order)
    .bind(now)
    .execute(&mut *connection)
    .await?;
    Ok(())
}

pub(super) async fn update_workspace_variable(
    connection: &mut SqliteConnection,
    workspace_id: &str,
    id: &str,
    input: &WorkspaceVariableInput,
    sort_order: i64,
    now: &str,
) -> AppResult<i64> {
    Ok(sqlx::query_scalar(
        r#"
        UPDATE workspace_variables
        SET key = ?1, value = ?2, is_secret = ?3, is_enabled = ?4,
            description = ?5, sort_order = ?6, updated_at = ?7,
            deleted_at = NULL, revision = revision + 1
        WHERE id = ?8 AND workspace_id = ?9
        RETURNING revision
        "#,
    )
    .bind(input.key.trim())
    .bind(&input.value)
    .bind(input.is_secret)
    .bind(input.is_enabled)
    .bind(normalize_description(input.description.clone()))
    .bind(sort_order)
    .bind(now)
    .bind(id)
    .bind(workspace_id)
    .fetch_one(&mut *connection)
    .await?)
}

pub(super) async fn insert_environment_variable(
    connection: &mut SqliteConnection,
    workspace_id: &str,
    environment_id: &str,
    id: &str,
    input: &WorkspaceVariableInput,
    sort_order: i64,
    now: &str,
) -> AppResult<()> {
    sqlx::query(
        r#"
        INSERT INTO workspace_environment_variables (
          id, workspace_id, environment_id, key, value, is_secret, is_enabled,
          description, sort_order, created_at, updated_at, revision
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?10, 1)
        "#,
    )
    .bind(id)
    .bind(workspace_id)
    .bind(environment_id)
    .bind(input.key.trim())
    .bind(&input.value)
    .bind(input.is_secret)
    .bind(input.is_enabled)
    .bind(normalize_description(input.description.clone()))
    .bind(sort_order)
    .bind(now)
    .execute(&mut *connection)
    .await?;
    Ok(())
}

pub(super) async fn update_environment_variable(
    connection: &mut SqliteConnection,
    workspace_id: &str,
    environment_id: &str,
    id: &str,
    input: &WorkspaceVariableInput,
    sort_order: i64,
    now: &str,
) -> AppResult<i64> {
    Ok(sqlx::query_scalar(
        r#"
        UPDATE workspace_environment_variables
        SET key = ?1, value = ?2, is_secret = ?3, is_enabled = ?4,
            description = ?5, sort_order = ?6, updated_at = ?7,
            deleted_at = NULL, revision = revision + 1
        WHERE id = ?8 AND workspace_id = ?9 AND environment_id = ?10
        RETURNING revision
        "#,
    )
    .bind(input.key.trim())
    .bind(&input.value)
    .bind(input.is_secret)
    .bind(input.is_enabled)
    .bind(normalize_description(input.description.clone()))
    .bind(sort_order)
    .bind(now)
    .bind(id)
    .bind(workspace_id)
    .bind(environment_id)
    .fetch_one(&mut *connection)
    .await?)
}

pub(super) async fn soft_delete(
    connection: &mut SqliteConnection,
    table: &str,
    workspace_id: &str,
    environment_id: Option<&str>,
    id: &str,
    now: &str,
) -> AppResult<i64> {
    let sql = match table {
        "workspace_variables" => {
            "UPDATE workspace_variables SET deleted_at = ?1, updated_at = ?1, revision = revision + 1 WHERE id = ?2 AND workspace_id = ?3 AND deleted_at IS NULL RETURNING revision"
        }
        "workspace_environments" => {
            "UPDATE workspace_environments SET deleted_at = ?1, updated_at = ?1, revision = revision + 1 WHERE id = ?2 AND workspace_id = ?3 AND deleted_at IS NULL RETURNING revision"
        }
        "workspace_environment_variables" => {
            "UPDATE workspace_environment_variables SET deleted_at = ?1, updated_at = ?1, revision = revision + 1 WHERE id = ?2 AND workspace_id = ?3 AND environment_id = ?4 AND deleted_at IS NULL RETURNING revision"
        }
        _ => return Err(AppError::Config("unsupported workspace entity table".to_string())),
    };
    let mut query = sqlx::query_scalar(sql)
        .bind(now)
        .bind(id)
        .bind(workspace_id);
    if table == "workspace_environment_variables" {
        query = query.bind(environment_id.ok_or_else(|| {
            AppError::Config("environment id required for variable delete".to_string())
        })?);
    }
    query.fetch_one(&mut *connection).await.map_err(Into::into)
}

async fn mark_temporarily_deleted(
    connection: &mut SqliteConnection,
    table: &str,
    id: &str,
    now: &str,
) -> AppResult<()> {
    let sql = match table {
        "workspace_variables" => "UPDATE workspace_variables SET deleted_at = ?1 WHERE id = ?2",
        "workspace_environment_variables" => {
            "UPDATE workspace_environment_variables SET deleted_at = ?1 WHERE id = ?2"
        }
        _ => return Err(AppError::Config("unsupported variable table".to_string())),
    };
    sqlx::query(sql)
        .bind(now)
        .bind(id)
        .execute(&mut *connection)
        .await?;
    Ok(())
}

pub(super) fn same_workspace_variable(
    current: &WorkspaceVariable,
    input: &WorkspaceVariableInput,
    sort_order: i64,
) -> bool {
    current.deleted_at.is_none()
        && current.key == input.key.trim()
        && current.value == input.value
        && current.is_secret == input.is_secret
        && current.is_enabled == input.is_enabled
        && current.description == normalize_description(input.description.clone())
        && current.sort_order == sort_order
}

pub(super) fn same_environment_variable(
    current: &WorkspaceEnvironmentVariable,
    input: &WorkspaceVariableInput,
    sort_order: i64,
) -> bool {
    current.deleted_at.is_none()
        && current.key == input.key.trim()
        && current.value == input.value
        && current.is_secret == input.is_secret
        && current.is_enabled == input.is_enabled
        && current.description == normalize_description(input.description.clone())
        && current.sort_order == sort_order
}
