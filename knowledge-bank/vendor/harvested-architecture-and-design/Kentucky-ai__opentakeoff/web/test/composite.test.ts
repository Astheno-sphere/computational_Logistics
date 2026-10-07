// Local-first composite store (lib/sync/composite.js, Slice 5) — the spread wiring
// that layers annotation + snapshot sync over a Drive-backed cloud store. Verifies
// which layer wins each method (the plan's spread-shadowing contract) and the
// non-enumerable syncBridge the canvas registers into. Runs against real IndexedDB
// (fake-indexeddb) + a no-op fake Drive so the reconciler's bootstrap is harmless.
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { buildLocalFirstStore } from "../src/lib/sync/composite.js";

beforeEach(() => {
  (globalThis as any).indexedDB = new IDBFactory();
});

// A no-op Drive: enough for the reconciler's bootstrap pull + snapshot list to
// resolve without throwing (they run in the background at construction).
function fakeDrive() {
  return {
    async findChild() { return null; },
    async listChildren() { return []; },
    async getJson() { return null; },
    async putJson() { return { id: "x" }; },
    async createFolder() { return { id: "x" }; },
    async deleteFile() {},
  };
}

// A stub cloud store: the surface the composite spreads + the shared sidecar
// resolvers. Distinct function identities so we can prove which layer wins.
// findSidecarFolder returns null → the bootstrap pull is a clean no-op.
function stubCloud() {
  return {
    listFolder: () => {},
    addSheets: () => {},
    addPdf: () => {},
    loadPdfData: () => {},
    removePdf: () => {},
    // these SHOULD be shadowed by the sync layers:
    loadAnnotations: () => "cloud",
    saveAnnotations: () => "cloud",
    saveSnapshot: () => "cloud",
    listSnapshots: () => "cloud",
    getSnapshot: () => "cloud",
    deleteSnapshot: () => "cloud",
    ensureSidecarId: async () => "sidecar",
    findSidecarFolder: async () => null,
  };
}

test("composite: annotation + snapshot methods are shadowed by the sync layers; PDF/manifest methods stay cloud's", () => {
  const cloud = stubCloud();
  const store = buildLocalFirstStore("P", fakeDrive() as any, cloud as any) as any;

  // cloud's PDF/manifest surface survives — cloudMode duck-types on store.listFolder,
  // and addPdf's internal this.addSheets must still resolve (neither sync layer shadows it).
  assert.equal(store.listFolder, cloud.listFolder);
  assert.equal(store.addSheets, cloud.addSheets);
  assert.equal(store.addPdf, cloud.addPdf);
  assert.equal(store.loadPdfData, cloud.loadPdfData);
  assert.equal(store.removePdf, cloud.removePdf);

  // annotations → annSync (local-first); snapshots → snapSync (append-only union)
  assert.notEqual(store.loadAnnotations, cloud.loadAnnotations);
  assert.notEqual(store.saveAnnotations, cloud.saveAnnotations);
  assert.notEqual(store.saveSnapshot, cloud.saveSnapshot);
  assert.notEqual(store.listSnapshots, cloud.listSnapshots);
  assert.notEqual(store.getSnapshot, cloud.getSnapshot);
  assert.notEqual(store.deleteSnapshot, cloud.deleteSnapshot);
});

test("composite: exposes a non-enumerable syncBridge with null handlers and a wired flushPending", () => {
  const store = buildLocalFirstStore("P", fakeDrive() as any, stubCloud() as any) as any;

  // Non-enumerable → invisible to Object.keys, the composite spread, and cloudMode duck-typing.
  assert.ok(!Object.keys(store).includes("syncBridge"));
  const bridge = store.syncBridge;
  assert.equal(bridge.onRemoteUpdate, null); // the canvas registers these on mount
  assert.equal(bridge.isBusy, null);
  assert.equal(typeof bridge.flushPending, "function"); // wired from annSync (idle-drain hook, Slice 5b)
});

test("composite: the store's onRemoteUpdate/isBusy options are null-guarded before the canvas registers", async () => {
  const store = buildLocalFirstStore("P", fakeDrive() as any, stubCloud() as any) as any;
  // With both bridge handlers still null, the store's bootstrap (which reads isBusy
  // and may fire onRemoteUpdate on a seed) must not throw. A plain load is local + safe.
  await assert.doesNotReject(store.loadAnnotations());
  assert.equal(store.syncBridge.onRemoteUpdate, null); // still null — nothing registered
});
