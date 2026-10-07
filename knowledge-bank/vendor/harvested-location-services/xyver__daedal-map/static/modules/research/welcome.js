export function buildResearchFriendlyWelcomeMessage() {
  return 'Welcome to Research. Use this mode for bounded analysis over a saved corpus: rankings, comparisons, summaries, and evidence-backed findings that stay tied to a defined workspace.<br><br>Good first asks are "rank the highest-risk counties in this corpus", "compare these two regions", or "summarize the strongest patterns you see".';
}

export function buildResearchWelcomeMessage(manifest, fallbackMessage) {
  if ((manifest?.artifact_count || 0) > 0 && !manifest?.stale_artifacts) {
    return `Active corpus has ${manifest.artifact_count} loaded artifact${manifest.artifact_count === 1 ? '' : 's'}. Ask for rankings, comparisons, summaries, or map-backed evidence from this workspace.`;
  }

  if (manifest?.saved_corpus) {
    const saved = manifest.saved_corpus;
    if (manifest?.stale_artifacts) {
      return `"${saved.name}" is selected, but it is out of date in this local session. Click Load Data to refresh the corpus, then ask bounded analytical questions about it.`;
    }
    return `"${saved.name}" is selected. Click Load Data to activate it for this session, then ask for rankings, comparisons, or evidence-backed findings.`;
  }

  return fallbackMessage;
}
