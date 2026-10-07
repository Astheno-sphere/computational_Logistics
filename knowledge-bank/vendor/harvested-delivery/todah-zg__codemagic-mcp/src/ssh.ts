import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const execFileAsync = promisify(execFile);

const EXEC_BUFFER = 32 * 1024 * 1024;
const CLI_TIMEOUT_MS = 30_000;

export interface SSHKeyPair {
  /** Raw OpenSSH private key (PEM) — base64-encode before sending to Codemagic API */
  privateKey: string;
  /** OpenSSH public key (`ssh-ed25519 AAAA...`) — safe to share; used for deploy key registration */
  publicKey: string;
}

/**
 * Generate a fresh Ed25519 SSH key pair using ssh-keygen.
 * Keys are written to a temp directory and deleted after reading.
 */
export async function generateSSHKeyPair(): Promise<SSHKeyPair> {
  const tempDir = await mkdtemp(join(tmpdir(), "cm-keygen-"));
  const keyPath = join(tempDir, "deploy_key");
  try {
    await execFileAsync("ssh-keygen", [
      "-t", "ed25519",
      "-f", keyPath,
      "-N", "",                   // no passphrase
      "-q",                       // quiet
      "-C", "codemagic-deploy-key",
    ], { timeout: CLI_TIMEOUT_MS });

    const [privateKey, publicKey] = await Promise.all([
      readFile(keyPath, "utf8"),
      readFile(`${keyPath}.pub`, "utf8"),
    ]);
    return { privateKey: privateKey.trim(), publicKey: publicKey.trim() };
  } finally {
    await rm(tempDir, { recursive: true, force: true }).catch(() => {});
  }
}

/**
 * Parse the GitHub owner and repo name from an SSH or HTTPS GitHub URL.
 * Returns null if the URL is not a recognisable GitHub URL.
 */
export function parseGitHubRepo(repoUrl: string): { owner: string; repo: string } | null {
  // git@github.com:owner/repo.git
  const ssh = repoUrl.match(/git@github\.com:([^/]+)\/([^/.]+?)(?:\.git)?$/);
  if (ssh) return { owner: ssh[1], repo: ssh[2] };

  // ssh://git@github.com/owner/repo.git
  const sshProto = repoUrl.match(/ssh:\/\/git@github\.com\/([^/]+)\/([^/.]+?)(?:\.git)?$/);
  if (sshProto) return { owner: sshProto[1], repo: sshProto[2] };

  // https://github.com/owner/repo.git
  const https = repoUrl.match(/https:\/\/github\.com\/([^/]+)\/([^/.]+?)(?:\.git)?$/);
  if (https) return { owner: https[1], repo: https[2] };

  return null;
}

export interface DeployKeyResult {
  added: boolean;
  method: "gh-cli" | "manual";
  message: string;
}

/**
 * Attempt to add a deploy key to a GitHub repo using the gh CLI.
 * Falls back to manual instructions if gh is absent or not authenticated.
 */
export async function addGitHubDeployKey(
  owner: string,
  repo: string,
  publicKey: string,
): Promise<DeployKeyResult> {
  // Check gh is present and authenticated — exit 0 means authenticated
  try {
    await execFileAsync("gh", ["auth", "status"], { timeout: CLI_TIMEOUT_MS });
  } catch {
    return {
      added: false,
      method: "manual",
      message: manualGitHubInstructions(owner, repo, publicKey),
    };
  }

  // Add the deploy key via the GitHub API
  try {
    await execFileAsync("gh", [
      "api", `repos/${owner}/${repo}/keys`,
      "--method", "POST",
      "--field", "title=Codemagic Deploy Key",
      "--field", `key=${publicKey}`,
      "--field", "read_only=true",
    ], { maxBuffer: EXEC_BUFFER, timeout: CLI_TIMEOUT_MS });
    return {
      added: true,
      method: "gh-cli",
      message: `Deploy key added to ${owner}/${repo} automatically via the gh CLI.`,
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return {
      added: false,
      method: "manual",
      message: `gh CLI call failed (${detail.slice(0, 120)}). ` + manualGitHubInstructions(owner, repo, publicKey),
    };
  }
}

function manualGitHubInstructions(owner: string, repo: string, publicKey: string): string {
  return [
    "Add the public key as a deploy key on your repository:",
    `  1. Open https://github.com/${owner}/${repo}/settings/keys`,
    `  2. Click "Add deploy key"`,
    `  3. Title: Codemagic Deploy Key`,
    `  4. Key (paste exactly):`,
    `     ${publicKey}`,
    `  5. Leave "Allow write access" unchecked, then click "Add key"`,
  ].join("\n");
}

/** Generic instructions for non-GitHub SSH hosts (GitLab, Bitbucket, self-hosted). */
export function manualGenericInstructions(publicKey: string): string {
  return [
    "Add the public key as a deploy key on your Git provider:",
    "",
    `  ${publicKey}`,
    "",
    "  GitLab:    Settings → Repository → Deploy Keys",
    "  Bitbucket: Repository Settings → Access keys",
    "  Other:     Check your provider's SSH deploy key documentation",
  ].join("\n");
}
