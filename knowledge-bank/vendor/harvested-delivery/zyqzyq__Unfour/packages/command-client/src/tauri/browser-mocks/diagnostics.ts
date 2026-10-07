import { UNHANDLED, type MockResult } from "./types";

export function handleDiagnosticsMock<T>(command: string): MockResult<T> {
  if (command === "system_health") {
    return {
      appName: "Unfour",
      storageReady: true,
      commandBusReady: true,
      aiReservedCapabilities: ["api.send_request", "ssh.connect.reserved"],
    } as T;
  }

  if (command === "open_log_dir" || command === "open_diagnostics_dir") {
    return undefined as T;
  }

  if (command === "export_diagnostics_bundle") {
    return {
      bundleDir: "mock-diagnostics",
      manifestPath: "mock-diagnostics/manifest.json",
    } as T;
  }

  return UNHANDLED;
}
