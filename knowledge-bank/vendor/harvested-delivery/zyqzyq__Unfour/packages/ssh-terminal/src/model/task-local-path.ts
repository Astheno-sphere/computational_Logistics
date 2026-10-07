/** Last path segment if it looks like a file name (extension or {{placeholder}}). */
export function fileNameFromPath(path: string): string | null {
  const trimmed = path.trim().replace(/[/\\]+$/, "");
  if (!trimmed) return null;
  const parts = trimmed.split(/[/\\]/).filter(Boolean);
  const last = parts[parts.length - 1] ?? "";
  if (!last || /^[A-Za-z]:$/.test(last)) return null;
  if (last.includes(".") || last.includes("{{") || last.includes("}}")) {
    return last;
  }
  return null;
}

/** Join a directory and file name using the separator style of the directory. */
export function joinLocalPath(directory: string, fileName: string): string {
  const dir = directory.trim().replace(/[/\\]+$/, "");
  const name = fileName.trim().replace(/^[/\\]+/, "");
  if (!dir) return name;
  if (!name) return dir;
  const separator = dir.includes("\\") && !dir.includes("/") ? "\\" : "/";
  return `${dir}${separator}${name}`;
}

/**
 * When the user browses a download output folder, keep an existing file name
 * (from the current local path or remote path) instead of replacing the path
 * with a bare directory that the download step would treat as a file.
 */
export function downloadPathFromDirectory(
  directory: string,
  currentLocalPath: string,
  remotePath = "",
): string {
  const fileName =
    fileNameFromPath(currentLocalPath) ??
    fileNameFromPath(remotePath) ??
    "{{filename}}";
  return joinLocalPath(directory, fileName);
}
