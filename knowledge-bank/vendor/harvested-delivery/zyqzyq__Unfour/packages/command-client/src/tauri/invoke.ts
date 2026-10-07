import { invoke } from "@tauri-apps/api/core";
import { logCommandFailure } from "../logger";
import { mockInvoke } from "./browser-mocks";

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauriRuntime() {
  return typeof window !== "undefined" && Boolean(window.__TAURI_INTERNALS__);
}

export async function call<T>(
  command: string,
  args?: Record<string, unknown>,
): Promise<T> {
  if (!isTauriRuntime()) {
    try {
      return await mockInvoke<T>(command, args);
    } catch (error) {
      void logCommandFailure(command, error);
      throw error;
    }
  }

  try {
    return await invoke<T>(command, args);
  } catch (error) {
    void logCommandFailure(command, error);
    throw error;
  }
}
