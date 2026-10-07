const { execFileSync } = require("node:child_process");
const { rmSync, renameSync, mkdtempSync } = require("node:fs");
const os = require("node:os");
const path = require("node:path");

/**
 * Ad-hoc code-sign the packaged .app so macOS Gatekeeper accepts it.
 *
 * Without a valid signature an unsigned arm64 app reports "'Peckish' is damaged
 * and can't be opened" once it carries the download quarantine flag — Gatekeeper
 * runs a full bundle verification that a missing / linker-only signature fails.
 * Ad-hoc signing is NOT notarization (users still do the one-time
 * right-click → Open), but it produces a signature that verifies, turning the
 * fatal "damaged" error into the bypassable "unidentified developer" one.
 *
 * The dance below works around two macOS gotchas that make the obvious
 * `codesign --deep` fail:
 *   1. macOS 15 tags helper binaries with resource-fork / provenance detritus
 *      that codesign rejects ("resource fork, Finder information … not allowed").
 *      `xattr -c` can't clear it and a same-directory copy APFS-clones it intact;
 *      a `ditto --noextattr` to a *separate* tmp dir does strip it.
 *   2. Signing must happen on that clean copy, and the result moved back with a
 *      rename — copying the signed bundle back onto some volumes re-tags the
 *      files and re-breaks the signature. A rename moves the inode untouched.
 *
 * We sign without `--timestamp` (ad-hoc can't be timestamped, and it would need
 * network the build host may not have). electron-builder's own signing stays
 * disabled (mac.identity=null) so it doesn't fight this with a --timestamp pass.
 * macOS-only; a no-op elsewhere.
 */
exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== "darwin") return;
  const app = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`);
  const stage = mkdtempSync(path.join(os.tmpdir(), "peckish-sign-"));
  const staged = path.join(stage, path.basename(app));
  try {
    execFileSync("ditto", ["--norsrc", "--noextattr", "--noacl", app, staged], { stdio: "inherit" });
    execFileSync("codesign", ["--force", "--deep", "--sign", "-", staged], { stdio: "inherit" });
    execFileSync("codesign", ["--verify", "--deep", "--strict", staged], { stdio: "inherit" });
    rmSync(app, { recursive: true, force: true });
    renameSync(staged, app);
    execFileSync("codesign", ["--verify", "--deep", "--strict", app], { stdio: "inherit" });
    console.log(`  • ad-hoc signed ${path.basename(app)}`);
  } finally {
    rmSync(stage, { recursive: true, force: true });
  }
};
