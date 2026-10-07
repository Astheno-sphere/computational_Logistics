import type { SshConnection } from "@unfour/command-client";
import { describe, expect, it } from "vitest";
import {
  defaultSshConnectionInput,
  sshConnectionToInput,
  sshEndpointLabel,
} from "./ssh-connection-state";

function connection(overrides: Partial<SshConnection> = {}): SshConnection {
  return {
    id: "conn-1",
    workspaceId: "ws-1",
    name: "Prod",
    host: "10.0.0.1",
    port: 2222,
    username: "ops",
    authKind: "private-key",
    keyPath: "/keys/id_ed25519",
    credentialRef: "cred-1",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    deletedAt: null,
    revision: 1,
    syncStatus: "synced",
    remoteId: null,
    ...overrides,
  };
}

describe("defaultSshConnectionInput", () => {
  it("carries the workspace id and password auth defaults", () => {
    const input = defaultSshConnectionInput("ws-9");
    expect(input.workspaceId).toBe("ws-9");
    expect(input.authKind).toBe("password");
    expect(input.port).toBe(22);
    expect(input.credentialRef).toBeNull();
  });
});

describe("sshConnectionToInput", () => {
  it("maps a stored connection back into an editable input", () => {
    const input = sshConnectionToInput(connection(), "ws-2");
    expect(input).toMatchObject({
      id: "conn-1",
      workspaceId: "ws-2",
      name: "Prod",
      host: "10.0.0.1",
      port: 2222,
      username: "ops",
      authKind: "private-key",
      keyPath: "/keys/id_ed25519",
      credentialRef: "cred-1",
    });
  });
});

describe("sshEndpointLabel", () => {
  it("formats user@host for a connection", () => {
    expect(sshEndpointLabel(connection({ username: "deploy", host: "box" }))).toBe(
      "deploy@box",
    );
  });

  it("returns a placeholder when there is no connection", () => {
    expect(sshEndpointLabel(null)).toBe("No SSH connection");
    expect(sshEndpointLabel(undefined)).toBe("No SSH connection");
  });
});
