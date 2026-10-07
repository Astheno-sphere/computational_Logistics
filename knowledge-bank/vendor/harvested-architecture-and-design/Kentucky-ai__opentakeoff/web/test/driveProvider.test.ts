// Annotation-sync provider (sync/provider.js) — pull/push primitives with the
// app-level rev precondition, against an in-memory fake Drive. No network.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createDriveProvider } from "../src/lib/sync/provider.js";

const FOLDER_MIME = "application/vnd.google-apps.folder";

// Fake Drive over a Map<id, {id,name,parent,mime,bytes?}>. Enough of createDrive
// for the provider: findChild, putJson (create+update), getJson. `_getJsonCalls`
// and `_findChildCalls` let tests assert round-trip counts. `_failGetJsonOnce`
// forces one unreadable read (corrupt file / blip).
function fakeDrive() {
  const byId = new Map<string, any>();
  let seq = 0;
  const nid = () => `id_${++seq}`;
  const find = (parent: string, name: string) => {
    for (const r of byId.values()) if (r.parent === parent && r.name === name) return r;
    return null;
  };
  return {
    _byId: byId,
    _getJsonCalls: 0,
    _findChildCalls: 0,
    _failGetJsonOnce: false,
    async findChild(parent: string, name: string) {
      this._findChildCalls++;
      const r = find(parent, name);
      return r ? { id: r.id, name: r.name, mimeType: r.mime } : null;
    },
    async putJson({ folderId, name, data, existingId }: any) {
      const bytes = new TextEncoder().encode(JSON.stringify(data));
      if (existingId) {
        // Mirror real drive.js: updateFileBytes PATCHes by id and 404s if the
        // file is gone. The fake must reject too, or it hides update-by-dead-id
        // bugs (a create-branch fallback would silently paper over them).
        if (!byId.has(existingId)) throw new Error(`update failed (HTTP 404): ${existingId} gone`);
        byId.get(existingId).bytes = bytes;
        return { id: existingId };
      }
      const id = nid();
      byId.set(id, { id, name, parent: folderId, mime: "application/json", bytes });
      return { id };
    },
    async deleteFile(id: string) { byId.delete(id); },
    async getJson(id: string) {
      this._getJsonCalls++;
      if (this._failGetJsonOnce) { this._failGetJsonOnce = false; throw new Error("unreadable"); }
      return JSON.parse(new TextDecoder().decode(byId.get(id).bytes));
    },
  };
}

const SIDECAR = "sidecar1";
// The injected shared-sidecar resolver: always the same id, and it records how
// often it was asked (to prove the provider never creates its own sidecar).
function mk(drive = fakeDrive()) {
  let sidecarCalls = 0;
  const ensureSidecarId = async () => { sidecarCalls++; return SIDECAR; };
  const provider = createDriveProvider("folderX", drive as any, { ensureSidecarId });
  return { drive, provider, sidecarCalls: () => sidecarCalls };
}
// read the raw stored annotations.json (whatever id it got)
const remoteAnn = (drive: any) => {
  for (const r of drive._byId.values()) if (r.name === "annotations.json") return JSON.parse(new TextDecoder().decode(r.bytes));
  return null;
};

test("pull returns null when no annotations file exists yet (fresh project)", async () => {
  const { provider } = mk();
  assert.equal(await provider.pull(), null);
});

test("pull returns { data, rev } for a rev-bearing file", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [1], rev: 7 }, existingId: null });
  const res = await provider.pull();
  assert.deepEqual(res, { data: { shapes: [1], rev: 7 }, rev: 7 });
});

test("pull yields rev null for a rev-less file (a flag-off teammate's write)", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [1], schema: "x" }, existingId: null });
  const res = await provider.pull();
  assert.equal(res!.rev, null);
  assert.deepEqual(res!.data, { shapes: [1], schema: "x" });
});

test("pull propagates a read error (corrupt/blip) instead of masking it", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { rev: 1 }, existingId: null });
  drive._failGetJsonOnce = true;
  await assert.rejects(provider.pull(), /unreadable/);
});

test("first push (no expectedRev, no file) creates the file at rev 1", async () => {
  const { drive, provider } = mk();
  const res = await provider.push({ shapes: [1], schema: "x" }, {});
  assert.deepEqual(res, { rev: 1 });
  assert.deepEqual(remoteAnn(drive), { shapes: [1], schema: "x", rev: 1 });
});

test("push with matching expectedRev writes expectedRev + 1", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], rev: 4 }, existingId: null });
  const res = await provider.push({ shapes: [9], schema: "x" }, { expectedRev: 4 });
  assert.deepEqual(res, { rev: 5 });
  assert.deepEqual(remoteAnn(drive), { shapes: [9], schema: "x", rev: 5 });
});

test("push conflicts (no write) when remote moved past expectedRev", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], rev: 8 }, existingId: null });
  // caller thinks it's based on rev 4, but remote is already at 8
  const res = await provider.push({ shapes: [9] }, { expectedRev: 4 });
  assert.deepEqual(res, { conflict: true, remote: { data: { shapes: [0], rev: 8 }, rev: 8 } });
  // remote is untouched
  assert.deepEqual(remoteAnn(drive), { shapes: [0], rev: 8 });
});

test("push conflicts when remote is rev-less but caller expected a rev (external write)", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], schema: "x" }, existingId: null });
  const res = await provider.push({ shapes: [9] }, { expectedRev: 3 });
  assert.equal((res as any).conflict, true);
  assert.equal((res as any).remote.rev, null);
  assert.deepEqual(remoteAnn(drive), { shapes: [0], schema: "x" }); // untouched
});

test("push over an existing rev-less file with NO expectedRev proceeds (first opt-in write)", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], schema: "x" }, existingId: null });
  const res = await provider.push({ shapes: [9], schema: "x" }, {}); // expectedRev null
  assert.deepEqual(res, { rev: 1 }); // remoteRev null → (null ?? null ?? 0) + 1
  assert.deepEqual(remoteAnn(drive), { shapes: [9], schema: "x", rev: 1 });
});

test("push treats an unreadable remote as no-known-rev: first push proceeds, expected-rev conflicts", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { rev: 5 }, existingId: null });
  drive._failGetJsonOnce = true; // the precondition read fails
  // expectedRev set → cannot confirm, so conflict (safe: never blind-overwrite)
  const res = await provider.push({ shapes: [1] }, { expectedRev: 5 });
  assert.equal((res as any).conflict, true);
  assert.equal((res as any).remote.rev, null);
});

test("concurrent first pushes don't create duplicate files (ensureAnnId memoized)", async () => {
  const { drive, provider } = mk();
  await Promise.all([
    provider.push({ shapes: [1], schema: "x" }, {}),
    provider.push({ shapes: [2], schema: "x" }, {}),
  ]);
  const files = [...drive._byId.values()].filter((r: any) => r.name === "annotations.json");
  assert.equal(files.length, 1, "exactly one annotations.json");
});

test("push self-heals a stale cached id: a deleted file re-creates instead of wedging forever", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], rev: 2 }, existingId: null });
  const pulled = await provider.pull(); // caches the id for push
  assert.equal(pulled!.rev, 2);

  // the file is deleted out from under the cached id
  const annFile = [...drive._byId.values()].find((r: any) => r.name === "annotations.json");
  await drive.deleteFile(annFile!.id);

  // first push after the delete: precondition read 404s → safe no-write conflict,
  // and the dead id is dropped from the memo
  const r1 = await provider.push({ shapes: [1] }, { expectedRev: 2 });
  assert.equal((r1 as any).conflict, true);

  // the NEXT push must succeed by re-locating/re-creating — no permanent wedge
  const r2 = await provider.push({ shapes: [9], schema: "x" }, {});
  assert.deepEqual(r2, { rev: 1 });
  const files = [...drive._byId.values()].filter((r: any) => r.name === "annotations.json");
  assert.equal(files.length, 1);
  assert.deepEqual(remoteAnn(drive), { shapes: [9], schema: "x", rev: 1 });
});

test("pull with a non-creating findSidecarId returns null and creates nothing on a fresh project", async () => {
  const drive = fakeDrive();
  const provider = createDriveProvider("folderX", drive as any, {
    ensureSidecarId: async () => { throw new Error("ensureSidecarId (create-once) must not run on a read path"); },
    findSidecarId: async () => null, // no sidecar folder yet
  });
  assert.equal(await provider.pull(), null);
  assert.equal([...drive._byId.values()].length, 0, "a read-only pull must not create anything");
});

test("a non-integer rev (corrupt/hand-edited) is treated as absent, not trusted", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], rev: 3.7 }, existingId: null });
  // pull reports rev null (not 3.7), so no comparison ever bumps to 4.7
  assert.equal((await provider.pull())!.rev, null);
  // a first opt-in push (no expectedRev) overwrites the degenerate file at rev 1
  const r = await provider.push({ shapes: [1], schema: "x" }, {});
  assert.deepEqual(r, { rev: 1 });
});

test("rev 0 round-trips: pull yields rev 0, push with expectedRev 0 writes rev 1", async () => {
  const { drive, provider } = mk();
  await drive.putJson({ folderId: SIDECAR, name: "annotations.json", data: { shapes: [0], rev: 0 }, existingId: null });
  assert.equal((await provider.pull())!.rev, 0); // 0 is a present rev, not "absent"
  const r = await provider.push({ shapes: [1], schema: "x" }, { expectedRev: 0 });
  assert.deepEqual(r, { rev: 1 });
});

test("provider never creates its own sidecar — it uses the injected resolver only", async () => {
  const { drive, provider, sidecarCalls } = mk();
  await provider.push({ shapes: [1] }, {});
  await provider.pull();
  // sidecar resolver was used, and no folder was ever created by the provider
  assert.ok(sidecarCalls() > 0);
  const folders = [...drive._byId.values()].filter((r: any) => r.mime === FOLDER_MIME);
  assert.equal(folders.length, 0);
});
