import * as fs from 'fs';
import * as path from 'path';
import { execFileSync } from 'child_process';

const AGENTSOCIETY2_CHECK = [
  'import importlib.util',
  'import sys',
  'sys.exit(0 if importlib.util.find_spec("agentsociety2") else 1)',
].join(';');

const INSPECT_SCRIPT = `
import importlib.util
import json
import sys

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    from importlib_metadata import PackageNotFoundError, version

spec = importlib.util.find_spec("agentsociety2")
payload = {
    "pythonVersion": sys.version.split()[0],
    "compatible": spec is not None,
    "as2Version": None,
}
if spec is not None:
    try:
        payload["as2Version"] = version("agentsociety2")
    except PackageNotFoundError:
        pass
print(json.dumps(payload))
`.trim();

export type PythonEnvironmentSource =
  | 'configured'
  | 'workspace-venv'
  | 'parent-venv'
  | 'sdk-venv'
  | 'uv'
  | 'virtual-env'
  | 'system';

export type ResolveAgentsocietyPythonOptions = {
  configuredPath?: string;
  workspacePath?: string;
  extensionPath?: string;
};

export type PythonEnvironmentCandidate = {
  path: string;
  source: PythonEnvironmentSource;
  compatible: boolean;
  pythonVersion?: string;
  as2Version?: string;
  error?: string;
};

type CandidateEntry = {
  path: string;
  source: PythonEnvironmentSource;
};

function isExecutableFile(filePath: string): boolean {
  try {
    return fs.existsSync(filePath) && fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

export function venvPythonIn(baseDir: string): string | null {
  const unix = path.join(baseDir, '.venv', 'bin', 'python');
  if (isExecutableFile(unix)) {
    return unix;
  }
  const win = path.join(baseDir, '.venv', 'Scripts', 'python.exe');
  if (isExecutableFile(win)) {
    return win;
  }
  return null;
}

function execPython(pythonPath: string, args: string[]): string | null {
  try {
    return execFileSync(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 20_000,
      env: process.env,
    })
      .toString()
      .trim();
  } catch (error) {
    const stderr =
      error && typeof error === 'object' && 'stderr' in error
        ? String((error as { stderr?: Buffer }).stderr ?? '')
        : '';
    const stdout =
      error && typeof error === 'object' && 'stdout' in error
        ? String((error as { stdout?: Buffer }).stdout ?? '')
        : '';
    return (stdout || stderr || null)?.trim() || null;
  }
}

export function pythonHasAgentsociety2(pythonPath: string): boolean {
  const trimmed = pythonPath.trim();
  if (!trimmed) {
    return false;
  }
  try {
    execFileSync(trimmed, ['-c', AGENTSOCIETY2_CHECK], {
      stdio: 'ignore',
      timeout: 20_000,
      env: process.env,
    });
    return true;
  } catch {
    return false;
  }
}

function inspectPythonEnvironment(pythonPath: string): Omit<PythonEnvironmentCandidate, 'path' | 'source'> {
  const output = execPython(pythonPath, ['-c', INSPECT_SCRIPT]);
  if (!output) {
    return { compatible: false, error: 'python_unavailable' };
  }
  try {
    const parsed = JSON.parse(output) as {
      pythonVersion?: string;
      compatible?: boolean;
      as2Version?: string | null;
    };
    return {
      compatible: parsed.compatible === true,
      pythonVersion: parsed.pythonVersion,
      as2Version: parsed.as2Version ?? undefined,
    };
  } catch {
    return { compatible: false, error: 'inspect_failed' };
  }
}

function resolveUvPython(workspacePath?: string, extensionPath?: string): string | null {
  const roots: string[] = [];
  if (workspacePath) {
    roots.push(workspacePath);
    let dir = workspacePath;
    for (let depth = 0; depth < 4; depth += 1) {
      roots.push(dir);
      const parent = path.dirname(dir);
      if (parent === dir) {
        break;
      }
      dir = parent;
    }
  }
  if (extensionPath) {
    roots.push(path.resolve(extensionPath, '..'));
    roots.push(path.resolve(extensionPath, '..', '..'));
  }

  for (const root of roots) {
    const hasUvProject =
      fs.existsSync(path.join(root, 'pyproject.toml')) &&
      (fs.existsSync(path.join(root, 'uv.lock')) || fs.existsSync(path.join(root, '.venv')));
    if (!hasUvProject) {
      continue;
    }
    try {
      const output = execFileSync('uv', ['run', 'python', '-c', 'import sys; print(sys.executable)'], {
        cwd: root,
        stdio: ['ignore', 'pipe', 'ignore'],
        timeout: 20_000,
        env: process.env,
      })
        .toString()
        .trim();
      if (output) {
        return output;
      }
    } catch {
      // try next root
    }
  }
  return null;
}

function collectCandidateEntries(options: ResolveAgentsocietyPythonOptions): CandidateEntry[] {
  const seen = new Set<string>();
  const entries: CandidateEntry[] = [];
  const add = (value: string | undefined | null, source: PythonEnvironmentSource) => {
    const trimmed = value?.trim();
    if (!trimmed || seen.has(trimmed)) {
      return;
    }
    seen.add(trimmed);
    entries.push({ path: trimmed, source });
  };

  if (options.configuredPath?.trim()) {
    add(options.configuredPath, 'configured');
  }

  if (options.workspacePath) {
    const workspaceVenv = venvPythonIn(options.workspacePath);
    if (workspaceVenv) {
      add(workspaceVenv, 'workspace-venv');
    }
    let dir = options.workspacePath;
    for (let depth = 0; depth < 6; depth += 1) {
      const parentVenv = venvPythonIn(dir);
      if (parentVenv && parentVenv !== workspaceVenv) {
        add(parentVenv, 'parent-venv');
      }
      const parent = path.dirname(dir);
      if (parent === dir) {
        break;
      }
      dir = parent;
    }
  }

  if (options.extensionPath) {
    add(venvPythonIn(path.resolve(options.extensionPath, '..')), 'sdk-venv');
    add(venvPythonIn(path.resolve(options.extensionPath, '..', '..')), 'sdk-venv');
  }

  if (process.env.VIRTUAL_ENV) {
    add(path.join(process.env.VIRTUAL_ENV, 'bin', 'python'), 'virtual-env');
    add(path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe'), 'virtual-env');
  }

  add(resolveUvPython(options.workspacePath, options.extensionPath), 'uv');
  add('python3', 'system');
  add('python', 'system');
  return entries;
}

export function listPythonCandidates(options: ResolveAgentsocietyPythonOptions): string[] {
  return collectCandidateEntries(options).map((entry) => entry.path);
}

export function discoverPythonEnvironments(
  options: ResolveAgentsocietyPythonOptions
): PythonEnvironmentCandidate[] {
  const results: PythonEnvironmentCandidate[] = [];
  for (const entry of collectCandidateEntries(options)) {
    const inspected = inspectPythonEnvironment(entry.path);
    results.push({
      path: entry.path,
      source: entry.source,
      ...inspected,
    });
  }
  return results.sort((left, right) => {
    if (left.compatible !== right.compatible) {
      return left.compatible ? -1 : 1;
    }
    const sourceRank: Record<PythonEnvironmentSource, number> = {
      configured: 0,
      'workspace-venv': 1,
      'sdk-venv': 2,
      uv: 3,
      'virtual-env': 4,
      'parent-venv': 5,
      system: 6,
    };
    return sourceRank[left.source] - sourceRank[right.source];
  });
}

export function resolveAgentsocietyPython(
  options: ResolveAgentsocietyPythonOptions
): string | null {
  const compatible = discoverPythonEnvironments(options).find((item) => item.compatible);
  return compatible?.path ?? null;
}
