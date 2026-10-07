"""Dependency-free geometry edition selection for app and release tools."""


def geometry_edition_projection(release: dict, current: dict) -> dict:
    """Select one downloadable edition without creating a second authority."""
    if release.get("manifest_kind") != "geometry_release_unit":
        raise RuntimeError("Geometry current pointer did not resolve to a geometry release manifest")
    version = str(release.get("version") or "").strip()
    if version != str(current.get("current_version") or "").strip():
        raise RuntimeError("Geometry current pointer and release manifest versions disagree")
    country = str((release.get("release_unit") or {}).get("id") or "").upper()
    if country != str(current.get("country_code") or country).upper():
        raise RuntimeError("Geometry current pointer and release manifest countries disagree")
    edition_name = str(current.get("edition") or "").strip()
    edition = (release.get("editions") or {}).get(edition_name)
    if not isinstance(edition, dict) or edition.get("delivery") != "download":
        raise RuntimeError(f"Geometry release has no downloadable edition: {edition_name}")
    objects = {str(item.get("sha256") or ""): item for item in release.get("objects") or [] if isinstance(item, dict)}
    files = []
    for item in edition.get("files") or []:
        digest = str(item.get("object_sha256") or "")
        source = objects.get(digest)
        if source is None:
            raise RuntimeError(f"Geometry edition references an unknown object: {digest}")
        files.append({"path": item.get("path"), "sha256": digest, "size_bytes": source.get("size_bytes")})
    package_id = str(current.get("package_id") or "").strip()
    if not package_id:
        raise RuntimeError("Geometry current pointer missing package_id")
    return {"pack_id": package_id, "version": version, "published_at": release.get("released_at"), "artifact": edition.get("artifact") or {}, "files": files}
