import { useCallback } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { IconButton, Input } from "@unfour/ui";
import { useTerminalSearch } from "../hooks/useTerminalSearch";
import { useTerminalStore } from "../model/terminal-state";

export function TerminalSearchBar() {
  const search = useTerminalSearch();
  const searchAddon = useTerminalStore((s) => s.terminalSearchAddon);

  const handleQueryChange = useCallback(
    (value: string) => {
      search.setQuery(value);
      if (searchAddon && value) {
        searchAddon.findNext(value);
      } else if (searchAddon && !value) {
        searchAddon.clearDecorations();
      }
    },
    [search, searchAddon],
  );

  const findPrevious = useCallback(() => {
    if (searchAddon && search.query) {
      searchAddon.findPrevious(search.query);
    }
  }, [searchAddon, search.query]);

  const findNext = useCallback(() => {
    if (searchAddon && search.query) {
      searchAddon.findNext(search.query);
    }
  }, [searchAddon, search.query]);

  if (!search.open) {
    return null;
  }

  return (
    <div className="absolute right-3 top-3 z-10 flex h-8 max-w-[min(420px,calc(100%-24px))] items-center gap-1 rounded-[var(--u-radius-md)] border border-[var(--u-color-border)] bg-[var(--u-color-surface)] px-1 shadow-sm">
      <Input
        aria-label="Search terminal output"
        autoFocus
        className="h-6 w-52 border-transparent bg-transparent px-1"
        onChange={(event) => handleQueryChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            searchAddon?.clearDecorations();
            search.setOpen(false);
          }
          if (event.key === "Enter") {
            event.shiftKey ? findPrevious() : findNext();
          }
        }}
        placeholder="Search terminal output"
        value={search.query}
      />
      <IconButton
        disabled={!searchAddon || !search.query}
        label="Previous terminal search result"
        onClick={findPrevious}
        size="compact"
      >
        <ChevronUp size={13} />
      </IconButton>
      <IconButton
        disabled={!searchAddon || !search.query}
        label="Next terminal search result"
        onClick={findNext}
        size="compact"
      >
        <ChevronDown size={13} />
      </IconButton>
      <IconButton
        label="Close terminal search"
        onClick={() => {
          searchAddon?.clearDecorations();
          search.setOpen(false);
        }}
        size="compact"
      >
        <X size={13} />
      </IconButton>
    </div>
  );
}
