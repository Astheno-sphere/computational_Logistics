export const UNHANDLED = Symbol("unhandled mock command");

export type MockResult<T> = T | typeof UNHANDLED | Promise<T | typeof UNHANDLED>;

export type MockCommandHandler = <T>(
  command: string,
  args?: Record<string, unknown>,
) => MockResult<T>;
