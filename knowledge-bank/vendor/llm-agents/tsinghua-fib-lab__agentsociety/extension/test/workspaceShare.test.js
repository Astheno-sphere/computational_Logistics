const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const {
  buildExportManifest,
  canonicalizeContentHash,
  parseExportManifest,
  planImportTarget,
  shouldExcludeWorkspacePath,
  shouldSkipImportPath,
  validateExportSelection,
} = require('../out/services/workspaceExportManifest');
const {
  collectContentDigests,
  runPythonArchiveCommand,
} = require('../out/services/workspaceArchiveIo');

function sampleManifest() {
  return buildExportManifest({
    workspaceName: 'demo',
    extensionVersion: '1.6.7',
    roots: [{
      archivePath: 'TOPIC.md',
      kind: 'file',
      tier: 'core',
      bytes: 12,
      fileCount: 1,
    }],
    contentHash: 'a'.repeat(64),
    notice: {
      title: 't',
      copyright: 'c',
      redistribution: 'r',
      secrets: 's',
      importer: 'i',
    },
  });
}

test('import accepts current share packages and rejects unsafe ones', () => {
  const manifest = sampleManifest();
  assert.equal(parseExportManifest(manifest).ok, true);
  assert.deepEqual(parseExportManifest({ ...manifest, formatVersion: 1 }), {
    ok: false,
    error: 'unsupported_version',
  });
  assert.equal(parseExportManifest({ ...manifest, workspaceName: '../evil' }).ok, false);
  assert.equal(parseExportManifest({
    ...manifest,
    roots: [{ ...manifest.roots[0], bytes: -1 }],
  }).ok, false);
  assert.equal(parseExportManifest({
    ...manifest,
    roots: [manifest.roots[0], { ...manifest.roots[0] }],
  }).ok, false);
});

test('import skips secrets and export sidecars regardless of manifest claims', () => {
  assert.equal(shouldSkipImportPath('../outside.txt'), true);
  assert.equal(shouldSkipImportPath('/absolute.txt'), true);
  assert.equal(shouldSkipImportPath('.env'), true);
  assert.equal(shouldSkipImportPath('.env.local'), true);
  assert.equal(shouldSkipImportPath('hypothesis_1/.env'), true);
  assert.equal(shouldSkipImportPath('custom/auth.json'), true);
  assert.equal(shouldSkipImportPath('agentsociety_data/cache.db'), true);
  assert.equal(shouldSkipImportPath('.git/config'), true);
  assert.equal(shouldSkipImportPath('_agentsociety/export-manifest.json'), true);
  assert.equal(shouldSkipImportPath('_agentsociety/SHARE.md'), true);
  assert.equal(shouldSkipImportPath('TOPIC.md'), false);
  assert.equal(shouldSkipImportPath('custom/skills/demo/SKILL.md'), false);
  assert.equal(shouldSkipImportPath('papers/note.md'), false);
  assert.equal(shouldSkipImportPath('.claude/skills/demo/SKILL.md'), false);
});

test('export excludes secrets and local IDE state', () => {
  assert.equal(shouldExcludeWorkspacePath('nested/.env.production'), true);
  assert.equal(shouldExcludeWorkspacePath('paper/easypaper_config.yaml'), true);
  assert.equal(shouldExcludeWorkspacePath('.cursor/settings.json'), true);
  assert.equal(shouldExcludeWorkspacePath('.vscode/launch.json'), true);
  assert.equal(shouldExcludeWorkspacePath('custom/skills/demo/SKILL.md'), false);
});

test('content hash is stable and changes with file contents', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'as-share-hash-'));
  fs.mkdirSync(path.join(root, 'nested'));
  fs.writeFileSync(path.join(root, 'TOPIC.md'), 'topic');
  fs.writeFileSync(path.join(root, 'nested', 'data.txt'), 'first');
  const first = canonicalizeContentHash(collectContentDigests(root));
  const second = canonicalizeContentHash(collectContentDigests(root));
  assert.equal(first, second);

  fs.writeFileSync(path.join(root, 'nested', 'data.txt'), 'second');
  assert.notEqual(canonicalizeContentHash(collectContentDigests(root)), first);
  fs.rmSync(root, { recursive: true, force: true });
});

test('non-research optional roots are filtered from share picker noise', () => {
  const {
    isNonResearchOptionalRoot,
    RECOMMENDED_EXPORT_ROOTS,
    formatExportRootSummary,
  } = require('../out/services/workspaceExportManifest');
  assert.equal(isNonResearchOptionalRoot('packages'), true);
  assert.equal(isNonResearchOptionalRoot('extension'), true);
  assert.equal(isNonResearchOptionalRoot('frontend'), true);
  assert.equal(isNonResearchOptionalRoot('hypothesis_1'), false);
  assert.equal(isNonResearchOptionalRoot('papers'), false);
  assert.ok(RECOMMENDED_EXPORT_ROOTS.some((item) => item.archivePath === 'TOPIC.md'));
  assert.ok(RECOMMENDED_EXPORT_ROOTS.some((item) => item.archivePath === 'papers'));
  assert.equal(formatExportRootSummary([{ archivePath: 'TOPIC.md' }, { archivePath: 'papers' }]), 'TOPIC.md, papers');
});

test('export warns when existing research roots were not selected', () => {
  const validation = validateExportSelection({
    selectedRoots: [{
      archivePath: 'datasets',
      kind: 'directory',
      tier: 'core',
      bytes: 1,
      fileCount: 1,
    }],
  });
  assert.ok(validation.issues.some((issue) => issue.code === 'no_core_research'));
});

test('export symlink resolver skips broken and outside links', () => {
  const { resolveSafeExportSymlink } = require('../out/services/workspaceExportManifest');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'as-share-link-'));
  const inside = path.join(root, 'inside.txt');
  const outside = path.join(path.dirname(root), `${path.basename(root)}-outside.txt`);
  fs.writeFileSync(inside, 'inside');
  fs.writeFileSync(outside, 'outside');
  fs.symlinkSync('missing.txt', path.join(root, 'broken'));
  fs.symlinkSync(inside, path.join(root, 'inside-link'));
  fs.symlinkSync(outside, path.join(root, 'outside-link'));

  assert.equal(resolveSafeExportSymlink(path.join(root, 'broken'), root), undefined);
  assert.equal(resolveSafeExportSymlink(path.join(root, 'inside-link'), root), inside);
  assert.equal(resolveSafeExportSymlink(path.join(root, 'outside-link'), root), undefined);

  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(outside, { force: true });
});

test('import always plans a new named project directory', () => {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'as-share-parent-'));
  assert.deepEqual(planImportTarget(parent, 'demo-project'), {
    ok: true,
    targetPath: path.join(parent, 'demo-project'),
  });
  fs.mkdirSync(path.join(parent, 'existing'));
  assert.deepEqual(planImportTarget(parent, 'existing'), {
    ok: false,
    error: 'target_exists',
  });
  assert.deepEqual(planImportTarget(parent, '../escape'), {
    ok: false,
    error: 'invalid_name',
  });
  fs.rmSync(parent, { recursive: true, force: true });
});

test('extract refuses archives that write outside the destination', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'as-share-slip-'));
  const zipPath = path.join(root, 'evil.zip');
  const extracted = path.join(root, 'extracted');
  fs.mkdirSync(extracted, { recursive: true });
  const created = spawnSync(
    process.platform === 'win32' ? 'python' : 'python3',
    ['-c', 'import zipfile, sys; zipfile.ZipFile(sys.argv[1], "w").writestr("../evil.txt", "pwned")', zipPath],
    { encoding: 'utf-8' },
  );
  assert.equal(created.status, 0, created.stderr);
  await assert.rejects(
    () => runPythonArchiveCommand(
      process.platform === 'win32' ? 'python' : 'python3',
      'extract',
      zipPath,
      extracted,
    ),
    /unsafe archive path/,
  );
  assert.equal(fs.existsSync(path.join(root, 'evil.txt')), false);
  fs.rmSync(root, { recursive: true, force: true });
});

test('extract refuses archive entries with excessive compression ratios', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'as-share-bomb-'));
  const zipPath = path.join(root, 'bomb.zip');
  const extracted = path.join(root, 'extracted');
  const created = spawnSync(
    process.platform === 'win32' ? 'python' : 'python3',
    [
      '-c',
      'import zipfile, sys; zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED).writestr("large.txt", b"0" * 1024 * 1024)',
      zipPath,
    ],
    { encoding: 'utf-8' },
  );
  assert.equal(created.status, 0, created.stderr);
  await assert.rejects(
    () => runPythonArchiveCommand(
      process.platform === 'win32' ? 'python' : 'python3',
      'extract',
      zipPath,
      extracted,
    ),
    /compression ratio is too high/,
  );
  fs.rmSync(root, { recursive: true, force: true });
});
