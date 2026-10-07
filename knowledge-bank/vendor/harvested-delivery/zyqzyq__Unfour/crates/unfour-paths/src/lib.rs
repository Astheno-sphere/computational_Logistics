use std::fs;
use std::io;
use std::path::PathBuf;

/// Stable (default) product data directory name under the user home.
pub const DEFAULT_PRODUCT_DATA_DIR: &str = ".unfour";
/// Dev-profile product data directory name (sibling of `.unfour`, not a child).
pub const DEV_PRODUCT_DATA_DIR: &str = ".unfour-dev";
/// Test-profile product data directory name (sibling of `.unfour`, not a child).
pub const TEST_PRODUCT_DATA_DIR: &str = ".unfour-test";
pub const DEFAULT_DATABASE_FILE: &str = "unfour.sqlite";

const ENV_DATA_DIR: &str = "UNFOUR_DATA_DIR";
const ENV_STORAGE_PROFILE: &str = "UNFOUR_STORAGE_PROFILE";

/// Local storage profile that selects the product data root under `$HOME`.
///
/// Profiles use sibling directories (`~/.unfour`, `~/.unfour-dev`,
/// `~/.unfour-test`). They do not nest under `~/.unfour/dev`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StorageProfile {
    Stable,
    Dev,
    Test,
}

impl StorageProfile {
    pub fn dir_name(self) -> &'static str {
        match self {
            Self::Stable => DEFAULT_PRODUCT_DATA_DIR,
            Self::Dev => DEV_PRODUCT_DATA_DIR,
            Self::Test => TEST_PRODUCT_DATA_DIR,
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "stable" => Some(Self::Stable),
            "dev" => Some(Self::Dev),
            "test" => Some(Self::Test),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnfourPaths {
    pub product_data_dir: PathBuf,
    pub database_path: PathBuf,
    pub config_dir: PathBuf,
    pub cache_dir: PathBuf,
    pub backups_dir: PathBuf,
    pub logs_dir: PathBuf,
    pub diagnostics_dir: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StorageDiagnostics {
    pub product_data_dir: PathBuf,
    pub database_path: PathBuf,
    pub config_dir: PathBuf,
    pub cache_dir: PathBuf,
    pub backups_dir: PathBuf,
    pub logs_dir: PathBuf,
    pub diagnostics_dir: PathBuf,
    pub database_exists: bool,
    pub current_exe: Option<PathBuf>,
    pub current_working_dir: Option<PathBuf>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct PathRoots {
    data_dir: PathBuf,
    config_dir: Option<PathBuf>,
    cache_dir: Option<PathBuf>,
}

impl PathRoots {
    fn new(data_dir: PathBuf, config_dir: Option<PathBuf>, cache_dir: Option<PathBuf>) -> Self {
        Self {
            data_dir,
            config_dir,
            cache_dir,
        }
    }
}

pub fn resolve_unfour_paths() -> io::Result<UnfourPaths> {
    resolve_with_env(&default_roots()?)
}

pub fn initialize_unfour_storage() -> io::Result<UnfourPaths> {
    initialize_with_env(&default_roots()?)
}

pub fn storage_diagnostics() -> io::Result<StorageDiagnostics> {
    diagnostics_with_env(&default_roots()?)
}

pub fn default_database_path() -> io::Result<PathBuf> {
    Ok(resolve_unfour_paths()?.database_path)
}

/// Resolve the active storage profile.
///
/// Priority:
/// 1. `UNFOUR_STORAGE_PROFILE` (`dev` | `test` | `stable`)
/// 2. compile-time `UNFOUR_RELEASE_CHANNEL` (`stable` | `test`)
///
/// `UNFOUR_DATA_DIR` bypasses profile selection and replaces the whole tree.
pub fn resolve_storage_profile() -> StorageProfile {
    try_resolve_storage_profile().unwrap_or_else(|error| panic!("{error}"))
}

/// Fallible storage-profile resolver used by every path API.
///
/// A non-empty invalid runtime value is an error rather than a fallback.
pub fn try_resolve_storage_profile() -> io::Result<StorageProfile> {
    resolve_storage_profile_from(
        std::env::var(ENV_STORAGE_PROFILE).ok().as_deref(),
        option_env!("UNFOUR_RELEASE_CHANNEL"),
    )
}

fn resolve_storage_profile_from(
    runtime_profile: Option<&str>,
    compile_time_channel: Option<&str>,
) -> io::Result<StorageProfile> {
    if let Some(value) = runtime_profile {
        if !value.is_empty() {
            return StorageProfile::parse(value).ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    format!(
                        "UNFOUR_STORAGE_PROFILE must be exactly 'dev', 'test', or 'stable', got {value:?}"
                    ),
                )
            });
        }
    }
    if let Some(channel) = compile_time_channel {
        return match channel {
            "stable" => Ok(StorageProfile::Stable),
            "test" => Ok(StorageProfile::Test),
            value => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("invalid compiled UNFOUR_RELEASE_CHANNEL: {value:?}"),
            )),
        };
    }
    Ok(StorageProfile::Test)
}

/// All Unfour data lives under a home-relative product root on every platform.
/// Using the home directory (not `%APPDATA%` / `XDG_DATA_HOME`) keeps the path
/// stable, predictable, and consistent with developer-tool conventions.
fn default_roots() -> io::Result<PathRoots> {
    let home = dirs::home_dir().ok_or_else(|| {
        io::Error::new(io::ErrorKind::NotFound, "home directory is not available")
    })?;
    Ok(PathRoots::new(home.clone(), Some(home.clone()), Some(home)))
}

fn data_dir_override_from(value: Option<&str>) -> io::Result<Option<PathBuf>> {
    let Some(raw) = value.map(str::trim).filter(|value| !value.is_empty()) else {
        return Ok(None);
    };
    let path = PathBuf::from(raw);
    if !path.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "UNFOUR_DATA_DIR must be an absolute path",
        ));
    }
    Ok(Some(path))
}

fn data_dir_override() -> io::Result<Option<PathBuf>> {
    data_dir_override_from(std::env::var(ENV_DATA_DIR).ok().as_deref())
}

fn resolve_with_env(roots: &PathRoots) -> io::Result<UnfourPaths> {
    let profile = try_resolve_storage_profile()?;
    if let Some(override_dir) = data_dir_override()? {
        return Ok(paths_under_product_root(override_dir));
    }
    resolve_with_roots(roots, profile)
}

fn initialize_with_env(roots: &PathRoots) -> io::Result<UnfourPaths> {
    let paths = resolve_with_env(roots)?;
    create_storage_directories(&paths)?;
    Ok(paths)
}

fn diagnostics_with_env(roots: &PathRoots) -> io::Result<StorageDiagnostics> {
    let paths = resolve_with_env(roots)?;
    Ok(diagnostics_from_paths(paths))
}

fn resolve_with_roots(roots: &PathRoots, profile: StorageProfile) -> io::Result<UnfourPaths> {
    let product_dir_name = profile.dir_name();
    let product_data_dir = roots.data_dir.join(product_dir_name);
    let database_path = product_data_dir.join(DEFAULT_DATABASE_FILE);
    let config_dir = roots
        .config_dir
        .as_ref()
        .map(|dir| dir.join(product_dir_name))
        .unwrap_or_else(|| product_data_dir.join("config"));
    let cache_dir = roots
        .cache_dir
        .as_ref()
        .map(|dir| dir.join(product_dir_name))
        .unwrap_or_else(|| product_data_dir.join("cache"));
    let backups_dir = product_data_dir.join("backups");
    let logs_dir = product_data_dir.join("logs");
    let diagnostics_dir = product_data_dir.join("diagnostics");

    Ok(UnfourPaths {
        product_data_dir,
        database_path,
        config_dir,
        cache_dir,
        backups_dir,
        logs_dir,
        diagnostics_dir,
    })
}

/// Build the standard tree when `UNFOUR_DATA_DIR` replaces the product root.
///
/// Matches the default home-based layout where config/cache path fields point
/// at the product root itself (not nested `config/` / `cache/` children).
fn paths_under_product_root(product_data_dir: PathBuf) -> UnfourPaths {
    UnfourPaths {
        database_path: product_data_dir.join(DEFAULT_DATABASE_FILE),
        config_dir: product_data_dir.clone(),
        cache_dir: product_data_dir.clone(),
        backups_dir: product_data_dir.join("backups"),
        logs_dir: product_data_dir.join("logs"),
        diagnostics_dir: product_data_dir.join("diagnostics"),
        product_data_dir,
    }
}

fn create_storage_directories(paths: &UnfourPaths) -> io::Result<()> {
    fs::create_dir_all(&paths.product_data_dir)?;
    fs::create_dir_all(&paths.config_dir)?;
    fs::create_dir_all(&paths.cache_dir)?;
    fs::create_dir_all(&paths.backups_dir)?;
    fs::create_dir_all(&paths.logs_dir)?;
    fs::create_dir_all(&paths.diagnostics_dir)?;
    Ok(())
}

fn diagnostics_from_paths(paths: UnfourPaths) -> StorageDiagnostics {
    StorageDiagnostics {
        database_exists: paths.database_path.exists(),
        product_data_dir: paths.product_data_dir,
        database_path: paths.database_path,
        config_dir: paths.config_dir,
        cache_dir: paths.cache_dir,
        backups_dir: paths.backups_dir,
        logs_dir: paths.logs_dir,
        diagnostics_dir: paths.diagnostics_dir,
        current_exe: std::env::current_exe().ok(),
        current_working_dir: std::env::current_dir().ok(),
    }
}

#[cfg(test)]
fn initialize_with_roots(roots: &PathRoots, profile: StorageProfile) -> io::Result<UnfourPaths> {
    let paths = resolve_with_roots(roots, profile)?;
    create_storage_directories(&paths)?;
    Ok(paths)
}

#[cfg(test)]
fn diagnostics_with_roots(
    roots: &PathRoots,
    profile: StorageProfile,
) -> io::Result<StorageDiagnostics> {
    Ok(diagnostics_from_paths(resolve_with_roots(roots, profile)?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    use std::sync::{Mutex, OnceLock};

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    fn unique_test_root(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "unfour-paths-{name}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
    }

    fn assert_ends_with(path: &Path, parts: &[&str]) {
        let suffix = parts.iter().collect::<PathBuf>();
        assert!(
            path.ends_with(&suffix),
            "expected {} to end with {}",
            path.display(),
            suffix.display()
        );
    }

    #[test]
    fn compiled_channel_selects_the_matching_default_product_data_dir() {
        let _guard = env_lock().lock().expect("env lock");
        std::env::remove_var(ENV_DATA_DIR);
        std::env::remove_var(ENV_STORAGE_PROFILE);

        let paths = resolve_unfour_paths().expect("resolve paths");

        let (profile, directory) = match option_env!("UNFOUR_RELEASE_CHANNEL") {
            Some("stable") => (StorageProfile::Stable, DEFAULT_PRODUCT_DATA_DIR),
            Some("test") => (StorageProfile::Test, TEST_PRODUCT_DATA_DIR),
            value => panic!("unexpected compiled channel: {value:?}"),
        };
        assert_ends_with(&paths.database_path, &[directory, DEFAULT_DATABASE_FILE]);
        assert_eq!(paths.product_data_dir.file_name().unwrap(), directory);
        assert_eq!(resolve_storage_profile(), profile);
    }

    #[test]
    fn storage_profile_dir_names_are_siblings_not_nested() {
        assert_eq!(StorageProfile::Stable.dir_name(), ".unfour");
        assert_eq!(StorageProfile::Dev.dir_name(), ".unfour-dev");
        assert_eq!(StorageProfile::Test.dir_name(), ".unfour-test");
        assert_ne!(
            StorageProfile::Dev.dir_name(),
            Path::new(DEFAULT_PRODUCT_DATA_DIR)
                .join("dev")
                .to_string_lossy()
        );
    }

    #[test]
    fn resolve_storage_profile_prefers_runtime_over_compile_time() {
        assert_eq!(
            resolve_storage_profile_from(Some("dev"), Some("stable")).expect("dev profile"),
            StorageProfile::Dev
        );
        assert_eq!(
            resolve_storage_profile_from(Some("test"), Some("stable")).expect("test profile"),
            StorageProfile::Test
        );
        assert_eq!(
            resolve_storage_profile_from(Some("stable"), Some("test")).expect("stable profile"),
            StorageProfile::Stable
        );
    }

    #[test]
    fn resolve_storage_profile_maps_compile_time_channel() {
        assert_eq!(
            resolve_storage_profile_from(None, Some("stable")).expect("stable channel"),
            StorageProfile::Stable
        );
        assert_eq!(
            resolve_storage_profile_from(None, Some("test")).expect("test channel"),
            StorageProfile::Test
        );
        assert!(resolve_storage_profile_from(None, Some("dev")).is_err());
        assert!(resolve_storage_profile_from(None, Some("nightly")).is_err());
        assert_eq!(
            resolve_storage_profile_from(None, None).expect("local default"),
            StorageProfile::Test
        );
    }

    #[test]
    fn resolve_storage_profile_rejects_unknown_runtime_value() {
        let error = resolve_storage_profile_from(Some("nightly"), Some("test"))
            .expect_err("invalid runtime profile must fail");
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
        assert!(error.to_string().contains("UNFOUR_STORAGE_PROFILE"));
        assert!(resolve_storage_profile_from(Some("Dev"), Some("test")).is_err());
        assert!(resolve_storage_profile_from(Some(" dev"), Some("test")).is_err());
        assert!(resolve_storage_profile_from(Some(" "), Some("test")).is_err());
        assert_eq!(
            resolve_storage_profile_from(Some(""), None).expect("blank uses default"),
            StorageProfile::Test
        );
    }

    #[test]
    fn resolve_with_dev_profile_uses_sibling_product_dir() {
        let root = unique_test_root("dev-profile");
        let roots = PathRoots::new(root.clone(), Some(root.clone()), Some(root.clone()));

        let paths = resolve_with_roots(&roots, StorageProfile::Dev).expect("resolve paths");

        assert_eq!(paths.product_data_dir, root.join(DEV_PRODUCT_DATA_DIR));
        assert_eq!(
            paths.database_path,
            root.join(DEV_PRODUCT_DATA_DIR).join(DEFAULT_DATABASE_FILE)
        );
        assert_eq!(paths.config_dir, root.join(DEV_PRODUCT_DATA_DIR));
        assert_eq!(paths.cache_dir, root.join(DEV_PRODUCT_DATA_DIR));
        assert_eq!(paths.logs_dir, paths.product_data_dir.join("logs"));
        assert_eq!(paths.backups_dir, paths.product_data_dir.join("backups"));
        assert_eq!(
            paths.diagnostics_dir,
            paths.product_data_dir.join("diagnostics")
        );

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn resolve_with_test_profile_uses_sibling_product_dir() {
        let root = unique_test_root("test-profile");
        let roots = PathRoots::new(root.clone(), Some(root.clone()), Some(root.clone()));

        let paths = resolve_with_roots(&roots, StorageProfile::Test).expect("resolve paths");

        assert_eq!(paths.product_data_dir, root.join(TEST_PRODUCT_DATA_DIR));
        assert_eq!(
            paths.database_path,
            root.join(TEST_PRODUCT_DATA_DIR).join(DEFAULT_DATABASE_FILE)
        );

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn data_dir_override_replaces_entire_tree() {
        let root = unique_test_root("data-dir-override");
        let override_dir = root.join("sandbox");
        let paths = paths_under_product_root(override_dir.clone());

        assert_eq!(paths.product_data_dir, override_dir);
        assert_eq!(
            paths.database_path,
            override_dir.join(DEFAULT_DATABASE_FILE)
        );
        assert_eq!(paths.config_dir, override_dir);
        assert_eq!(paths.cache_dir, override_dir);
        assert_eq!(paths.logs_dir, override_dir.join("logs"));
        assert_eq!(paths.backups_dir, override_dir.join("backups"));
        assert_eq!(paths.diagnostics_dir, override_dir.join("diagnostics"));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn data_dir_override_requires_absolute_path() {
        let err = data_dir_override_from(Some("relative/path")).expect_err("relative rejected");
        assert_eq!(err.kind(), io::ErrorKind::InvalidInput);

        assert!(data_dir_override_from(None).expect("none").is_none());
        assert!(data_dir_override_from(Some("")).expect("empty").is_none());
        assert!(data_dir_override_from(Some("   "))
            .expect("blank")
            .is_none());
    }

    #[test]
    fn runtime_env_data_dir_override_wins_over_profile() {
        let _guard = env_lock().lock().expect("env lock");
        let root = unique_test_root("env-override");
        let override_dir = root.join("ci-sandbox");
        std::fs::create_dir_all(&override_dir).expect("create override dir");

        std::env::set_var(ENV_DATA_DIR, &override_dir);
        std::env::set_var(ENV_STORAGE_PROFILE, "dev");

        let paths = resolve_unfour_paths().expect("resolve paths");
        assert_eq!(paths.product_data_dir, override_dir);
        assert_eq!(
            paths.database_path,
            override_dir.join(DEFAULT_DATABASE_FILE)
        );

        std::env::remove_var(ENV_DATA_DIR);
        std::env::remove_var(ENV_STORAGE_PROFILE);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn runtime_env_storage_profile_dev_selects_sibling_dir() {
        let _guard = env_lock().lock().expect("env lock");
        std::env::remove_var(ENV_DATA_DIR);
        std::env::set_var(ENV_STORAGE_PROFILE, "dev");

        let paths = resolve_unfour_paths().expect("resolve paths");
        assert_eq!(
            paths.product_data_dir.file_name().unwrap(),
            DEV_PRODUCT_DATA_DIR
        );
        assert_ends_with(
            &paths.database_path,
            &[DEV_PRODUCT_DATA_DIR, DEFAULT_DATABASE_FILE],
        );
        assert_eq!(resolve_storage_profile(), StorageProfile::Dev);

        std::env::remove_var(ENV_STORAGE_PROFILE);
    }

    #[test]
    fn runtime_env_storage_profile_test_selects_sibling_dir() {
        let _guard = env_lock().lock().expect("env lock");
        std::env::remove_var(ENV_DATA_DIR);
        std::env::set_var(ENV_STORAGE_PROFILE, "test");

        let paths = resolve_unfour_paths().expect("resolve paths");
        assert_eq!(
            paths.product_data_dir.file_name().unwrap(),
            TEST_PRODUCT_DATA_DIR
        );
        assert_ends_with(
            &paths.database_path,
            &[TEST_PRODUCT_DATA_DIR, DEFAULT_DATABASE_FILE],
        );
        assert_eq!(resolve_storage_profile(), StorageProfile::Test);

        std::env::remove_var(ENV_STORAGE_PROFILE);
    }

    #[test]
    fn runtime_env_storage_profile_stable_selects_stable_dir() {
        let _guard = env_lock().lock().expect("env lock");
        std::env::remove_var(ENV_DATA_DIR);
        std::env::set_var(ENV_STORAGE_PROFILE, "stable");

        let paths = resolve_unfour_paths().expect("resolve paths");
        assert_eq!(
            paths.product_data_dir.file_name().unwrap(),
            DEFAULT_PRODUCT_DATA_DIR
        );
        assert_eq!(resolve_storage_profile(), StorageProfile::Stable);

        std::env::remove_var(ENV_STORAGE_PROFILE);
    }

    #[test]
    fn runtime_env_invalid_storage_profile_returns_clear_error() {
        let _guard = env_lock().lock().expect("env lock");
        std::env::remove_var(ENV_DATA_DIR);
        std::env::set_var(ENV_STORAGE_PROFILE, "nightly");

        let error = resolve_unfour_paths().expect_err("invalid profile must fail");
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
        assert!(error.to_string().contains("UNFOUR_STORAGE_PROFILE"));

        std::env::remove_var(ENV_STORAGE_PROFILE);
    }

    #[test]
    fn initialize_creates_storage_directories_without_creating_database() {
        let root = unique_test_root("create-dirs");
        let roots = PathRoots::new(
            root.join("data"),
            Some(root.join("config")),
            Some(root.join("cache")),
        );

        let paths =
            initialize_with_roots(&roots, StorageProfile::Stable).expect("initialize storage");

        assert!(paths.product_data_dir.is_dir());
        assert!(paths.config_dir.is_dir());
        assert!(paths.cache_dir.is_dir());
        assert!(paths.backups_dir.is_dir());
        assert!(!paths.database_path.exists());

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn diagnostics_reports_storage_state() {
        let root = unique_test_root("diagnostics");
        let roots = PathRoots::new(
            root.join("data"),
            Some(root.join("config")),
            Some(root.join("cache")),
        );
        let diagnostics =
            diagnostics_with_roots(&roots, StorageProfile::Stable).expect("diagnostics");

        let StorageDiagnostics {
            product_data_dir,
            database_path,
            config_dir,
            cache_dir,
            backups_dir,
            logs_dir,
            diagnostics_dir,
            database_exists,
            current_exe,
            current_working_dir,
        } = diagnostics;

        assert_ends_with(
            &database_path,
            &[DEFAULT_PRODUCT_DATA_DIR, DEFAULT_DATABASE_FILE],
        );
        assert_eq!(
            product_data_dir,
            root.join("data").join(DEFAULT_PRODUCT_DATA_DIR)
        );
        assert_eq!(
            config_dir,
            root.join("config").join(DEFAULT_PRODUCT_DATA_DIR)
        );
        assert_eq!(cache_dir, root.join("cache").join(DEFAULT_PRODUCT_DATA_DIR));
        assert_eq!(backups_dir, product_data_dir.join("backups"));
        assert_eq!(logs_dir, product_data_dir.join("logs"));
        assert_eq!(diagnostics_dir, product_data_dir.join("diagnostics"));
        assert!(!database_exists);
        let _ = current_exe;
        let _ = current_working_dir;

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn resolve_includes_logs_and_diagnostics_under_product_data_dir() {
        let root = unique_test_root("diag-dirs");
        let roots = PathRoots::new(
            root.join("data"),
            Some(root.join("config")),
            Some(root.join("cache")),
        );

        let paths = resolve_with_roots(&roots, StorageProfile::Stable).expect("resolve paths");

        assert_eq!(paths.logs_dir, paths.product_data_dir.join("logs"));
        assert_eq!(
            paths.diagnostics_dir,
            paths.product_data_dir.join("diagnostics")
        );

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn initialize_creates_logs_and_diagnostics_directories() {
        let root = unique_test_root("create-diag-dirs");
        let roots = PathRoots::new(
            root.join("data"),
            Some(root.join("config")),
            Some(root.join("cache")),
        );

        let paths =
            initialize_with_roots(&roots, StorageProfile::Stable).expect("initialize storage");

        assert!(paths.logs_dir.is_dir());
        assert!(paths.diagnostics_dir.is_dir());

        let _ = std::fs::remove_dir_all(root);
    }
}
