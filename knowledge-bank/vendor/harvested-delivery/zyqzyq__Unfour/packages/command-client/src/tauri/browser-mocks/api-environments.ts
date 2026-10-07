import {
  assertMockEnvironmentNameAvailable,
  mockEnvList,
  mockState,
  mockStore,
} from "./state";
import { UNHANDLED, type MockResult } from "./types";
import type { ApiEnvironment, KeyValue } from "../../types";

export function handleApiEnvironmentMock<T>(
  command: string,
  args?: Record<string, unknown>,
): MockResult<T> {
  if (command === "api_environments_list") {
    const workspaceId = String(args?.workspaceId ?? mockState.activeWorkspaceId);
    return mockEnvList(workspaceId) as T;
  }

  if (command === "api_environment_create") {
    const workspaceId = String(args?.workspaceId ?? mockState.activeWorkspaceId);
    const name = String(args?.name ?? "New Environment").trim() || "New Environment";
    assertMockEnvironmentNameAvailable(workspaceId, name);
    const isActive = mockEnvList(workspaceId).length === 0;
    const now = new Date().toISOString();
    const environment: ApiEnvironment = {
      id: crypto.randomUUID(),
      workspaceId,
      name,
      variables: [],
      isActive,
      createdAt: now,
      updatedAt: now,
    };
    mockStore.environments = [...mockStore.environments, environment];
    return environment as T;
  }

  if (command === "api_environment_update") {
    const workspaceId = String(args?.workspaceId ?? mockState.activeWorkspaceId);
    const environmentId = String(args?.environmentId ?? "");
    const environment = mockStore.environments.find(
      (env) => env.workspaceId === workspaceId && env.id === environmentId,
    );
    if (!environment) throw new Error("api environment not found");
    const name = String(args?.name ?? environment.name).trim() || environment.name;
    assertMockEnvironmentNameAvailable(workspaceId, name, environmentId);
    environment.name = name;
    environment.variables = (args?.variables as KeyValue[]) ?? [];
    environment.updatedAt = new Date().toISOString();
    return environment as T;
  }

  if (command === "api_environment_delete") {
    const workspaceId = String(args?.workspaceId ?? mockState.activeWorkspaceId);
    const environmentId = String(args?.environmentId ?? "");
    mockStore.environments = mockStore.environments.filter(
      (env) => !(env.workspaceId === workspaceId && env.id === environmentId),
    );
    return mockEnvList(workspaceId) as T;
  }

  if (command === "api_environment_activate") {
    const workspaceId = String(args?.workspaceId ?? mockState.activeWorkspaceId);
    const environmentId = args?.environmentId ? String(args.environmentId) : null;
    mockStore.environments = mockStore.environments.map((env) =>
      env.workspaceId === workspaceId
        ? { ...env, isActive: env.id === environmentId }
        : env,
    );
    return mockEnvList(workspaceId) as T;
  }

  return UNHANDLED;
}
