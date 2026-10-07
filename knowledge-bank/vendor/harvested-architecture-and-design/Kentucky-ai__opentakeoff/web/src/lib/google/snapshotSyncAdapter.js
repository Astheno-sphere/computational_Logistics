// Adapts google/drive.js to the snapshot-sync provider contract. drive.js
// already exposes exactly the six methods createSnapshotSync needs, so this is
// a thin pick — its job is to DOCUMENT the provider seam and be the single place
// a second backend (OneDrive/O365) would slot in by implementing the same shape.
// drive.js methods are plain closures over getToken/fetch (no `this`), so
// destructuring them here is safe.

/** @param {ReturnType<import("./drive.js").createDrive>} drive */
export function driveSnapshotProvider(drive) {
  const { findChild, createFolder, listChildren, getJson, putJson, deleteFile } = drive;
  return { findChild, createFolder, listChildren, getJson, putJson, deleteFile };
}
