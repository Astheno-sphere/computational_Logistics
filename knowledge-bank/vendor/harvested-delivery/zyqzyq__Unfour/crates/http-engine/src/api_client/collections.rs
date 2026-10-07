use super::*;
#[cfg(test)]
use unfour_core::domain::CommandContext;

impl ApiClientService {
    pub async fn list_collections(&self, workspace_id: String) -> AppResult<Vec<ApiCollection>> {
        validate_workspace_id(&workspace_id)?;
        let rows = sqlx::query_as::<_, CollectionRow>(
            r#"
            SELECT id, workspace_id, name, description, created_at, updated_at
            FROM api_collections
            WHERE workspace_id = ?1 AND deleted_at IS NULL
            ORDER BY name COLLATE NOCASE
            "#,
        )
        .bind(workspace_id)
        .fetch_all(self.db.pool())
        .await?;

        Ok(rows.into_iter().map(ApiCollection::from).collect())
    }

    #[cfg(test)]
    pub(crate) async fn create_collection(
        &self,
        workspace_id: String,
        name: String,
    ) -> AppResult<ApiCollection> {
        let context = CommandContext::local("api.collection.create");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .create_collection_on(&mut transaction, &context, workspace_id, name)
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    #[cfg(test)]
    pub(crate) async fn rename_collection(
        &self,
        workspace_id: String,
        collection_id: String,
        name: String,
    ) -> AppResult<ApiCollection> {
        let context = CommandContext::local("api.collection.rename");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .rename_collection_on(
                &mut transaction,
                &context,
                workspace_id,
                collection_id,
                name,
            )
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    pub async fn list_collection_folders(
        &self,
        workspace_id: String,
        collection_id: Option<String>,
    ) -> AppResult<Vec<ApiCollectionFolder>> {
        validate_workspace_id(&workspace_id)?;
        let collection_id = normalize_entity_id(collection_id);
        let rows = match collection_id {
            Some(collection_id) => {
                self.get_collection(&workspace_id, &collection_id).await?;
                sqlx::query_as::<_, ApiCollectionFolder>(
                    r#"
                    SELECT id, workspace_id, collection_id, parent_folder_id, name,
                           sort_order, created_at, updated_at, deleted_at,
                           revision, sync_status, remote_id
                    FROM api_collection_folders
                    WHERE workspace_id = ?1 AND collection_id = ?2 AND deleted_at IS NULL
                    ORDER BY COALESCE(parent_folder_id, ''), sort_order, name COLLATE NOCASE
                    "#,
                )
                .bind(&workspace_id)
                .bind(collection_id)
                .fetch_all(self.db.pool())
                .await?
            }
            None => {
                sqlx::query_as::<_, ApiCollectionFolder>(
                    r#"
                    SELECT id, workspace_id, collection_id, parent_folder_id, name,
                           sort_order, created_at, updated_at, deleted_at,
                           revision, sync_status, remote_id
                    FROM api_collection_folders
                    WHERE workspace_id = ?1 AND deleted_at IS NULL
                    ORDER BY collection_id, COALESCE(parent_folder_id, ''), sort_order, name COLLATE NOCASE
                    "#,
                )
                .bind(&workspace_id)
                .fetch_all(self.db.pool())
                .await?
            }
        };

        Ok(rows)
    }

    #[cfg(test)]
    pub(crate) async fn create_collection_folder(
        &self,
        workspace_id: String,
        collection_id: String,
        parent_folder_id: Option<String>,
        name: String,
    ) -> AppResult<ApiCollectionFolder> {
        let context = CommandContext::local("api.collection.folder.create");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .create_collection_folder_on(
                &mut transaction,
                &context,
                workspace_id,
                collection_id,
                parent_folder_id,
                name,
            )
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    #[cfg(test)]
    pub(crate) async fn rename_collection_folder(
        &self,
        workspace_id: String,
        folder_id: String,
        name: String,
    ) -> AppResult<ApiCollectionFolder> {
        let context = CommandContext::local("api.collection.folder.rename");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .rename_collection_folder_on(&mut transaction, &context, workspace_id, folder_id, name)
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    #[cfg(test)]
    pub(crate) async fn delete_collection_folder(
        &self,
        workspace_id: String,
        folder_id: String,
    ) -> AppResult<Vec<ApiCollectionFolder>> {
        let context = CommandContext::local("api.collection.folder.delete");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .delete_collection_folder_on(&mut transaction, &context, workspace_id, folder_id)
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    #[cfg(test)]
    pub(crate) async fn move_collection_folder(
        &self,
        workspace_id: String,
        folder_id: String,
        target_parent_folder_id: Option<String>,
    ) -> AppResult<ApiCollectionFolder> {
        let context = CommandContext::local("api.collection.folder.move");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .move_collection_folder_on(
                &mut transaction,
                &context,
                workspace_id,
                folder_id,
                target_parent_folder_id,
            )
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    #[cfg(test)]
    pub(crate) async fn reorder_collection_folders(
        &self,
        workspace_id: String,
        collection_id: String,
        parent_folder_id: Option<String>,
        folder_ids: Vec<String>,
    ) -> AppResult<Vec<ApiCollectionFolder>> {
        let context = CommandContext::local("api.collection.folder.reorder");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .reorder_collection_folders_on(
                &mut transaction,
                &context,
                workspace_id,
                collection_id,
                parent_folder_id,
                folder_ids,
            )
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    /// Soft-delete a collection and cascade soft-delete its saved requests in a
    /// single transaction.
    #[cfg(test)]
    pub(crate) async fn delete_collection(
        &self,
        workspace_id: String,
        collection_id: String,
    ) -> AppResult<Vec<ApiCollection>> {
        let context = CommandContext::local("api.collection.delete");
        let mut transaction = self.db.pool().begin().await?;
        let outcome = self
            .delete_collection_on(&mut transaction, &context, workspace_id, collection_id)
            .await?;
        transaction.commit().await?;
        Ok(outcome.value)
    }

    /// Reassign a saved request to a different collection and/or folder.
    pub(super) async fn get_collection(
        &self,
        workspace_id: &str,
        collection_id: &str,
    ) -> AppResult<ApiCollection> {
        let row = sqlx::query_as::<_, CollectionRow>(
            r#"
            SELECT id, workspace_id, name, description, created_at, updated_at
            FROM api_collections
            WHERE workspace_id = ?1 AND id = ?2 AND deleted_at IS NULL
            "#,
        )
        .bind(workspace_id)
        .bind(collection_id)
        .fetch_optional(self.db.pool())
        .await?;

        row.map(ApiCollection::from)
            .ok_or_else(|| AppError::NotFound("api collection".to_string()))
    }
}
