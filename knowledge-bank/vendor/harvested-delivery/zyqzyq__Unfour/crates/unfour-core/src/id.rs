use uuid::Uuid;

/// Generate a time-ordered (UUID v7) identifier string.
///
/// UUID v7 embeds a Unix-timestamp prefix, so generated ids sort
/// chronologically. This keeps inserts localized within B-tree indexes
/// (both SQLite and Postgres) and makes `ORDER BY id` approximate creation
/// order. Every persisted entity id should be minted through this function so
/// that offline clients and the server agree on the id shape and ordering.
pub fn new_id() -> String {
    Uuid::now_v7().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn new_id_mints_uuid_v7() {
        let id = new_id();
        let parsed = Uuid::parse_str(&id).expect("new_id must produce a valid UUID");
        assert_eq!(
            parsed.get_version_num(),
            7,
            "new_id must mint a UUID v7 (time-ordered) identifier"
        );
    }

    #[test]
    fn new_id_is_unique_and_chronological() {
        let first = new_id();
        let second = new_id();
        assert_ne!(first, second, "two minted ids must not collide");
        assert!(
            first < second,
            "UUID v7 ids must sort chronologically by creation time"
        );
    }
}
