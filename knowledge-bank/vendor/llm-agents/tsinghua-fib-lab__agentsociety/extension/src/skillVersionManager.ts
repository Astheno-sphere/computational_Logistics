/**
 * Skill Version Manager
 *
 * Manages versioned built-in `agentsociety-*` skills:
 * - Bundled versions live at `extension/skills/<skill>/<version>/`
 * - User snapshots live at `~/.agentsociety/skill-versions/<skill>/<tag>/`
 * - Workspace presets stored at `<workspace>/.agentsociety/skill-presets.json`
 * - Active preset is realized by symlinking `.claude/skills/<skill>` → resolved version dir
 *
 * Office skills (docx/pdf/pptx/xlsx) are NOT versioned — flat copies via copyOfficialOfficeSkills.
 * Analysis support bundles (e.g. frontend-design) ship inside
 * `agentsociety-analysis/<version>/support/` and appear in the workspace via the
 * agentsociety-analysis skill symlink — not as separate `.claude/skills` peers.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { getMainOutputChannel } from './shared/outputChannels';

const SKILL_PREFIX = 'agentsociety-';
const PRESETS_RELATIVE = path.join('.agentsociety', 'skill-presets.json');
const SNAPSHOT_ROOT_REL = path.join('.agentsociety', 'skill-versions');

export type VersionSource = 'bundled' | 'snapshot';

export interface SkillVersionRef {
  source: VersionSource;
  version?: string;
  tag?: string;
}

export interface SkillVersionInfo {
  id: string;
  label?: string;
  addedIn?: string;
  source: VersionSource;
}

export interface SkillManifest {
  defaultVersion: string;
  versions: Array<{ id: string; label?: string; addedIn?: string }>;
}

export interface SkillPresetMap {
  [skillName: string]: SkillVersionRef;
}

export interface SkillPresetsFile {
  active: string;
  presets: { [presetName: string]: SkillPresetMap };
}

export interface ApplyResult {
  preset: string;
  applied: Array<{ skill: string; ref: SkillVersionRef; mode: 'symlink' | 'copy' }>;
  fallbacks: string[]; // skills that fell back to defaultVersion (no entry in preset)
  errors: Array<{ skill: string; message: string }>;
}

const DEFAULT_PRESET_NAME = 'default';

export class SkillVersionManager {
  private readonly extensionPath: string;
  private readonly skillsSourcePath: string;
  private readonly outputChannel: vscode.OutputChannel;
  private symlinkFailureWarned = false;

  constructor(context: vscode.ExtensionContext, outputChannel?: vscode.OutputChannel) {
    this.extensionPath = context.extensionPath;
    this.skillsSourcePath = path.join(this.extensionPath, 'skills');
    this.outputChannel =
      outputChannel ?? getMainOutputChannel();
  }

  // ============ Identification ============

  static isVersioned(skillName: string): boolean {
    return skillName.startsWith(SKILL_PREFIX);
  }

  /** All `agentsociety-*` skills present in the extension bundle (with manifest.json). */
  listManagedSkills(): string[] {
    if (!fs.existsSync(this.skillsSourcePath)) {
      return [];
    }
    const result: string[] = [];
    for (const name of fs.readdirSync(this.skillsSourcePath)) {
      if (!SkillVersionManager.isVersioned(name)) {
        continue;
      }
      const dir = path.join(this.skillsSourcePath, name);
      try {
        if (!fs.statSync(dir).isDirectory()) {
          continue;
        }
        if (fs.existsSync(path.join(dir, 'manifest.json'))) {
          result.push(name);
        }
      } catch {
        /* skip unreadable */
      }
    }
    return result.sort();
  }

  // ============ Manifest / Versions ============

  readManifest(skillName: string): SkillManifest | null {
    const manifestPath = path.join(this.skillsSourcePath, skillName, 'manifest.json');
    if (!fs.existsSync(manifestPath)) {
      return null;
    }
    try {
      const raw = fs.readFileSync(manifestPath, 'utf-8');
      const data = JSON.parse(raw);
      if (typeof data?.defaultVersion !== 'string' || !Array.isArray(data?.versions)) {
        return null;
      }
      return data as SkillManifest;
    } catch (e) {
      this.log(`Failed to read manifest for ${skillName}: ${(e as Error).message}`);
      return null;
    }
  }

  listBundledVersions(skillName: string): SkillVersionInfo[] {
    const manifest = this.readManifest(skillName);
    if (!manifest) {
      return [];
    }
    return manifest.versions.map((v) => ({
      id: v.id,
      label: v.label,
      addedIn: v.addedIn,
      source: 'bundled' as const,
    }));
  }

  defaultVersion(skillName: string): string | null {
    return this.readManifest(skillName)?.defaultVersion ?? null;
  }

  // ============ Snapshots ============

  private snapshotRoot(): string {
    const home = os.homedir();
    return path.join(home, SNAPSHOT_ROOT_REL);
  }

  private snapshotSkillDir(skillName: string): string {
    return path.join(this.snapshotRoot(), skillName);
  }

  listSnapshots(skillName: string): SkillVersionInfo[] {
    const dir = this.snapshotSkillDir(skillName);
    if (!fs.existsSync(dir)) {
      return [];
    }
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      const out: SkillVersionInfo[] = [];
      for (const e of entries) {
        if (!e.isDirectory() || e.name.startsWith('.')) {
          continue;
        }
        const stat = fs.statSync(path.join(dir, e.name));
        out.push({
          id: e.name,
          label: `Snapshot · ${stat.mtime.toISOString().slice(0, 10)}`,
          source: 'snapshot',
        });
      }
      return out.sort((a, b) => a.id.localeCompare(b.id));
    } catch {
      return [];
    }
  }

  countSnapshots(skillName: string): number {
    return this.listSnapshots(skillName).length;
  }

  /** Take a snapshot of the skill currently realized at `.claude/skills/<skill>/`. */
  createSnapshot(workspacePath: string, skillName: string, tag: string): { success: boolean; message: string; path?: string } {
    if (!SkillVersionManager.isVersioned(skillName)) {
      return { success: false, message: `不在版本管理范围: ${skillName}` };
    }
    const trimmed = tag.trim();
    if (!trimmed || !/^[A-Za-z0-9._-]+$/.test(trimmed)) {
      return { success: false, message: `tag 非法（仅允许字母/数字/. _ -）: ${tag}` };
    }
    const liveDir = path.join(workspacePath, '.claude', 'skills', skillName);
    if (!fs.existsSync(liveDir)) {
      return { success: false, message: `未找到 .claude/skills/${skillName}/，请先应用一个 preset 再快照` };
    }

    const realLive = this.resolveSymlink(liveDir);
    const targetDir = path.join(this.snapshotSkillDir(skillName), trimmed);
    if (fs.existsSync(targetDir)) {
      return { success: false, message: `快照 tag 已存在: ${trimmed}` };
    }

    try {
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });
      copyDirectoryRecursive(realLive, targetDir);
      return { success: true, message: `已生成快照: ${targetDir}`, path: targetDir };
    } catch (e) {
      return { success: false, message: `快照失败: ${(e as Error).message}` };
    }
  }

  // ============ Path resolution ============

  resolveVersionPath(skillName: string, ref: SkillVersionRef): string | null {
    if (ref.source === 'bundled') {
      const id = ref.version || this.defaultVersion(skillName);
      if (!id) {
        return null;
      }
      const p = path.join(this.skillsSourcePath, skillName, id);
      return fs.existsSync(p) && fs.statSync(p).isDirectory() ? p : null;
    } else {
      const tag = ref.tag;
      if (!tag) {
        return null;
      }
      const p = path.join(this.snapshotSkillDir(skillName), tag);
      return fs.existsSync(p) && fs.statSync(p).isDirectory() ? p : null;
    }
  }

  // ============ Presets ============

  private presetsPath(workspacePath: string): string {
    return path.join(workspacePath, PRESETS_RELATIVE);
  }

  loadPresets(workspacePath: string): SkillPresetsFile | null {
    const p = this.presetsPath(workspacePath);
    if (!fs.existsSync(p)) {
      return null;
    }
    try {
      const raw = fs.readFileSync(p, 'utf-8');
      const data = JSON.parse(raw);
      if (typeof data?.active !== 'string' || typeof data?.presets !== 'object') {
        return null;
      }
      return data as SkillPresetsFile;
    } catch (e) {
      this.log(`Failed to read presets: ${(e as Error).message}`);
      return null;
    }
  }

  savePresets(workspacePath: string, data: SkillPresetsFile): { success: boolean; message: string } {
    const p = this.presetsPath(workspacePath);
    try {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n', 'utf-8');
      return { success: true, message: `已保存 preset 到 ${p}` };
    } catch (e) {
      return { success: false, message: `写入 preset 失败: ${(e as Error).message}` };
    }
  }

  ensureDefaultPresetExists(workspacePath: string): SkillPresetsFile {
    const existing = this.loadPresets(workspacePath);
    if (existing) {
      return existing;
    }
    const defaultMap: SkillPresetMap = {};
    for (const skill of this.listManagedSkills()) {
      const ver = this.defaultVersion(skill);
      if (ver) {
        defaultMap[skill] = { source: 'bundled', version: ver };
      }
    }
    const file: SkillPresetsFile = {
      active: DEFAULT_PRESET_NAME,
      presets: { [DEFAULT_PRESET_NAME]: defaultMap },
    };
    this.savePresets(workspacePath, file);
    return file;
  }

  getActivePreset(workspacePath: string): { name: string; map: SkillPresetMap } {
    const file = this.ensureDefaultPresetExists(workspacePath);
    const name = file.active;
    const map = file.presets[name] ?? file.presets[DEFAULT_PRESET_NAME] ?? {};
    return { name, map };
  }

  setActivePreset(workspacePath: string, name: string): { success: boolean; message: string } {
    const file = this.ensureDefaultPresetExists(workspacePath);
    if (!file.presets[name]) {
      return { success: false, message: `preset 不存在: ${name}` };
    }
    file.active = name;
    return this.savePresets(workspacePath, file);
  }

  listPresetNames(workspacePath: string): string[] {
    const file = this.ensureDefaultPresetExists(workspacePath);
    return Object.keys(file.presets).sort();
  }

  // ============ Apply preset (rebuild symlinks) ============

  applyPreset(workspacePath: string, presetName?: string): ApplyResult {
    const file = this.ensureDefaultPresetExists(workspacePath);
    const targetName = presetName || file.active;
    if (!file.presets[targetName]) {
      return {
        preset: targetName,
        applied: [],
        fallbacks: [],
        errors: [{ skill: '*', message: `preset 不存在: ${targetName}` }],
      };
    }

    const mapping = file.presets[targetName];
    const skillsTarget = path.join(workspacePath, '.claude', 'skills');
    fs.mkdirSync(skillsTarget, { recursive: true });

    const result: ApplyResult = {
      preset: targetName,
      applied: [],
      fallbacks: [],
      errors: [],
    };

    for (const skill of this.listManagedSkills()) {
      let ref: SkillVersionRef | undefined = mapping[skill];
      if (!ref) {
        const ver = this.defaultVersion(skill);
        if (!ver) {
          result.errors.push({ skill, message: 'manifest 无 defaultVersion' });
          continue;
        }
        ref = { source: 'bundled', version: ver };
        result.fallbacks.push(skill);
      }

      const target = this.resolveVersionPath(skill, ref);
      if (!target) {
        result.errors.push({
          skill,
          message: `版本无法解析: ${JSON.stringify(ref)}`,
        });
        continue;
      }

      const link = path.join(skillsTarget, skill);
      try {
        if (fs.existsSync(link) || this.isLinkOrDir(link)) {
          // Remove existing entry (symlink or directory)
          fs.rmSync(link, { recursive: true, force: true });
        }
      } catch (e) {
        result.errors.push({ skill, message: `清理旧链接失败: ${(e as Error).message}` });
        continue;
      }

      const mode = this.symlinkOrCopy(target, link);
      if (mode === null) {
        result.errors.push({ skill, message: `symlink/copy 全部失败` });
        continue;
      }
      result.applied.push({ skill, ref, mode });
    }

    // Persist active preset
    if (presetName && presetName !== file.active) {
      file.active = presetName;
      this.savePresets(workspacePath, file);
    }

    return result;
  }

  // ============ Helpers ============

  private isLinkOrDir(p: string): boolean {
    try {
      const lstat = fs.lstatSync(p);
      return lstat.isSymbolicLink() || lstat.isDirectory();
    } catch {
      return false;
    }
  }

  private resolveSymlink(p: string): string {
    try {
      return fs.realpathSync(p);
    } catch {
      return p;
    }
  }

  private symlinkOrCopy(source: string, link: string): 'symlink' | 'copy' | null {
    try {
      fs.symlinkSync(source, link, 'dir');
      return 'symlink';
    } catch (e) {
      if (!this.symlinkFailureWarned) {
        this.symlinkFailureWarned = true;
        this.log(
          `[警告] symlink 失败，回退到目录复制（Windows 需开启开发者模式）: ${(e as Error).message}`,
        );
      }
      try {
        copyDirectoryRecursive(source, link);
        return 'copy';
      } catch (e2) {
        this.log(`copy 也失败: ${(e2 as Error).message}`);
        return null;
      }
    }
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  showOutput(): void {
    this.outputChannel.show();
  }
}

/**
 * Recursively copy a directory tree, skipping pyc / pycache.
 * Standalone so SkillVersionManager doesn't depend on WorkspaceManager.
 */
export function copyDirectoryRecursive(source: string, target: string): void {
  fs.mkdirSync(target, { recursive: true });
  for (const item of fs.readdirSync(source)) {
    if (item === '__pycache__' || item.endsWith('.pyc')) {
      continue;
    }
    const sp = path.join(source, item);
    const tp = path.join(target, item);
    const stat = fs.statSync(sp);
    if (stat.isDirectory()) {
      copyDirectoryRecursive(sp, tp);
    } else if (stat.isFile()) {
      fs.copyFileSync(sp, tp);
    }
  }
}
