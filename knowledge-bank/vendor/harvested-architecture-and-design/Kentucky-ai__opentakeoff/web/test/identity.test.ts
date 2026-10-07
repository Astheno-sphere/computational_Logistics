// Company identity: localStorage load/save resilience. normalizeLogoToPng is
// browser-only (createImageBitmap / <canvas> / Image don't exist in node) —
// exercised in the app, deliberately NOT here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadCompany, saveCompany, LOGO_LIMIT, loadProfiles, saveProfiles, addProfile, setActiveProfile, updateActiveProfile, removeProfile, activeProfile } from "../src/lib/identity.js";

function stubStore() {
  const store = new Map<string, string>();
  (globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k) : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
  };
  return store;
}

test("loadProfiles migrates a legacy single company into one active profile", () => {
  const store = stubStore();
  try {
    store.set("opentakeoff_company", '{"name":"345 Flooring","address":"Lynnwood, WA"}');
    const s = loadProfiles();
    assert.equal(s.profiles.length, 1);
    assert.equal(s.profiles[0].name, "345 Flooring");
    assert.equal(s.profiles[0].address, "Lynnwood, WA");
    assert.equal(s.activeId, s.profiles[0].id);
    assert.deepEqual(activeProfile(s), s.profiles[0]);
  } finally {
    delete (globalThis as any).localStorage;
  }
});

test("loadCompany returns {} without localStorage; saveCompany reports failure", () => {
  assert.equal(typeof globalThis.localStorage, "undefined"); // node test env
  assert.deepEqual(loadCompany(), {});                        // ReferenceError swallowed
  assert.equal(saveCompany({ name: "Acme" }), false);         // can't persist, says so
});

test("loadCompany: malformed / non-object payloads collapse to {}", () => {
  const store = new Map<string, string>();
  (globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k) : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
  };
  try {
    assert.deepEqual(loadCompany(), {});                      // missing key
    store.set("opentakeoff_company", "not json {{{");
    assert.deepEqual(loadCompany(), {});                      // corrupt JSON
    store.set("opentakeoff_company", '["a","b"]');
    assert.deepEqual(loadCompany(), {});                      // array is not an object here
    store.set("opentakeoff_company", '"just a string"');
    assert.deepEqual(loadCompany(), {});                      // JSON, but not an object
    store.set("opentakeoff_company", "null");
    assert.deepEqual(loadCompany(), {});                      // null parses, still {}
    store.set("opentakeoff_company", '{"name":"Acme Floors","logo":"data:image/png;base64,AA=="}');
    assert.deepEqual(loadCompany(), { name: "Acme Floors", logo: "data:image/png;base64,AA==" });
    store.set("opentakeoff_company", '{"name":42,"address":{"street":"x"},"logo":"data:,ok"}');
    assert.deepEqual(loadCompany(), { logo: "data:,ok" });    // non-string values dropped
  } finally {
    delete (globalThis as any).localStorage;
  }
});

test("reducers: add / set-active / update-active / remove", () => {
  let { state } = addProfile({ profiles: [], activeId: null }, { name: "345 Flooring" });
  assert.equal(state.profiles.length, 1);
  assert.equal(activeProfile(state).name, "345 Flooring");
  ({ state } = addProfile(state, { name: "Fin Workspaces" }));
  assert.equal(state.profiles.length, 2);
  assert.equal(activeProfile(state).name, "Fin Workspaces");        // new profile is active
  const firstId = state.profiles[0].id;
  state = setActiveProfile(state, firstId);
  assert.equal(activeProfile(state).name, "345 Flooring");
  state = updateActiveProfile(state, { address: "Lynnwood, WA" });
  assert.equal(activeProfile(state).address, "Lynnwood, WA");
  assert.equal(state.profiles[1].address, undefined);               // the other profile untouched
  state = updateActiveProfile(state, { address: "" });
  assert.equal(activeProfile(state).address, undefined);            // clearing a field drops it
  state = removeProfile(state, firstId);
  assert.equal(state.profiles.length, 1);
  assert.equal(activeProfile(state).name, "Fin Workspaces");        // active falls back to remaining
  assert.equal(state.activeId, state.profiles[0].id);
  assert.equal(setActiveProfile(state, "nope"), state);            // unknown id is a no-op
});

test("profile fields are trimmed and empties dropped, matching the legacy mirror", () => {
  let { state } = addProfile({ profiles: [], activeId: null }, { name: "   ", address: "  Lynnwood, WA  " });
  assert.equal(activeProfile(state).name, undefined);            // whitespace-only dropped, not "   "
  assert.equal(activeProfile(state).address, "Lynnwood, WA");    // trimmed
  state = updateActiveProfile(state, { name: "  345 Flooring  " });
  assert.equal(activeProfile(state).name, "345 Flooring");
});

test("saveProfiles round-trips and mirrors the active profile to loadCompany", () => {
  const store = stubStore();
  try {
    let { state } = addProfile({ profiles: [], activeId: null }, { name: "345 Flooring", address: "A" });
    ({ state } = addProfile(state, { name: "Fin Workspaces", address: "B" }));
    assert.equal(saveProfiles(state), true);
    const reloaded = loadProfiles();
    assert.equal(reloaded.profiles.length, 2);
    assert.equal(activeProfile(reloaded).name, "Fin Workspaces");
    assert.deepEqual(loadCompany(), { name: "Fin Workspaces", address: "B" });   // masthead sees active
    saveProfiles(setActiveProfile(reloaded, reloaded.profiles[0].id));
    assert.deepEqual(loadCompany(), { name: "345 Flooring", address: "A" });     // switch → mirror updates
  } finally {
    delete (globalThis as any).localStorage;
  }
});

test("saveCompany drops empty fields; nothing left removes the key", () => {
  const store = new Map<string, string>();
  (globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k) : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
  };
  try {
    assert.equal(saveCompany({ name: "Acme Floors", address: "  ", logo: "" }), true);
    assert.deepEqual(loadCompany(), { name: "Acme Floors" });  // blank address + empty logo dropped
    assert.equal(saveCompany({ name: "", address: "" }), true);
    assert.equal(store.has("opentakeoff_company"), false);     // {} → removeItem, not "{}"
    assert.deepEqual(loadCompany(), {});
  } finally {
    delete (globalThis as any).localStorage;
  }
});

test("LOGO_LIMIT is the documented cap", () => {
  assert.equal(LOGO_LIMIT, 200_000);
});
