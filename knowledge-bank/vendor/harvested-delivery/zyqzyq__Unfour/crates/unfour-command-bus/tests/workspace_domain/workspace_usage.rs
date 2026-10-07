use super::*;

#[tokio::test]
async fn workspace_usage_state_is_local_only_and_snapshot_is_sync_safe() {
    let capture = Arc::new(SqlHook {
        name: "capture",
        fail_on: None,
        local_only: false,
    });
    let (bus, db) = bus_with_hooks(vec![capture]).await;
    let created = bus.create_workspace("Mutable".to_string()).await.unwrap();
    let revision = created.revision;
    let unchanged = bus
        .rename_workspace(created.id.clone(), created.name.clone())
        .await
        .unwrap();
    assert_eq!(unchanged.revision, revision);
    let no_op_mutations: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM hook_effects WHERE command_name = 'workspace.rename'",
    )
    .fetch_one(db.pool())
    .await
    .unwrap();
    assert_eq!(no_op_mutations, 0);
    bus.rename_workspace(created.id.clone(), "Renamed".to_string())
        .await
        .unwrap();
    bus.update_workspace_environment(created.id.clone(), "prod".to_string())
        .await
        .unwrap();
    bus.update_workspace_mcp_policy(created.id.clone(), "read_only".to_string())
        .await
        .unwrap();
    let before_usage: (i64, Option<String>) =
        sqlx::query_as("SELECT revision, last_opened_at FROM workspaces WHERE id = ?1")
            .bind(&created.id)
            .fetch_one(db.pool())
            .await
            .unwrap();
    let default_state = bus.set_default_workspace(created.id.clone()).await.unwrap();
    assert!(
        default_state
            .workspaces
            .iter()
            .find(|workspace| workspace.id == created.id)
            .unwrap()
            .is_default
    );
    let active_state = bus.set_active_workspace(created.id.clone()).await.unwrap();
    assert_eq!(active_state.active_workspace_id, created.id);
    let usage_hook_calls: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM hook_effects WHERE command_name IN ('workspace.default.set', 'workspace.activate')",
    )
    .fetch_one(db.pool())
    .await
    .unwrap();
    assert_eq!(usage_hook_calls, 0);
    let after_usage: (i64, Option<String>) =
        sqlx::query_as("SELECT revision, last_opened_at FROM workspaces WHERE id = ?1")
            .bind(&created.id)
            .fetch_one(db.pool())
            .await
            .unwrap();
    assert_eq!(after_usage.0, before_usage.0);
    assert_ne!(after_usage.1, before_usage.1);
    assert!(after_usage.1.is_some());

    let snapshot = bus
        .read_domain_snapshot(&DomainEntityKey::new(
            DomainEntityType::Workspace,
            &created.id,
            &created.id,
        ))
        .await
        .unwrap();
    let DomainSnapshot::Workspace(snapshot) = snapshot else {
        panic!("expected workspace snapshot");
    };
    assert_eq!(snapshot.id, created.id);
    assert_eq!(snapshot.name, "Renamed");
    assert_eq!(snapshot.environment_type, "prod");
    assert_eq!(snapshot.mcp_policy, "read_only");
    assert!(!snapshot.created_at.is_empty());
    assert!(!snapshot.updated_at.is_empty());
    assert!(snapshot.revision > revision);
    let serialized = serde_json::to_value(&snapshot).unwrap();
    assert!(serialized.get("isDefault").is_none());
    assert!(serialized.get("lastOpenedAt").is_none());
}
