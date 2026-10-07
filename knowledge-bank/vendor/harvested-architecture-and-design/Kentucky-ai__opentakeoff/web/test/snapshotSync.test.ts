// Snapshot Drive-sync decorator — proves the append-only union against an
// in-memory fake provider (a Map of folders+files) and a fake base localStore
// that mirrors store.js snapshot scope semantics. No network, no IndexedDB.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createSnapshotSync } from "../src/lib/google/snapshotSync.js";
import { driveSnapshotProvider } from "../src/lib/google/snapshotSyncAdapter.js";

const FOLDER_MIME = "application/vnd.google-apps.folder";
const F = "folder1"; // the project folder id

// Fake provider over one Map<id, {id,name,parent,mime,data?}>. Enough of the
// six-method contract for the decorator to run. `_fail` makes the named method
// throw (offline); `_hang` makes it never resolve (slow network). `_getJson`
// counts downloads so we can prove only-missing fetching.
function fakeProvider() {
  const byId = new Map<string, any>();
  let seq = 0;
  const nid = () => `n${++seq}`;
  const find = (parent: string, name: string) => {
    for (const r of byId.values()) if (r.parent === parent && r.name === name) return r;
    return null;
  };
  return {
    _byId: byId,
    _fail: null as string | null,
    _hang: null as string | null,
    _getJsonCalls: 0,
    async findChild(parent: string, name: string) {
      const r = find(parent, name);
      return r ? { id: r.id, name: r.name, mimeType: r.mime } : null;
    },
    async createFolder(parent: string, name: string) {
      const id = nid();
      byId.set(id, { id, name, parent, mime: FOLDER_MIME });
      return { id, name };
    },
    async listChildren(folder: string) {
      if (this._hang === "listChildren") return new Promise<any>(() => {});
      if (this._fail === "listChildren") throw new Error("offline");
      const out = [];
      for (const r of byId.values()) if (r.parent === folder) out.push({ id: r.id, name: r.name, mimeType: r.mime });
      return out;
    },
    async getJson(id: string) {
      this._getJsonCalls++;
      if (this._fail === "getJson") throw new Error("corrupt");
      const r = byId.get(id);
      return r ? r.data : null;
    },
    _delayPutJsonMs: 0,
    async putJson({ folderId, name, data, existingId }: any) {
      if (this._hang === "putJson") return new Promise<any>(() => {});
      if (this._fail === "putJson") throw new Error("push fail");
      if (this._delayPutJsonMs) await new Promise((r) => setTimeout(r, this._delayPutJsonMs));
      if (existingId && byId.has(existingId)) { byId.get(existingId).data = data; return { id: existingId }; }
      const id = nid();
      byId.set(id, { id, name, parent: folderId, mime: "application/json", data });
      return { id };
    },
    async deleteFile(id: string) {
      if (this._fail === "deleteFile") throw new Error("del fail");
      byId.delete(id);
    },
  };
}

// Base localStore stand-in mirroring store.js snapshot scope semantics exactly.
function fakeBase() {
  const byId = new Map<string, any>();
  let seq = 0;
  return {
    _byId: byId,
    async saveSnapshot(label: any, payload: any, project: any = null) {
      const id = `snap_${++seq}`;
      const ts = 1000 + seq;
      byId.set(id, { id, ts, label: String(label || "").trim() || null, project: project ?? null, payload });
      return { id, ts };
    },
    async putSnapshot(record: any) {
      if (!record || typeof record.id !== "string" || !record.id.trim()) throw new Error("record.id");
      if (typeof record.ts !== "number" || !Number.isFinite(record.ts)) throw new Error("record.ts");
      if (record.payload == null) throw new Error("record.payload");
      byId.set(record.id, record);
    },
    async listSnapshots(project: any = null) {
      const scope = project ?? null;
      const out = [];
      for (const r of byId.values()) if ((r.project ?? null) === scope) out.push({ id: r.id, ts: r.ts, label: r.label });
      return out.sort((a, b) => b.ts - a.ts);
    },
    async getSnapshot(id: string, project: any = null) {
      const r = byId.get(id);
      if (!r) return null;
      if ((r.project ?? null) !== (project ?? null)) return null;
      return r;
    },
    async deleteSnapshot(id: string) { byId.delete(id); },
  };
}

const mk = (over: any = {}) => {
  const base = over.base ?? fakeBase();
  const provider = over.provider ?? fakeProvider();
  const sync = createSnapshotSync({ base, provider, folderId: F, timeoutMs: 50, ...over.opts }) as any;
  return { base, provider, sync };
};

// Count how many json files sit in the snapshots folder (whatever its id is).
const remoteSnapshotFiles = (provider: any) =>
  [...provider._byId.values()].filter((r: any) => r.name?.endsWith(".json"));

test("saveSnapshot writes local authoritatively and pushes the full record to Drive", async () => {
  const { base, provider, sync } = mk();
  const meta = await sync.saveSnapshot("first", { shapes: [1] });
  // local is written synchronously (before the push settles)
  assert.equal((await base.getSnapshot(meta.id, F)).label, "first");
  await sync.whenIdle();
  const files = remoteSnapshotFiles(provider);
  assert.equal(files.length, 1);
  assert.equal(files[0].name, `${meta.id}.json`);
  assert.deepEqual(files[0].data, await base.getSnapshot(meta.id, F)); // verbatim record
});

test("listSnapshots unions a remote-only snapshot into local (device B sees device A's work)", async () => {
  const { base, provider, sync } = mk();
  // seed the folder structure + a remote record device A pushed
  const sidecar = await provider.createFolder(F, ".opentakeoff");
  const snaps = await provider.createFolder(sidecar.id, "snapshots");
  const remote = { id: "snap_remote", ts: 5000, label: "from A", project: F, payload: { shapes: [9] } };
  await provider.putJson({ folderId: snaps.id, name: "snap_remote.json", data: remote });

  const list = await sync.listSnapshots();
  assert.deepEqual(list.map((s: any) => s.id), ["snap_remote"]);
  // materialized verbatim into local (id preserved, scope honored)
  assert.deepEqual(await base.getSnapshot("snap_remote", F), remote);
});

test("union dedups by id: an id already local is NOT re-downloaded", async () => {
  const { base, provider, sync } = mk();
  const meta = await sync.saveSnapshot("mine", { shapes: [1] });
  await sync.whenIdle();
  provider._getJsonCalls = 0;
  const list = await sync.listSnapshots();
  assert.deepEqual(list.map((s: any) => s.id), [meta.id]);
  assert.equal(provider._getJsonCalls, 0, "already-local id must not be fetched");
});

test("delete removes local AND the Drive file, and a later list does not resurrect it", async () => {
  const { base, provider, sync } = mk();
  const meta = await sync.saveSnapshot("doomed", { shapes: [1] });
  await sync.whenIdle();
  assert.equal(remoteSnapshotFiles(provider).length, 1);

  await sync.deleteSnapshot(meta.id);
  assert.equal(await base.getSnapshot(meta.id, F), null);
  assert.equal(remoteSnapshotFiles(provider).length, 0, "Drive file hard-deleted");

  const list = await sync.listSnapshots();
  assert.deepEqual(list, [], "no resurrection");
});

test("delete immediately after save (push still in flight) does not resurrect", async () => {
  const { base, provider, sync } = mk();
  const meta = await sync.saveSnapshot("racy", { shapes: [1] });
  // delete WITHOUT whenIdle — the background push may not have created the
  // remote file yet; deleteSnapshot must wait it out then remove the file
  await sync.deleteSnapshot(meta.id);
  await sync.whenIdle(); // nothing should still be pending
  assert.equal(await base.getSnapshot(meta.id, F), null);
  assert.equal(remoteSnapshotFiles(provider).length, 0, "no remote file survives a racy delete");
  assert.deepEqual(await sync.listSnapshots(), [], "no resurrection");
});

test("delete does not hang when the in-flight push is stuck, and still cannot resurrect", async () => {
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const { base, provider, sync } = mk(); // timeoutMs is 50
  provider._hang = "putJson"; // the push will reach putJson and never settle
  const meta = await sync.saveSnapshot("stuck", { shapes: [1] }); // local write returns at once
  await sleep(10); // let the background push advance INTO the hung putJson (past its deletedIds check)

  // deleteSnapshot must resolve via the timeout cap, not block on the stuck push
  const outcome = await Promise.race([
    sync.deleteSnapshot(meta.id).then(() => "resolved"),
    sleep(1000).then(() => "hung"),
  ]);
  assert.equal(outcome, "resolved", "delete must not hang on a stuck push");
  assert.equal(await base.getSnapshot(meta.id, F), null);
  assert.equal(remoteSnapshotFiles(provider).length, 0, "stuck push wrote nothing; delete removed nothing to recreate");
});

test("delete during a SLOW (finite) push does not resurrect — the late push cleans up its own file", async () => {
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const { base, provider, sync } = mk(); // timeoutMs 50
  provider._delayPutJsonMs = 150; // putJson creates the file, but only AFTER delete's cap fires
  const meta = await sync.saveSnapshot("slow", { shapes: [1] });
  await sleep(10); // push passes its pre-write deletedIds guard and enters the slow putJson

  await sync.deleteSnapshot(meta.id); // cap fires at 50ms; findChild misses the not-yet-created file
  // at this instant the file does NOT exist yet (putJson still in flight)
  assert.equal(remoteSnapshotFiles(provider).length, 0);

  await sync.whenIdle(); // let the slow push finish: it creates the file, then self-deletes it
  assert.equal(await base.getSnapshot(meta.id, F), null);
  assert.equal(remoteSnapshotFiles(provider).length, 0, "the late push cleaned up the file it created");
  assert.deepEqual(await sync.listSnapshots(), [], "no resurrection");
});

test("pullMissing skips a remote record whose project scope doesn't match this folder", async () => {
  const { base, provider, sync } = mk();
  const sidecar = await provider.createFolder(F, ".opentakeoff");
  const snaps = await provider.createFolder(sidecar.id, "snapshots");
  // a record with no project — verbatim materialization would leak it into the
  // anonymous/null local scope; it must be skipped
  await provider.putJson({ folderId: snaps.id, name: "snap_foreign.json", data: { id: "snap_foreign", ts: 1, label: "x", payload: {} } });

  assert.deepEqual(await sync.listSnapshots(), []);
  assert.equal(await base.getSnapshot("snap_foreign"), null, "did not leak into the anonymous scope");
});

test("offline: a failed pull returns the local list instead of throwing/hanging", async () => {
  const { sync, provider, base } = mk();
  await base.saveSnapshot("local-only", { shapes: [1] }, F);
  provider._fail = "listChildren";
  const list = await sync.listSnapshots();
  assert.deepEqual(list.map((s: any) => s.label), ["local-only"]);
});

test("offline: a failed push leaves local intact and never surfaces an error", async () => {
  const { base, provider, sync } = mk();
  provider._fail = "putJson";
  const meta = await sync.saveSnapshot("keep-me", { shapes: [1] });
  await sync.whenIdle(); // must not reject
  assert.equal((await base.getSnapshot(meta.id, F)).label, "keep-me");
  assert.equal(remoteSnapshotFiles(provider).length, 0);
});

test("slow network: listSnapshots resolves via timeout with the local list", async () => {
  const { base, provider, sync } = mk();
  await base.saveSnapshot("here", { shapes: [1] }, F);
  provider._hang = "listChildren"; // never resolves
  const list = await sync.listSnapshots(); // must resolve on the 50ms timeout
  assert.deepEqual(list.map((s: any) => s.label), ["here"]);
});

test("a corrupt or name/id-mismatched remote file is skipped, not fatal", async () => {
  const { base, provider, sync } = mk();
  const sidecar = await provider.createFolder(F, ".opentakeoff");
  const snaps = await provider.createFolder(sidecar.id, "snapshots");
  // good record
  await provider.putJson({ folderId: snaps.id, name: "snap_ok.json", data: { id: "snap_ok", ts: 1, label: "ok", project: F, payload: {} } });
  // name/id mismatch → skipped
  await provider.putJson({ folderId: snaps.id, name: "snap_liar.json", data: { id: "snap_other", ts: 1, label: "x", project: F, payload: {} } });
  // incomplete (no ts) → fails putSnapshot guard → skipped
  await provider.putJson({ folderId: snaps.id, name: "snap_bad.json", data: { id: "snap_bad", label: "x", project: F, payload: {} } });
  // non-json file → ignored
  await provider.putJson({ folderId: snaps.id, name: "notes.txt", data: {} });

  const list = await sync.listSnapshots();
  assert.deepEqual(list.map((s: any) => s.id), ["snap_ok"]);
});

test("saveSnapshot honors an explicit project scope arg (cloudStore drops it; snapSync must not)", async () => {
  const { base, sync } = mk();
  const meta = await sync.saveSnapshot("scoped", { shapes: [1] }, "folderZ");
  assert.equal(await base.getSnapshot(meta.id, F), null, "not visible under the decorator's own folder");
  assert.equal((await base.getSnapshot(meta.id, "folderZ")).label, "scoped");
});

test("the shared `.opentakeoff` sidecar is resolved once via an injected resolver", async () => {
  const provider = fakeProvider();
  let sidecarCalls = 0;
  const ensureSidecarId = async () => { sidecarCalls++; const r = await provider.createFolder(F, ".opentakeoff"); return r.id; };
  const base = fakeBase();
  const sync = createSnapshotSync({ base, provider, folderId: F, ensureSidecarId, timeoutMs: 50 }) as any;
  await sync.saveSnapshot("a", { shapes: [1] });
  await sync.whenIdle();
  await sync.saveSnapshot("b", { shapes: [2] });
  await sync.whenIdle();
  // snapshots subfolder is memoized → sidecar resolver hit exactly once
  assert.equal(sidecarCalls, 1);
  // and snapSync did NOT create its own `.opentakeoff` (the injected one was used)
  const sidecars = [...provider._byId.values()].filter((r: any) => r.name === ".opentakeoff");
  assert.equal(sidecars.length, 1);
});

test("the decorator exposes ONLY the four snapshot methods (never shadows addSheets et al.)", async () => {
  const { sync } = mk();
  assert.deepEqual(Object.keys(sync).sort(), ["deleteSnapshot", "getSnapshot", "listSnapshots", "saveSnapshot"]);
});

test("driveSnapshotProvider exposes exactly the six-method provider contract", () => {
  const drive: any = {
    findChild() {}, createFolder() {}, listChildren() {}, getJson() {}, putJson() {}, deleteFile() {},
    getFileBytes() {}, uploadFile() {}, updateFileBytes() {}, // extra drive methods must be dropped
  };
  const p = driveSnapshotProvider(drive);
  assert.deepEqual(Object.keys(p).sort(), ["createFolder", "deleteFile", "findChild", "getJson", "listChildren", "putJson"]);
});
