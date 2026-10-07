import { getStorageNamespace } from '../auth.js';

const DB_NAME = 'countymap-research-browser-store';
const DB_VERSION = 2;
const STORE_NAME = 'corpora';
const INSTALL_MANIFEST_STORE = 'install_manifests';
const SOURCE_ARTIFACT_STORE = 'source_artifacts';

function openDb() {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error || new Error('IndexedDB open failed'));
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'storageKey' });
        store.createIndex('namespace', 'namespace', { unique: false });
      }
      if (!db.objectStoreNames.contains(INSTALL_MANIFEST_STORE)) {
        const store = db.createObjectStore(INSTALL_MANIFEST_STORE, { keyPath: 'storageKey' });
        store.createIndex('namespace', 'namespace', { unique: false });
      }
      if (!db.objectStoreNames.contains(SOURCE_ARTIFACT_STORE)) {
        const store = db.createObjectStore(SOURCE_ARTIFACT_STORE, { keyPath: 'storageKey' });
        store.createIndex('namespace', 'namespace', { unique: false });
        store.createIndex('sourceId', 'sourceId', { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
  });
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed'));
    request.onsuccess = () => resolve(request.result);
  });
}

function buildStorageKey(namespace, corpusId) {
  return `${namespace}::${corpusId}`;
}

function buildInstallManifestStorageKey(namespace, corpusId) {
  return `${namespace}::manifest::${corpusId}`;
}

function buildSourceArtifactStorageKey(namespace, sourceId, artifactVersion) {
  return `${namespace}::source::${sourceId}::${artifactVersion || 'unknown'}`;
}

function summarizeRecord(record) {
  if (!record) return null;
  return {
    corpusId: record.corpusId,
    corpusName: record.corpusName,
    namespace: record.namespace,
    corpusUpdatedAt: record.corpusUpdatedAt || null,
    savedAt: record.savedAt || null,
    status: record.status || 'complete',
    sizeBytes: Number(record.sizeBytes || 0),
    payloadBytes: Number(record.payloadBytes || 0),
    sizeKind: String(record.sizeKind || 'payload'),
    artifactCount: Number(record.artifactCount || 0),
    sourceCount: Number(record.sourceCount || 0),
    packCount: Number(record.packCount || 0)
  };
}

async function getLocalInstallManifestRecord(namespace, corpusId) {
  const db = await openDb();
  const record = await requestToPromise(
    db.transaction(INSTALL_MANIFEST_STORE, 'readonly')
      .objectStore(INSTALL_MANIFEST_STORE)
      .get(buildInstallManifestStorageKey(namespace, corpusId))
  );
  db.close();
  return record || null;
}

async function listLocalSourceArtifactRecords(namespace) {
  const db = await openDb();
  const tx = db.transaction(SOURCE_ARTIFACT_STORE, 'readonly');
  const index = tx.objectStore(SOURCE_ARTIFACT_STORE).index('namespace');
  const records = await requestToPromise(index.getAll(namespace));
  db.close();
  return Array.isArray(records) ? records : [];
}

async function listLocalSourceArtifactRecordsForCorpus(namespace, corpusId) {
  const records = await listLocalSourceArtifactRecords(namespace);
  return records.filter((record) => Array.isArray(record?.corpusIds) && record.corpusIds.includes(corpusId));
}

async function listLocalBrowserCorpusRecords(namespace) {
  const db = await openDb();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const index = tx.objectStore(STORE_NAME).index('namespace');
  const records = await requestToPromise(index.getAll(namespace));
  db.close();
  return Array.isArray(records) ? records : [];
}

export async function listBrowserCorpusRecords() {
  const namespace = getStorageNamespace();
  const db = await openDb();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const index = tx.objectStore(STORE_NAME).index('namespace');
  const records = await requestToPromise(index.getAll(namespace));
  db.close();
  return Array.isArray(records) ? records : [];
}

export async function listBrowserCorpusSummaries() {
  const records = await listBrowserCorpusRecords();
  return records.map(summarizeRecord);
}

export async function removeBrowserCorpusSnapshot(corpusId) {
  if (!corpusId) return;
  const namespace = getStorageNamespace();
  const db = await openDb();
  const artifactRecords = await listLocalSourceArtifactRecordsForCorpus(namespace, corpusId);
  const tx = db.transaction([STORE_NAME, INSTALL_MANIFEST_STORE, SOURCE_ARTIFACT_STORE], 'readwrite');
  await requestToPromise(tx.objectStore(STORE_NAME).delete(buildStorageKey(namespace, corpusId)));
  await requestToPromise(tx.objectStore(INSTALL_MANIFEST_STORE).delete(buildInstallManifestStorageKey(namespace, corpusId)));
  const artifactStore = tx.objectStore(SOURCE_ARTIFACT_STORE);
  for (const record of artifactRecords) {
    const remainingCorpusIds = (record?.corpusIds || []).filter((id) => id && id !== corpusId);
    if (remainingCorpusIds.length) {
      await requestToPromise(artifactStore.put({
        ...record,
        corpusIds: remainingCorpusIds
      }));
    } else if (record?.storageKey) {
      await requestToPromise(artifactStore.delete(record.storageKey));
    }
  }
  db.close();
}

export async function clearAllBrowserCorpusSnapshots() {
  const namespace = getStorageNamespace();
  const records = await listBrowserCorpusRecords();
  const manifestRecords = [];
  const artifactRecords = await listLocalSourceArtifactRecords(namespace);
  for (const record of records) {
    manifestRecords.push(buildInstallManifestStorageKey(namespace, record?.corpusId));
  }
  const db = await openDb();
  const tx = db.transaction([STORE_NAME, INSTALL_MANIFEST_STORE, SOURCE_ARTIFACT_STORE], 'readwrite');
  const store = tx.objectStore(STORE_NAME);
  const manifestStore = tx.objectStore(INSTALL_MANIFEST_STORE);
  const artifactStore = tx.objectStore(SOURCE_ARTIFACT_STORE);
  for (const record of records) {
    if (record?.namespace === namespace && record?.storageKey) {
      store.delete(record.storageKey);
    }
  }
  for (const storageKey of manifestRecords) {
    manifestStore.delete(storageKey);
  }
  for (const record of artifactRecords) {
    if (record?.namespace === namespace && record?.storageKey) {
      artifactStore.delete(record.storageKey);
    }
  }
  await new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('IndexedDB clear failed'));
    tx.onabort = () => reject(tx.error || new Error('IndexedDB clear aborted'));
  });
  db.close();
}

export async function getBrowserCorpusStorageSummary() {
  const summaries = await listBrowserCorpusSummaries();
  const totalBytes = summaries.reduce((sum, item) => sum + Number(item?.sizeBytes || 0), 0);
  const estimate = await navigator.storage?.estimate?.().catch(() => null);
  return {
    totalBytes,
    corpusCount: summaries.length,
    quotaBytes: Number(estimate?.quota || 0),
    usageBytes: Number(estimate?.usage || 0),
    summaries
  };
}

export async function saveBrowserCorpusInstallManifest({ corpusId, corpusName, corpusUpdatedAt, installManifest }) {
  if (!corpusId || !installManifest) throw new Error('Missing browser install manifest');
  const namespace = getStorageNamespace();
  const record = {
    storageKey: buildInstallManifestStorageKey(namespace, corpusId),
    namespace,
    corpusId,
    corpusName: corpusName || installManifest?.saved_corpus?.name || corpusId,
    corpusUpdatedAt: corpusUpdatedAt || installManifest?.saved_corpus?.updated_at || null,
    savedAt: new Date().toISOString(),
    manifestVersion: Number(installManifest?.manifest_version || 1),
    sourceCount: Number(installManifest?.saved_corpus?.resolved_source_count || installManifest?.sources?.length || 0),
    totals: installManifest?.totals || null,
    installManifest
  };
  const db = await openDb();
  const tx = db.transaction(INSTALL_MANIFEST_STORE, 'readwrite');
  await requestToPromise(tx.objectStore(INSTALL_MANIFEST_STORE).put(record));
  db.close();
  return record;
}

export async function saveBrowserCorpusInstallSummary({ corpusId, corpusName, corpusUpdatedAt, installManifest }) {
  if (!corpusId || !installManifest) throw new Error('Missing browser install summary');
  const namespace = getStorageNamespace();
  const totals = installManifest?.totals || {};
  const savedCorpus = installManifest?.saved_corpus || {};
  const installMode = String(installManifest?.install_mode || '').trim() || 'manifest_only';
  const record = {
    storageKey: buildStorageKey(namespace, corpusId),
    namespace,
    corpusId,
    corpusName: corpusName || savedCorpus.name || corpusId,
    corpusUpdatedAt: corpusUpdatedAt || savedCorpus.updated_at || null,
    savedAt: new Date().toISOString(),
    status: 'complete',
    sizeBytes: Number(installMode === 'source_artifacts' ? (totals.stored_bytes || 0) : 0),
    payloadBytes: Number(installMode === 'source_artifacts' ? (totals.transfer_bytes || totals.stored_bytes || 0) : 0),
    sizeKind: installMode === 'source_artifacts' ? 'catalog' : 'manifest',
    artifactCount: Number(installMode === 'source_artifacts' ? (savedCorpus.artifact_ready_source_count || installManifest?.sources?.length || 0) : 0),
    sourceCount: Number(savedCorpus.resolved_source_count || installManifest?.sources?.length || 0),
    packCount: Number(savedCorpus.pack_count || 0)
  };
  const db = await openDb();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  await requestToPromise(tx.objectStore(STORE_NAME).put(record));
  db.close();
  return summarizeRecord(record);
}

export async function getBrowserCorpusInstallManifest(corpusId) {
  if (!corpusId) return null;
  const namespace = getStorageNamespace();
  return await getLocalInstallManifestRecord(namespace, corpusId);
}

export async function saveBrowserSourceArtifact({ sourceId, artifactVersion, sha256, payload, browserArtifact, corpusId = '' }) {
  if (!sourceId || !artifactVersion || !payload) throw new Error('Missing browser source artifact payload');
  const namespace = getStorageNamespace();
  const storageKey = buildSourceArtifactStorageKey(namespace, sourceId, artifactVersion);
  const existingRecord = await (async () => {
    const db = await openDb();
    const record = await requestToPromise(
      db.transaction(SOURCE_ARTIFACT_STORE, 'readonly')
        .objectStore(SOURCE_ARTIFACT_STORE)
        .get(storageKey)
    );
    db.close();
    return record || null;
  })();
  const corpusIds = Array.from(new Set([
    ...(Array.isArray(existingRecord?.corpusIds) ? existingRecord.corpusIds : []),
    ...(corpusId ? [String(corpusId)] : [])
  ]));
  const record = {
    storageKey,
    namespace,
    sourceId,
    artifactVersion,
    sha256: String(sha256 || browserArtifact?.sha256 || ''),
    corpusIds,
    savedAt: new Date().toISOString(),
    payloadBytes: payload instanceof ArrayBuffer ? payload.byteLength : (ArrayBuffer.isView(payload) ? payload.byteLength : 0),
    browserArtifact: browserArtifact || null,
    payload
  };
  const db = await openDb();
  const tx = db.transaction(SOURCE_ARTIFACT_STORE, 'readwrite');
  await requestToPromise(tx.objectStore(SOURCE_ARTIFACT_STORE).put(record));
  db.close();
  return record;
}

export async function getBrowserSourceArtifact(sourceId, artifactVersion) {
  if (!sourceId || !artifactVersion) return null;
  const namespace = getStorageNamespace();
  const db = await openDb();
  const record = await requestToPromise(
    db.transaction(SOURCE_ARTIFACT_STORE, 'readonly')
      .objectStore(SOURCE_ARTIFACT_STORE)
      .get(buildSourceArtifactStorageKey(namespace, sourceId, artifactVersion))
  );
  db.close();
  return record || null;
}

export async function getBrowserCorpusInstallBundle(corpusId) {
  if (!corpusId) return null;
  const manifestRecord = await getBrowserCorpusInstallManifest(corpusId);
  if (!manifestRecord?.installManifest) return null;
  const resolvedSourceIds = manifestRecord.installManifest?.saved_corpus?.resolved_source_ids || [];
  const artifactRecords = [];
  for (const sourceEntry of manifestRecord.installManifest?.sources || []) {
    const sourceId = String(sourceEntry?.source_id || '').trim();
    const artifactVersion = String(sourceEntry?.browser_artifact?.artifact_version || '').trim();
    if (!sourceId || !artifactVersion || !resolvedSourceIds.includes(sourceId)) continue;
    const record = await getBrowserSourceArtifact(sourceId, artifactVersion);
    if (record) artifactRecords.push(record);
  }
  return {
    manifestRecord,
    artifactRecords
  };
}
