use std::path::PathBuf;

use unfour_core::AppResult;
use unfour_local_storage::LocalDb;

use crate::{CommandBus, CommandBusExtensions};

pub use unfour_paths::{DEFAULT_DATABASE_FILE, DEFAULT_PRODUCT_DATA_DIR};

pub fn default_database_path() -> AppResult<PathBuf> {
    LocalDb::default_database_path()
}

impl CommandBus {
    /// Connect to the default storage with a read-only DB handle, then build
    /// a `CommandBus` without seeding the default workspace. The `_read_only`
    /// suffix refers to the underlying SQLite connection; the returned bus
    /// still carries full write-capable services.
    pub async fn from_existing_default_storage_read_only() -> AppResult<Self> {
        let db = LocalDb::connect_existing_default_read_only().await?;
        Self::from_existing_db_without_seeding(db).await
    }

    /// Connect to the default storage with a read-write DB handle, then build
    /// a `CommandBus` without seeding the default workspace.
    pub async fn from_existing_default_storage() -> AppResult<Self> {
        Self::from_existing_default_storage_with_extensions(CommandBusExtensions::default()).await
    }

    /// Connect to the default storage with a read-write DB handle and install
    /// transactional command hooks without seeding workspace data.
    pub async fn from_existing_default_storage_with_extensions(
        extensions: CommandBusExtensions,
    ) -> AppResult<Self> {
        let db = LocalDb::connect_existing_default().await?;
        Self::from_existing_db_without_seeding_with_extensions(db, extensions).await
    }

    /// Connect to an explicit storage dir with a read-write DB handle, then
    /// build a `CommandBus` without seeding the default workspace.
    pub async fn from_existing_storage_dir(
        storage_dir: impl AsRef<std::path::Path>,
    ) -> AppResult<Self> {
        Self::from_existing_storage_dir_with_extensions(
            storage_dir,
            CommandBusExtensions::default(),
        )
        .await
    }

    /// Connect to an explicit storage dir with a read-write DB handle and
    /// install transactional command hooks without seeding workspace data.
    pub async fn from_existing_storage_dir_with_extensions(
        storage_dir: impl AsRef<std::path::Path>,
        extensions: CommandBusExtensions,
    ) -> AppResult<Self> {
        let db = LocalDb::connect_existing_path(storage_dir.as_ref().join(DEFAULT_DATABASE_FILE))
            .await?;
        Self::from_existing_db_without_seeding_with_extensions(db, extensions).await
    }

    /// Connect to a storage dir with a read-only DB handle, then build a
    /// `CommandBus` without seeding the default workspace. The `_read_only`
    /// suffix refers to the underlying SQLite connection; the returned bus
    /// still carries full write-capable services.
    pub async fn from_existing_storage_dir_read_only(
        storage_dir: impl AsRef<std::path::Path>,
    ) -> AppResult<Self> {
        let db = LocalDb::connect_existing_read_only_path(
            storage_dir.as_ref().join(DEFAULT_DATABASE_FILE),
        )
        .await?;
        Self::from_existing_db_without_seeding(db).await
    }
}
