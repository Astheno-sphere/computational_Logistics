fn main() {
    // Cargo build scripts cannot inject environment variables into dependency
    // crates. Resolve the same process-wide input independently so this crate
    // and the desktop metadata always compile with the same channel.
    let channel = match std::env::var("UNFOUR_RELEASE_CHANNEL") {
        Ok(value) if value.is_empty() => default_test_channel_with_warning(),
        Ok(value) => match value.as_str() {
            "test" | "stable" => value,
            _ => panic!("UNFOUR_RELEASE_CHANNEL must be exactly 'test' or 'stable', got {value:?}"),
        },
        Err(std::env::VarError::NotPresent) => default_test_channel_with_warning(),
        Err(error) => panic!("UNFOUR_RELEASE_CHANNEL is not valid Unicode: {error}"),
    };
    println!("cargo:rustc-env=UNFOUR_RELEASE_CHANNEL={channel}");
    println!("cargo:rerun-if-env-changed=UNFOUR_RELEASE_CHANNEL");
}

fn default_test_channel_with_warning() -> String {
    println!(
        "cargo:warning=UNFOUR_RELEASE_CHANNEL was not provided; defaulting unfour-paths to 'test'. Use root `pnpm tauri ...` or set the variable explicitly."
    );
    "test".to_string()
}
