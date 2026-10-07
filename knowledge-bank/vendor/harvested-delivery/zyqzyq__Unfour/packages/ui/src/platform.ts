import { useState } from "react";

export type Platform = "macos" | "windows" | "linux" | "unknown";

function detectPlatform(): Platform {
  if (typeof navigator === "undefined") {
    return "unknown";
  }
  const signature = `${navigator.platform ?? ""} ${navigator.userAgent ?? ""}`.toLowerCase();
  if (signature.includes("mac")) return "macos";
  if (signature.includes("win")) return "windows";
  if (signature.includes("linux") || signature.includes("x11")) return "linux";
  return "unknown";
}

/**
 * Returns the current OS platform. Used to branch UI that must differ per OS
 * (e.g. the macOS traffic lights vs custom window controls).
 */
export function usePlatform(): Platform {
  const [platform] = useState<Platform>(detectPlatform);
  return platform;
}
