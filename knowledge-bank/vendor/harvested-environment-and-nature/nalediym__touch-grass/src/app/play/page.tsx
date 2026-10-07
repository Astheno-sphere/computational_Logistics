"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import { getStoredUser, getStoredDashboard } from "@/lib/storage";
import { PlayView } from "@/components/play-view";
import { Onboarding } from "@/components/onboarding";
import type { User } from "@/lib/types";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getClientUser(): User | null {
  return getStoredUser();
}

function getServerUser(): User | null {
  return null;
}

export default function PlayPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const user = useSyncExternalStore(subscribe, getClientUser, getServerUser);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  if (user === null) {
    // Either SSR/hydration (always null on server) or no stored user
    // Show onboarding — the refresh callback will re-read from localStorage
    return <Onboarding onComplete={refresh} />;
  }

  const dashboard = getStoredDashboard()!;
  return <PlayView key={refreshKey} dashboard={dashboard} onRefresh={refresh} />;
}
