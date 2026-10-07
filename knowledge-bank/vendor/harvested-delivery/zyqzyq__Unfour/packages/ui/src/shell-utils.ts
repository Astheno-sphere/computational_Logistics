export function clampResizablePaneSize(
  nextSize: number,
  minSize: number,
  maxSize: number,
  currentSize: number,
) {
  if (!Number.isFinite(nextSize)) {
    return currentSize;
  }

  return Math.min(Math.max(nextSize, minSize), maxSize);
}
