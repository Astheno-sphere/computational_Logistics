import { call } from "./invoke";
import type { DiagnosticBundleResult, SystemHealth } from "../types";

export function getSystemHealth() {
  return call<SystemHealth>("system_health");
}

export function openLogDir() {
  return call<void>("open_log_dir");
}

export function openDiagnosticsDir() {
  return call<void>("open_diagnostics_dir");
}

export function exportDiagnosticsBundle() {
  return call<DiagnosticBundleResult>("export_diagnostics_bundle");
}
