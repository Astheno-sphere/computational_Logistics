import { handleApiCollectionMock } from "./api-collections";
import { handleApiEnvironmentMock } from "./api-environments";
import { handleApiRequestMock } from "./api-requests";
import { UNHANDLED, type MockCommandHandler } from "./types";

const apiMockHandlers: MockCommandHandler[] = [
  handleApiEnvironmentMock,
  handleApiCollectionMock,
  handleApiRequestMock,
];

export async function handleApiMock<T>(
  command: string,
  args?: Record<string, unknown>,
): Promise<T | typeof UNHANDLED> {
  for (const handler of apiMockHandlers) {
    const result = await handler<T>(command, args);
    if (result !== UNHANDLED) {
      return result;
    }
  }

  return UNHANDLED;
}
