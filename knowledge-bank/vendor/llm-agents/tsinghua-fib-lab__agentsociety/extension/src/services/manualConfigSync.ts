export type ManualConfigSyncMode = 'direct' | 'gateway';

export function shouldShowProviderModelConfiguration(_isNew: boolean): boolean {
  return true;
}

export function resolveManualConfigSyncMode(
  routedViaGateway: boolean,
  gatewayRunning: boolean
): ManualConfigSyncMode {
  if (!routedViaGateway) {
    return 'direct';
  }
  if (!gatewayRunning) {
    throw new Error('gateway_not_running');
  }
  return 'gateway';
}
