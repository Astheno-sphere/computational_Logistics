import * as path from 'path';

export function filePathToAtReference(workspaceRoot: string | undefined, filePath: string): string {
  const referencePath = (workspaceRoot && path.isAbsolute(filePath)
    ? path.relative(workspaceRoot, filePath)
    : filePath
  ).replace(/\\/g, '/');
  return `@${referencePath}`;
}
