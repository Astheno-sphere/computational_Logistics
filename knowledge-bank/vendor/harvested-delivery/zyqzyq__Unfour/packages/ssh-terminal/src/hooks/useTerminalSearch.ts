import { useEffect } from "react";
import { useTerminalStore } from "../model/terminal-state";

export function useTerminalSearch() {
  const open = useTerminalStore((state) => state.searchOpen);
  const query = useTerminalStore((state) => state.searchQuery);
  const setOpen = useTerminalStore((state) => state.setSearchOpen);
  const setQuery = useTerminalStore((state) => state.setSearchQuery);

  useEffect(() => {
    function toggleSearch(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape" && open) {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", toggleSearch);

    return () => window.removeEventListener("keydown", toggleSearch);
  }, [open, setOpen]);

  return {
    open,
    query,
    setOpen,
    setQuery,
  };
}
