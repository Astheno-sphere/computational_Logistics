/** Return the retained frame active at a shared timeline cursor position. */
export function selectTimelineFrame(frames, selectedMs) {
  if (!Array.isArray(frames) || !frames.length || !Number.isFinite(selectedMs)) return null;
  let low = 0;
  let high = frames.length - 1;
  let candidateIndex = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const start = Date.parse(String(frames[middle]?.start_at || ''));
    if (!Number.isFinite(start) || start > selectedMs) {
      high = middle - 1;
    } else {
      candidateIndex = middle;
      low = middle + 1;
    }
  }
  if (candidateIndex < 0) return null;
  const candidate = frames[candidateIndex];
  const end = Date.parse(String(candidate?.end_at || ''));
  return !Number.isFinite(end) || selectedMs < end ? candidate : null;
}
