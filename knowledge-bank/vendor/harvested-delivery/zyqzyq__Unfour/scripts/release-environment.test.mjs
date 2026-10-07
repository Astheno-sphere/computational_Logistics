import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  resolveReleaseChannel,
  resolveTauriInvocation,
  tauriEnvironment,
} from "./release-environment.mjs";

test("release channel resolution uses the requested default", () => {
  assert.equal(resolveReleaseChannel(undefined), "test");
  assert.equal(resolveReleaseChannel(""), "test");
  assert.equal(resolveReleaseChannel(undefined, "stable"), "stable");
});

test("an explicit release channel overrides the command default", () => {
  assert.equal(resolveReleaseChannel("stable"), "stable");
  assert.equal(resolveReleaseChannel("test", "stable"), "test");
});

test("Tauri build defaults to Stable and build:test forces Test", () => {
  assert.deepEqual(resolveTauriInvocation(["build"]), {
    args: ["build"],
    defaultChannel: "stable",
    forcedChannel: undefined,
  });
  assert.deepEqual(resolveTauriInvocation(["build:test", "--debug"]), {
    args: ["build", "--debug"],
    defaultChannel: "test",
    forcedChannel: "test",
  });
});

test("non-build Tauri commands continue to default to Test", () => {
  assert.deepEqual(resolveTauriInvocation(["dev"]), {
    args: ["dev"],
    defaultChannel: "test",
    forcedChannel: undefined,
  });
});

test("build:test forces Test even when the parent environment selects Stable", () => {
  const invocation = resolveTauriInvocation(["build:test"]);
  const { channel, environment } = tauriEnvironment(
    { UNFOUR_RELEASE_CHANNEL: "stable" },
    invocation.defaultChannel,
    invocation.forcedChannel,
  );

  assert.equal(channel, "test");
  assert.equal(environment.UNFOUR_RELEASE_CHANNEL, "test");
});

test("invalid release channels are rejected", () => {
  for (const value of ["dev", "nightly", "Stable", "test.1", " test", " "]) {
    assert.throws(
      () => resolveReleaseChannel(value),
      /must be exactly "test" or "stable"/,
    );
  }
});

test("the resolved channel reaches child processes", () => {
  const { environment } = tauriEnvironment({
    PATH: process.env.PATH,
    UNFOUR_RELEASE_CHANNEL: "test",
  });
  const child = spawnSync(
    process.execPath,
    ["-e", "process.stdout.write(process.env.UNFOUR_RELEASE_CHANNEL ?? '')"],
    { encoding: "utf8", env: environment },
  );

  assert.equal(child.status, 0);
  assert.equal(child.stdout, "test");
});
