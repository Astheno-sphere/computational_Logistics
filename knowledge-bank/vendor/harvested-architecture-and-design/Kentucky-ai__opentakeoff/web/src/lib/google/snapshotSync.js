// Optional Drive sync for snapshots — an append-only union layer that DECORATES
// the local snapshot store. It wraps localStore's four snapshot methods so the
// RevisionsPanel keeps calling `store.saveSnapshot/listSnapshots/getSnapshot/
// deleteSnapshot` unaware any sync exists (zero diff to the panel or
// snapshotDiff.js). Local is always authoritative and a write never blocks on
// the network; Drive is a best-effort backup/union so another machine can see
// the same snapshots.
//
// CUT-LINE: this file is the ONLY snapshot code that touches the cloud. It
// imports nothing from cloudStore/drive directly — it takes an injected
// `provider` (the small method set below), so a future OneDrive/O365 provider
// drops in unchanged, and deleting this file leaves a fully working local-first
// snapshot feature with no dangling imports.
//
// Provider contract (all Drive-generic, satisfied today by google/drive.js via
// snapshotSyncAdapter.js):
//   findChild(parentId, name)  -> { id, name, mimeType } | null
//   createFolder(parentId, name) -> { id, name }
//   listChildren(folderId)     -> [{ id, name, mimeType }]
//   getJson(fileId)            -> parsed JSON
//   putJson({ folderId, name, data, existingId? }) -> { id }
//   deleteFile(fileId)         -> void
//
// Layout: <projectFolder>/.opentakeoff/snapshots/<id>.json holds one full
// record. Remote ids are derivable from listChildren names (no download needed
// to enumerate). The `snapshots` subfolder is snapshot-exclusive, so nothing
// else races to write it — the only shared resource is the `.opentakeoff`
// sidecar folder, whose resolver is injected (see `ensureSidecarId`) so all
// writers agree on one folder instead of split-braining (adversarial F4).

const SIDECAR_NAME = ".opentakeoff";
const SNAP_FOLDER = "snapshots";
const FOLDER_MIME = "application/vnd.google-apps.folder";

// Race a promise against a timeout so opening the panel offline/slow-network
// never hangs the UI. On timeout the underlying work keeps running (a promise
// can't be cancelled) but its result is ignored; we attach handlers so a late
// rejection can't surface as an unhandled rejection.
function withTimeout(p, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("snapshot sync: timed out")), ms);
    p.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}

/**
 * @param {object} opts
 * @param {any} opts.base        the local snapshot store (localStore) — authoritative
 * @param {any} opts.provider    the injected cloud provider (see contract above)
 * @param {string} opts.folderId Drive project folder id; also the local snapshot scope
 * @param {() => Promise<string>} [opts.ensureSidecarId] shared `.opentakeoff` resolver.
 *   Inject cloudStore's resolver so all writers share ONE sidecar folder. When
 *   omitted (standalone/tests), this module resolves its own — fine when nothing
 *   else writes the sidecar concurrently.
 * @param {number} [opts.timeoutMs] cap on the awaited pull in listSnapshots
 */
export function createSnapshotSync({ base, provider, folderId, ensureSidecarId, timeoutMs = 2500 }) {
  // In-flight background pushes, keyed by snapshot id. Two consumers:
  //   • deleteSnapshot awaits the push for its id BEFORE deleting the remote
  //     file — otherwise a delete that races an unfinished push would find no
  //     file to delete, and the late push would create it and let a later pull
  //     resurrect the "deleted" snapshot.
  //   • whenIdle (test-only) awaits all of them; production never does (that's
  //     the point of fire-and-forget).
  const inflightPush = new Map();
  // Ids deleted this session. A push checks this immediately before writing and
  // skips if the id was deleted — so even when deleteSnapshot's wait-for-push is
  // cut short by the timeout cap, a push that lands late still won't recreate the
  // file (no resurrection) AND the delete never hangs. Ids are unique per save,
  // so this set never needs clearing.
  const deletedIds = new Set();

  // Resolve the shared `.opentakeoff` folder id. Injected resolver wins; else a
  // local memoized locate-else-create mirroring cloudStore.ensureSidecarId
  // (cache the promise, clear on failure so the next call retries).
  let sidecarP = null;
  const resolveSidecar = ensureSidecarId || function () {
    if (!sidecarP) {
      sidecarP = (async () => {
        const child = await provider.findChild(folderId, SIDECAR_NAME);
        if (child && child.mimeType === FOLDER_MIME) return child.id;
        const { id } = await provider.createFolder(folderId, SIDECAR_NAME);
        return id;
      })().catch((e) => { sidecarP = null; throw e; });
    }
    return sidecarP;
  };

  // Resolve the snapshot subfolder id, creating it once under the sidecar.
  let snapFolderP = null;
  function ensureSnapshotsFolderId() {
    if (!snapFolderP) {
      snapFolderP = (async () => {
        const sidecarId = await resolveSidecar();
        const child = await provider.findChild(sidecarId, SNAP_FOLDER);
        if (child && child.mimeType === FOLDER_MIME) return child.id;
        const { id } = await provider.createFolder(sidecarId, SNAP_FOLDER);
        return id;
      })().catch((e) => { snapFolderP = null; throw e; });
    }
    return snapFolderP;
  }

  // Fetch every remote record whose id isn't already local and materialize it
  // verbatim via putSnapshot (id-preserving → the union dedups by id with no
  // duplicates). Only ids MISSING locally are downloaded — enumeration is names
  // only. Push is never triggered from here (list/pull is read-only), which is
  // exactly why a delete can't resurrect: a pulled record enters via putSnapshot
  // and never becomes a push candidate.
  async function pullMissing(localList) {
    const localIds = new Set(localList.map((s) => s.id));
    const snapsFolder = await ensureSnapshotsFolderId();
    const children = await provider.listChildren(snapsFolder);
    for (const c of children) {
      if (!c.name || !c.name.endsWith(".json")) continue;
      const id = c.name.slice(0, -".json".length);
      if (!id || localIds.has(id)) continue;
      let record;
      try {
        record = await provider.getJson(c.id);
      } catch {
        continue; // a corrupt/unreadable remote file must not wedge the whole list
      }
      if (!record || record.id !== id) continue; // defensive: name/id must agree
      // Keep this project's scope: only materialize records that belong to this
      // folder. A record with no `project` (or a foreign one) is malformed for
      // this Drive folder — materializing it verbatim would leak it into the
      // anonymous/null local scope (store.js treats missing project as null).
      if ((record.project ?? null) !== folderId) continue;
      try {
        await base.putSnapshot(record);
      } catch {
        continue; // an incomplete record fails putSnapshot's guards — skip it
      }
    }
  }

  const api = {
    // Local write is authoritative and instant; the Drive push is fire-and-forget.
    // `project` defaults to this decorator's folderId but is honored when passed
    // explicitly (Slice 4c hands a scope here; cloudStore.saveSnapshot drops it,
    // so snapSync must win the spread AND respect the arg).
    async saveSnapshot(label, payload, project = folderId) {
      const meta = await base.saveSnapshot(label, payload, project);
      const push = (async () => {
        const record = await base.getSnapshot(meta.id, project);
        if (!record) return;
        const snapsFolder = await ensureSnapshotsFolderId();
        // Skip the write if the snapshot was already deleted (fast path — avoids
        // creating a file nobody wants). No await between here and putJson, so a
        // delete can't slip in during this check.
        if (deletedIds.has(meta.id)) return;
        const { id } = await provider.putJson({ folderId: snapsFolder, name: `${meta.id}.json`, data: record });
        // But a delete may have landed WHILE putJson was in flight: it added the
        // id and its own findChild ran before this file existed, so it deleted
        // nothing. This push is now the only thing that knows about the file it
        // just created — so it must clean up after itself. deleteSnapshot adds the
        // id BEFORE awaiting the push, so by the time we recheck here any started
        // delete is already visible. (Idempotent: if delete's findChild also
        // caught it, deleteFile on the gone id is a harmless swallowed no-op.)
        if (id && deletedIds.has(meta.id)) await provider.deleteFile(id).catch(() => {});
      })().catch(() => {
        // Swallow: local is canonical. A failed push means "not backed up yet",
        // surfaced by the Slice 6 status line — never asserted as backed up here.
      }).finally(() => {
        if (inflightPush.get(meta.id) === push) inflightPush.delete(meta.id);
      });
      inflightPush.set(meta.id, push);
      return meta;
    },

    // Awaited best-effort pull (fetch only missing ids) then return the local
    // scoped union. Capped by a timeout so offline/slow-network opens the panel
    // instantly with whatever is local rather than hanging.
    async listSnapshots(project = folderId) {
      const local = await base.listSnapshots(project);
      try {
        await withTimeout(pullMissing(local), timeoutMs);
      } catch {
        return local; // offline / slow / provider error → local list, no hang
      }
      return base.listSnapshots(project);
    },

    // Local only — a snapshot's payload is self-contained, so no network read.
    async getSnapshot(id, project = folderId) {
      return base.getSnapshot(id, project);
    },

    // Local delete is authoritative; then hard-delete the Drive file. We AWAIT
    // the remote delete (capped) so a subsequent online listSnapshots can't
    // resurrect the just-deleted snapshot by pulling a still-present file. If the
    // remote delete fails (offline), local is already gone and the remote file
    // lingers — it may resurrect on the next ONLINE list (no tombstones in v1;
    // upgrade path: a deleted-ids set). Offline listSnapshots can't pull anyway,
    // so the window is: delete-offline → later come online → list.
    async deleteSnapshot(id) {
      await base.deleteSnapshot(id);
      // Mark deleted FIRST, before awaiting anything. This is what makes the
      // ordering safe: a still-resolving push sees it and skips its write, and a
      // push already past that guard sees it on its post-putJson recheck and
      // deletes the file it created (see saveSnapshot). Setting it before the
      // await guarantees any push that started is visible to both checks.
      deletedIds.add(id);
      // Then briefly wait out an in-flight push so, in the common (fast) case,
      // the file exists before our findChild below deletes it. Capped by the
      // timeout so a hung/slow push never hangs the delete — if the cap fires
      // first, the push's own post-write cleanup removes any file it later
      // creates, so there's still no resurrection.
      const push = inflightPush.get(id);
      if (push) { try { await withTimeout(push, timeoutMs); } catch { /* capped or already swallowed */ } }
      try {
        await withTimeout((async () => {
          const snapsFolder = await ensureSnapshotsFolderId();
          const child = await provider.findChild(snapsFolder, `${id}.json`);
          if (child) await provider.deleteFile(child.id);
        })(), timeoutMs);
      } catch {
        // best-effort remote delete; see note above
      }
    },
  };

  // Test-only quiescence hook, non-enumerable so it never widens the store's
  // shape (Object.keys stays the 4 methods — snapSync must never shadow
  // addSheets et al. when spread into the composite store).
  Object.defineProperty(api, "whenIdle", {
    enumerable: false,
    value: async () => { while (inflightPush.size) await Promise.all([...inflightPush.values()]); },
  });

  return api;
}
