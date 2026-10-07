const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
const { PedraApiError } = require("@pedra-ai/sdk");
const { createServer } = require("../dist/server.js");

const EXPECTED_TOOLS = [
  "pedra_enhance",
  "pedra_enhance_and_correct_perspective",
  "pedra_empty_room",
  "pedra_furnish",
  "pedra_renovation",
  "pedra_edit_via_prompt",
  "pedra_sky_blue",
  "pedra_remove_object",
  "pedra_blur",
  "pedra_create_video",
  "pedra_update_video",
  "pedra_generate_voice_script",
  "pedra_generate_voice",
  "pedra_music_library",
  "pedra_list_properties",
  "pedra_list_property_images",
  "pedra_create_property",
  "pedra_add_images_to_property",
  "pedra_add_local_panoramas",
  "pedra_create_upload_link",
  "pedra_create_virtual_tour",
  "pedra_get_virtual_tour",
  "pedra_list_virtual_tours",
  "pedra_update_virtual_tour",
  "pedra_add_virtual_tour_scenes",
  "pedra_credits",
  "pedra_feedback",
];

const TOUR = {
  tourId: "t1",
  propertyId: "p1",
  name: "Calle Mayor 12",
  status: "ready",
  tourUrl: "https://app.pedra.ai/virtual-tour/t1",
  embedCode: "<iframe src=\"https://app.pedra.ai/virtual-tour/t1\"></iframe>",
  shareable: true,
  sceneCount: 2,
  linkCount: 2,
  scenes: [{ sceneId: "s1", name: "Entrance" }],
  links: [{ fromSceneId: "s1", toSceneId: "s2", yaw: -18, pitch: 0 }],
};

function fakeClient(overrides = {}) {
  const img = (url) => ({ message: "ok", url, urls: [url], raw: {} });
  return {
    enhance: async () => img("https://img.pedra.ai/enhanced"),
    enhanceAndCorrectPerspective: async () => img("https://img.pedra.ai/persp"),
    empty: async () => img("https://img.pedra.ai/empty"),
    furnish: async () => img("https://img.pedra.ai/furnish"),
    renovation: async () => img("https://img.pedra.ai/reno"),
    editViaPrompt: async () => img("https://img.pedra.ai/edit"),
    sky: async () => img("https://img.pedra.ai/sky"),
    remove: async () => img("https://img.pedra.ai/remove"),
    blur: async () => img("https://img.pedra.ai/blur"),
    createVideo: async () => ({
      message: "done",
      videoId: "v1",
      videoUrl: "https://img.pedra.ai/video.mp4",
      raw: {},
    }),
    updateVideo: async () => ({
      message: "updated",
      videoId: "v1",
      videoUrl: "https://img.pedra.ai/video2.mp4",
      raw: {},
    }),
    generateVoiceScript: async () => ({
      message: "ok",
      script: "A bright, airy home.",
      raw: {},
    }),
    generateVoice: async () => ({
      message: "ok",
      audioId: "a1",
      audioUrl: "https://img.pedra.ai/audio/a1.mp3",
      alignmentUrl: "https://img.pedra.ai/audio/a1.alignment.json",
      duration: 7,
      raw: {},
    }),
    musicLibrary: async () => ({
      tracks: [{ track: "chill", label: "Chill Beats" }],
      variantsPerTrack: 6,
      defaultTrack: "chill",
      voiceLanguages: ["English"],
      raw: {},
    }),
    listProperties: async () => ({
      properties: [{ propertyId: "p1", name: "Listing", photoCount: 3, appUrl: "https://app.pedra.ai/?propertyId=p1" }],
      raw: {},
    }),
    listPropertyImages: async () => ({
      propertyId: "p1",
      name: "Listing",
      images: [{ imageId: "i1", url: "https://img.pedra.ai/i1", aspectRatio: 1.5 }],
      raw: {},
    }),
    createProperty: async () => ({
      message: "Property created",
      propertyId: "p2",
      appUrl: "https://app.pedra.ai/?propertyId=p2",
      raw: {},
    }),
    addImagesToProperty: async () => ({
      message: "Added 1 image(s)",
      propertyId: "p1",
      added: [{ imageId: "i9", url: "https://img.pedra.ai/i9" }],
      failed: [],
      appUrl: "https://app.pedra.ai/?propertyId=p1",
      raw: {},
    }),
    addLocalPanoramas: async (propertyId, paths) => ({
      message: `Added ${paths.length} 360° photo(s)`,
      propertyId,
      type: "360",
      added: paths.map((p, i) => ({ imageId: `s${i + 1}`, url: `https://img.pedra.ai/s${i + 1}`, aspectRatio: 2, path: p })),
      failed: [],
      appUrl: "https://app.pedra.ai/?projectId=p1",
      raw: undefined,
    }),
    createUploadLink: async () => ({
      message: "Send this link",
      uploadUrl: "https://app.pedra.ai/upload/tok",
      propertyId: "p9",
      propertyName: "Calle Mayor 12",
      expiresAt: "2026-10-01T15:26:30.687Z",
      appUrl: "https://app.pedra.ai/?projectId=p9",
      raw: {},
    }),
    createVirtualTour: async () => ({ ...TOUR, status: "processing", progress: { stage: "queued" }, creditsCost: 3, raw: {} }),
    getVirtualTour: async () => ({ ...TOUR, raw: {} }),
    listVirtualTours: async () => ({ tours: [{ tourId: "t1", status: "ready" }], raw: {} }),
    updateVirtualTour: async () => ({ ...TOUR, name: "Renamed", raw: {} }),
    addVirtualTourScenes: async () => ({ ...TOUR, status: "processing", addedScenes: [{ sceneId: "s3" }], raw: {} }),
    credits: async () => ({ plan: "pro", creditsRemaining: 42, raw: {} }),
    feedback: async () => ({ message: "thanks", creditedBack: true, raw: {} }),
    ...overrides,
  };
}

async function connect(client) {
  const server = createServer(client);
  const [clientTransport, serverTransport] =
    InMemoryTransport.createLinkedPair();
  const mcp = new Client({ name: "test", version: "0.0.0" });
  await Promise.all([
    server.connect(serverTransport),
    mcp.connect(clientTransport),
  ]);
  return mcp;
}

function textOf(result) {
  return (result.content || [])
    .filter((c) => c.type === "text")
    .map((c) => c.text)
    .join("\n");
}

test("exposes exactly the expected tools", async () => {
  const mcp = await connect(fakeClient());
  const { tools } = await mcp.listTools();
  const names = tools.map((t) => t.name).sort();
  assert.deepStrictEqual(names, [...EXPECTED_TOOLS].sort());
  for (const t of tools) {
    assert.ok(t.description && t.description.length > 0, `${t.name} has a description`);
  }
});

test("credits returns plan + remaining", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_credits", arguments: {} });
  assert.ok(!res.isError);
  const text = textOf(res);
  assert.match(text, /pro/);
  assert.match(text, /42/);
});

test("enhance returns the asset URL and is not an error", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_enhance",
    arguments: { imageUrl: "https://example.com/room.jpg" },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /https:\/\/img\.pedra\.ai\/enhanced/);
});

test("edit tools forward propertyId and name and return source", async () => {
  let got;
  const mcp = await connect(
    fakeClient({
      furnish: async (params) => {
        got = params;
        return {
          url: "https://img.pedra.ai/furnish",
          urls: ["https://img.pedra.ai/furnish"],
          source: { imageId: "img1", name: "IMG_0412.jpg" },
          raw: {},
        };
      },
    }),
  );
  const res = await mcp.callTool({
    name: "pedra_furnish",
    arguments: { imageUrl: "https://example.com/room.jpg", propertyId: "p1", name: "IMG_0412.jpg" },
  });
  assert.ok(!res.isError);
  assert.equal(got.propertyId, "p1");
  assert.equal(got.name, "IMG_0412.jpg");
  assert.match(textOf(res), /IMG_0412\.jpg/);
});

test("every image-editing tool accepts propertyId, name and preserveAspectRatio", async () => {
  const mcp = await connect(fakeClient());
  const { tools } = await mcp.listTools();
  for (const name of EXPECTED_TOOLS.slice(0, 9)) {
    const props = tools.find((t) => t.name === name).inputSchema.properties;
    for (const key of ["propertyId", "name", "preserveAspectRatio"]) {
      assert.ok(props[key], `${name} is missing ${key}`);
    }
  }
});

test("create_video returns the finished video URL", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_create_video",
    arguments: { images: [{ imageUrl: "https://example.com/a.jpg" }] },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /video\.mp4/);
});

test("update_video returns the re-rendered video URL", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_update_video",
    arguments: { videoId: "v1", music: { track: "cinematic" } },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /video2\.mp4/);
});

test("update_video requires a videoId", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_update_video",
    arguments: { music: { track: "chill" } },
  });
  assert.strictEqual(res.isError, true);
});

test("generate_voice returns an audioId", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_generate_voice",
    arguments: { text: "A bright, airy home in the heart of the city." },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /"audioId": "a1"/);
});

test("generate_voice_script returns script text", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_generate_voice_script",
    arguments: { images: ["https://example.com/a.jpg"] },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /bright, airy home/);
});

test("music_library lists tracks", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_music_library", arguments: {} });
  assert.ok(!res.isError);
  assert.match(textOf(res), /cinematic|chill/);
});

test("list_properties returns properties", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_list_properties", arguments: {} });
  assert.ok(!res.isError);
  assert.match(textOf(res), /"propertyId": "p1"/);
});

test("list_property_images returns photo URLs", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_list_property_images", arguments: { propertyId: "p1" } });
  assert.ok(!res.isError);
  assert.match(textOf(res), /img\.pedra\.ai\/i1/);
});

test("create_property returns id + appUrl", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_property", arguments: { name: "New" } });
  assert.ok(!res.isError);
  assert.match(textOf(res), /propertyId=p2/);
});

test("create_property requires nothing (name optional)", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_property", arguments: {} });
  assert.ok(!res.isError);
});

test("add_images_to_property requires propertyId + imageUrls", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_add_images_to_property", arguments: { propertyId: "p1" } });
  assert.strictEqual(res.isError, true);
});

test("add_images_to_property returns stored URLs", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_add_images_to_property",
    arguments: { propertyId: "p1", imageUrls: ["https://x/a.jpg"] },
  });
  assert.ok(!res.isError);
  assert.match(textOf(res), /img\.pedra\.ai\/i9/);
});

test("API errors surface as tool errors, not crashes", async () => {
  const mcp = await connect(
    fakeClient({
      enhance: async () => {
        throw new PedraApiError("Insufficient credits", 402);
      },
    }),
  );
  const res = await mcp.callTool({
    name: "pedra_enhance",
    arguments: { imageUrl: "https://example.com/room.jpg" },
  });
  assert.strictEqual(res.isError, true);
  const text = textOf(res);
  assert.match(text, /Insufficient credits/);
  assert.match(text, /402/);
});

test("invalid input (missing required imageUrl) is rejected", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_edit_via_prompt",
    arguments: { prompt: "make it brighter" },
  });
  assert.strictEqual(res.isError, true);
});

// Captures the args the client receives so we can assert on what the server
// forwards to the API after local-image resolution.
function capturingClient() {
  const seen = {};
  const img = (url) => ({ message: "ok", url, urls: [url], raw: {} });
  return {
    client: fakeClient({
      enhance: async (a) => {
        seen.enhance = a;
        return img("https://img.pedra.ai/enhanced");
      },
      createVideo: async (a) => {
        seen.createVideo = a;
        return {
          message: "done",
          videoId: "v1",
          videoUrl: "https://img.pedra.ai/video.mp4",
          raw: {},
        };
      },
    }),
    seen,
  };
}

test("a local image path is read and inlined as a base64 data URI", async () => {
  const file = path.join(os.tmpdir(), `pedra-mcp-test-${process.pid}.png`);
  fs.writeFileSync(file, Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a]));
  const { client, seen } = capturingClient();
  const mcp = await connect(client);
  try {
    const res = await mcp.callTool({
      name: "pedra_enhance",
      arguments: { imageUrl: file },
    });
    assert.ok(!res.isError, textOf(res));
    assert.match(seen.enhance.imageUrl, /^data:image\/png;base64,/);
  } finally {
    fs.rmSync(file, { force: true });
  }
});

test("remote URLs and data URIs pass through untouched", async () => {
  const { client, seen } = capturingClient();
  const mcp = await connect(client);
  await mcp.callTool({
    name: "pedra_enhance",
    arguments: { imageUrl: "https://example.com/room.jpg" },
  });
  assert.strictEqual(seen.enhance.imageUrl, "https://example.com/room.jpg");

  const dataUri = "data:image/png;base64,AAAA";
  await mcp.callTool({
    name: "pedra_enhance",
    arguments: { imageUrl: dataUri },
  });
  assert.strictEqual(seen.enhance.imageUrl, dataUri);
});

test("per-frame local paths in create_video are inlined too", async () => {
  const file = path.join(os.tmpdir(), `pedra-mcp-video-${process.pid}.jpg`);
  fs.writeFileSync(file, Buffer.from([0xff, 0xd8, 0xff]));
  const { client, seen } = capturingClient();
  const mcp = await connect(client);
  try {
    await mcp.callTool({
      name: "pedra_create_video",
      arguments: { images: [{ imageUrl: file }] },
    });
    assert.match(seen.createVideo.images[0].imageUrl, /^data:image\/jpeg;base64,/);
  } finally {
    fs.rmSync(file, { force: true });
  }
});

test("a missing local file surfaces as a tool error, not a crash", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_enhance",
    arguments: { imageUrl: "/no/such/file/definitely-missing.png" },
  });
  assert.strictEqual(res.isError, true);
  assert.match(textOf(res), /Could not read local image/);
});

test("an unsupported local file type is rejected with a clear message", async () => {
  const file = path.join(os.tmpdir(), `pedra-mcp-test-${process.pid}.txt`);
  fs.writeFileSync(file, "not an image");
  const mcp = await connect(fakeClient());
  try {
    const res = await mcp.callTool({
      name: "pedra_enhance",
      arguments: { imageUrl: file },
    });
    assert.strictEqual(res.isError, true);
    assert.match(textOf(res), /Unsupported local image type/);
  } finally {
    fs.rmSync(file, { force: true });
  }
});

// --- virtual tours -----------------------------------------------------------

function recordingClient(names) {
  const seen = {};
  const overrides = {};
  const base = fakeClient();
  for (const name of names) {
    overrides[name] = async (...args) => {
      seen[name] = args;
      return base[name](...args);
    };
  }
  return { client: fakeClient(overrides), seen };
}

test("tour tools carry the remote server's annotations", async () => {
  const mcp = await connect(fakeClient());
  const { tools } = await mcp.listTools();
  const byName = Object.fromEntries(tools.map((t) => [t.name, t]));
  assert.strictEqual(byName.pedra_get_virtual_tour.annotations.readOnlyHint, true);
  assert.strictEqual(byName.pedra_list_virtual_tours.annotations.readOnlyHint, true);
  assert.strictEqual(byName.pedra_update_virtual_tour.annotations.destructiveHint, true);
  assert.strictEqual(byName.pedra_create_virtual_tour.annotations.readOnlyHint, false);
  assert.match(byName.pedra_add_local_panoramas.description, /LOCAL-ONLY/);
  // `type` is exposed on both property-image tools.
  assert.deepStrictEqual(byName.pedra_list_property_images.inputSchema.properties.type.enum, ["photo", "360"]);
  assert.deepStrictEqual(byName.pedra_add_images_to_property.inputSchema.properties.type.enum, ["photo", "360"]);
  assert.deepStrictEqual(byName.pedra_update_virtual_tour.inputSchema.required, ["tourId"]);
  assert.deepStrictEqual([...byName.pedra_add_virtual_tour_scenes.inputSchema.required].sort(), ["scenes", "tourId"]);
});

test("list_property_images forwards type 360", async () => {
  const { client, seen } = recordingClient(["listPropertyImages"]);
  const mcp = await connect(client);
  const res = await mcp.callTool({ name: "pedra_list_property_images", arguments: { propertyId: "p1", type: "360" } });
  assert.ok(!res.isError, textOf(res));
  assert.strictEqual(seen.listPropertyImages[0].type, "360");
});

test("add_images_to_property rejects an unknown type", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_add_images_to_property",
    arguments: { propertyId: "p1", imageUrls: ["https://x/a.jpg"], type: "panorama" },
  });
  assert.strictEqual(res.isError, true);
});

test("create_virtual_tour returns the tourId and strips raw", async () => {
  const { client, seen } = recordingClient(["createVirtualTour"]);
  const mcp = await connect(client);
  const res = await mcp.callTool({
    name: "pedra_create_virtual_tour",
    arguments: { name: "Calle Mayor 12", scenes: [{ imageUrl: "https://x/pano.jpg", name: "Entrance" }], linking: "smart", language: "es" },
  });
  assert.ok(!res.isError, textOf(res));
  assert.strictEqual(seen.createVirtualTour[0].linking, "smart");
  assert.strictEqual(seen.createVirtualTour[0].scenes[0].name, "Entrance");
  const out = JSON.parse(textOf(res));
  assert.strictEqual(out.tourId, "t1");
  assert.strictEqual(out.status, "processing");
  assert.ok(!("raw" in out));
});

test("create_virtual_tour with only a propertyId is valid", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_virtual_tour", arguments: { propertyId: "p1" } });
  assert.ok(!res.isError, textOf(res));
});

test("create_virtual_tour rejects an unknown language", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_virtual_tour", arguments: { propertyId: "p1", language: "nl" } });
  assert.strictEqual(res.isError, true);
});

test("get_virtual_tour returns the share link and embed code", async () => {
  const { client, seen } = recordingClient(["getVirtualTour"]);
  const mcp = await connect(client);
  const res = await mcp.callTool({ name: "pedra_get_virtual_tour", arguments: { tourId: "t1" } });
  assert.ok(!res.isError);
  assert.strictEqual(seen.getVirtualTour[0], "t1");
  assert.match(textOf(res), /virtual-tour\/t1/);
  assert.match(textOf(res), /iframe/);
});

test("get_virtual_tour requires a tourId", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_get_virtual_tour", arguments: {} });
  assert.strictEqual(res.isError, true);
});

test("list_virtual_tours returns tours", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_list_virtual_tours", arguments: {} });
  assert.ok(!res.isError);
  assert.match(textOf(res), /"tourId": "t1"/);
});

test("update_virtual_tour forwards sceneNames and links", async () => {
  const { client, seen } = recordingClient(["updateVirtualTour"]);
  const mcp = await connect(client);
  const res = await mcp.callTool({
    name: "pedra_update_virtual_tour",
    arguments: {
      tourId: "t1",
      sceneNames: { s1: "Kitchen" },
      links: [{ fromSceneId: "s1", toSceneId: "s2", yaw: 90 }],
      navigationStyle: "blue",
    },
  });
  assert.ok(!res.isError, textOf(res));
  assert.deepStrictEqual(seen.updateVirtualTour[0].sceneNames, { s1: "Kitchen" });
  assert.strictEqual(seen.updateVirtualTour[0].links[0].yaw, 90);
  assert.match(textOf(res), /Renamed/);
});

test("update_virtual_tour rejects a link without yaw", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_update_virtual_tour",
    arguments: { tourId: "t1", links: [{ fromSceneId: "s1", toSceneId: "s2" }] },
  });
  assert.strictEqual(res.isError, true);
});

test("add_virtual_tour_scenes returns the added scenes", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({
    name: "pedra_add_virtual_tour_scenes",
    arguments: { tourId: "t1", scenes: [{ imageId: "s3" }] },
  });
  assert.ok(!res.isError, textOf(res));
  assert.match(textOf(res), /"sceneId": "s3"/);
});

test("create_upload_link returns the upload URL", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_upload_link", arguments: { name: "Calle Mayor 12" } });
  assert.ok(!res.isError);
  assert.match(textOf(res), /app\.pedra\.ai\/upload\/tok/);
});

test("add_local_panoramas normalizes paths and calls the SDK helper", async () => {
  const { client, seen } = recordingClient(["addLocalPanoramas"]);
  const mcp = await connect(client);
  const res = await mcp.callTool({
    name: "pedra_add_local_panoramas",
    arguments: { propertyId: "p1", paths: ["'/tmp/a b.jpg'", "file:///tmp/c.jpg", "~/d.jpg"] },
  });
  assert.ok(!res.isError, textOf(res));
  assert.strictEqual(seen.addLocalPanoramas[0], "p1");
  assert.deepStrictEqual(seen.addLocalPanoramas[1], ["/tmp/a b.jpg", "/tmp/c.jpg", path.join(os.homedir(), "d.jpg")]);
  assert.match(textOf(res), /"type": "360"/);
});

test("add_local_panoramas requires at least one path", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_add_local_panoramas", arguments: { propertyId: "p1", paths: [] } });
  assert.strictEqual(res.isError, true);
});

test("tour API errors (409 tour_exists) surface as tool errors", async () => {
  const mcp = await connect(
    fakeClient({
      createVirtualTour: async () => {
        throw new PedraApiError("This property already has a virtual tour", 409, { code: "tour_exists", tourId: "t1" });
      },
    }),
  );
  const res = await mcp.callTool({ name: "pedra_create_virtual_tour", arguments: { propertyId: "p1" } });
  assert.strictEqual(res.isError, true);
  assert.match(textOf(res), /409/);
  assert.match(textOf(res), /already has a virtual tour/);
});

test("add_local_panoramas end to end with the real SDK sends base64 360 photos", async () => {
  const { Pedra } = require("@pedra-ai/sdk");
  const file = path.join(os.tmpdir(), `pedra-mcp-pano-${process.pid}.jpg`);
  fs.writeFileSync(file, Buffer.from([0xff, 0xd8, 0xff, 0xe0]));
  const calls = [];
  const fetch = async (url, init) => {
    const body = JSON.parse(init.body);
    calls.push({ url, body });
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ propertyId: "p1", type: "360", added: [{ imageId: "s1", url: "https://img.pedra.ai/s1", aspectRatio: 2 }], failed: [] }),
    };
  };
  const mcp = await connect(new Pedra("k", { fetch }));
  try {
    const res = await mcp.callTool({ name: "pedra_add_local_panoramas", arguments: { propertyId: "p1", paths: [file] } });
    assert.ok(!res.isError, textOf(res));
    assert.strictEqual(calls.length, 1);
    assert.match(calls[0].url, /\/add_images_to_property$/);
    assert.strictEqual(calls[0].body.type, "360");
    assert.match(calls[0].body.imageUrls[0], /^data:image\/jpeg;base64,/);
    assert.match(textOf(res), new RegExp(file.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  } finally {
    fs.rmSync(file, { force: true });
  }
});

// --- upload links: type ------------------------------------------------------

test("create_upload_link forwards type and returns type + maxFiles", async () => {
  let got;
  const mcp = await connect(
    fakeClient({
      createUploadLink: async (a) => {
        got = a;
        return { uploadUrl: "https://app.pedra.ai/upload/tok", propertyId: "p9", type: a.type, maxFiles: 100, raw: {} };
      },
    }),
  );
  const res = await mcp.callTool({ name: "pedra_create_upload_link", arguments: { propertyId: "p9", type: "360" } });
  assert.ok(!res.isError, textOf(res));
  assert.deepStrictEqual(got, { propertyId: "p9", type: "360" });
  const out = JSON.parse(textOf(res));
  assert.strictEqual(out.type, "360");
  assert.strictEqual(out.maxFiles, 100);
  assert.strictEqual(out.raw, undefined);
});

test("create_upload_link rejects an unknown type", async () => {
  const mcp = await connect(fakeClient());
  const res = await mcp.callTool({ name: "pedra_create_upload_link", arguments: { type: "video" } });
  assert.strictEqual(res.isError, true);
});

test("create_upload_link mirrors the remote description (photos too, type param)", async () => {
  const mcp = await connect(fakeClient());
  const { tools } = await mcp.listTools();
  const tool = tools.find((t) => t.name === "pedra_create_upload_link");
  assert.match(tool.description, /Regular photos and 360° photos both work/);
  assert.deepStrictEqual(tool.inputSchema.properties.type.enum, ["any", "360"]);
  const enhance = tools.find((t) => t.name === "pedra_enhance");
  assert.match(enhance.inputSchema.properties.imageUrl.description, /pedra_create_upload_link/);
  assert.doesNotMatch(enhance.inputSchema.properties.imageUrl.description, /imageFile/);
  assert.strictEqual(enhance.inputSchema.properties.imageFile, undefined);
  const add = tools.find((t) => t.name === "pedra_add_images_to_property");
  assert.strictEqual(add.inputSchema.properties.files, undefined);
});

test("upload limit errors show the HTTP status and code", async () => {
  const mcp = await connect(
    fakeClient({
      addImagesToProperty: async () => {
        throw new PedraApiError("Daily upload limit reached", 429, { error: "Daily upload limit reached", code: "upload_limit" });
      },
    }),
  );
  const res = await mcp.callTool({ name: "pedra_add_images_to_property", arguments: { propertyId: "p1", imageUrls: ["https://x/1.jpg"] } });
  assert.strictEqual(res.isError, true);
  assert.match(textOf(res), /HTTP 429, upload_limit/);
});

// --- no API key: agent signup --------------------------------------------------

const { NO_API_KEY_MESSAGE } = require("../dist/server.js");

function fakeAccess(statuses, requestAccessImpl) {
  const calls = { request: [], status: [] };
  let i = 0;
  return {
    calls,
    requestAccess: async (params) => {
      calls.request.push(params);
      if (requestAccessImpl) return requestAccessImpl(params);
      return { requestId: "r1", status: "pending", expiresAt: "2026-09-30T12:30:00.000Z", pollAfterSeconds: 5, message: "sent", raw: {} };
    },
    getAccessStatus: async (requestId) => {
      calls.status.push(requestId);
      return { raw: {}, ...statuses[Math.min(i++, statuses.length - 1)] };
    },
  };
}

async function connectKeyless(access, createClient) {
  const server = createServer(null, { access, createClient });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const mcp = new Client({ name: "test-agent", version: "0.0.0" });
  await Promise.all([server.connect(serverTransport), mcp.connect(clientTransport)]);
  return mcp;
}

const APPROVED = {
  status: "approved",
  apiKey: "new-key",
  email: "ana@agency.com",
  newAccount: true,
  plan: "free",
  creditsRemaining: 0,
  appUrl: "https://app.pedra.ai",
  note: "This account has no credits yet.",
};

test("without a key: exposes every tool plus the two access tools", async () => {
  const mcp = await connectKeyless(fakeAccess([]));
  const { tools } = await mcp.listTools();
  assert.deepStrictEqual(
    tools.map((t) => t.name).sort(),
    [...EXPECTED_TOOLS, "pedra_request_access", "pedra_check_access"].sort(),
  );
});

test("with a key: the access tools are not listed", async () => {
  const mcp = await connect(fakeClient());
  const { tools } = await mcp.listTools();
  assert.ok(!tools.some((t) => t.name === "pedra_request_access" || t.name === "pedra_check_access"));
});

test("without a key: other tools return a clear no-key error", async () => {
  const mcp = await connectKeyless(fakeAccess([]));
  const res = await mcp.callTool({ name: "pedra_credits", arguments: {} });
  assert.strictEqual(res.isError, true);
  assert.strictEqual(textOf(res), NO_API_KEY_MESSAGE);
  assert.match(textOf(res), /No API key yet: call pedra_request_access with the user's email/);
  // A local path isn't even read before the key check.
  const res2 = await mcp.callTool({ name: "pedra_enhance", arguments: { imageUrl: "/nope/missing.jpg" } });
  assert.strictEqual(res2.isError, true);
  assert.match(textOf(res2), /No API key yet/);
});

test("request_access sends the email and defaults agentName to the MCP client's name", async () => {
  const access = fakeAccess([]);
  const mcp = await connectKeyless(access);
  const res = await mcp.callTool({ name: "pedra_request_access", arguments: { email: "ana@agency.com" } });
  assert.ok(!res.isError, textOf(res));
  assert.deepStrictEqual(access.calls.request, [{ email: "ana@agency.com", agentName: "test-agent" }]);
  const out = JSON.parse(textOf(res));
  assert.strictEqual(out.requestId, "r1");
  assert.match(out.message, /pedra_check_access/);
});

test("request_access passes an explicit agentName and requires an email", async () => {
  const access = fakeAccess([]);
  const mcp = await connectKeyless(access);
  await mcp.callTool({ name: "pedra_request_access", arguments: { email: "a@b.co", agentName: "Claude Code" } });
  assert.strictEqual(access.calls.request[0].agentName, "Claude Code");
  const res = await mcp.callTool({ name: "pedra_request_access", arguments: {} });
  assert.strictEqual(res.isError, true);
});

test("request_access errors (429 rate_limited) surface as tool errors", async () => {
  const access = fakeAccess([], () => {
    throw new PedraApiError("Too many requests for this email address.", 429, { error: "x", code: "rate_limited" });
  });
  const mcp = await connectKeyless(access);
  const res = await mcp.callTool({ name: "pedra_request_access", arguments: { email: "a@b.co" } });
  assert.strictEqual(res.isError, true);
  assert.match(textOf(res), /HTTP 429, rate_limited/);
});

test("check_access: pending, then approved unlocks every tool for the session", async () => {
  const access = fakeAccess([{ status: "pending", pollAfterSeconds: 5 }, APPROVED]);
  const made = [];
  const mcp = await connectKeyless(access, (key) => {
    made.push(key);
    return fakeClient();
  });

  const pending = await mcp.callTool({ name: "pedra_check_access", arguments: { requestId: "r1" } });
  assert.ok(!pending.isError);
  assert.strictEqual(JSON.parse(textOf(pending)).status, "pending");
  assert.strictEqual((await mcp.callTool({ name: "pedra_credits", arguments: {} })).isError, true);

  const approved = await mcp.callTool({ name: "pedra_check_access", arguments: { requestId: "r1" } });
  assert.ok(!approved.isError, textOf(approved));
  const out = JSON.parse(textOf(approved));
  assert.strictEqual(out.status, "approved");
  assert.strictEqual(out.apiKey, "new-key");
  assert.match(out.message, /PEDRA_API_KEY/);
  assert.match(out.note, /no credits/);
  assert.deepStrictEqual(made, ["new-key"]);
  assert.deepStrictEqual(access.calls.status, ["r1", "r1"]);

  const credits = await mcp.callTool({ name: "pedra_credits", arguments: {} });
  assert.ok(!credits.isError, textOf(credits));
  assert.match(textOf(credits), /42/);
});

test("check_access: approval builds a real SDK client with the new key", async () => {
  // Default createClient is `new Pedra(key)`, which captures global fetch when
  // it's built: stub it first, so nothing reaches the network.
  const prevFetch = globalThis.fetch;
  let body;
  globalThis.fetch = async (url, init) => {
    body = JSON.parse(init.body);
    return { ok: true, status: 200, text: async () => JSON.stringify({ plan: "free", creditsRemaining: 0 }) };
  };
  try {
    const mcp = await connectKeyless(fakeAccess([APPROVED]));
    await mcp.callTool({ name: "pedra_check_access", arguments: { requestId: "r1" } });
    const res = await mcp.callTool({ name: "pedra_credits", arguments: {} });
    assert.ok(!res.isError, textOf(res));
    assert.strictEqual(body.apiKey, "new-key");
  } finally {
    globalThis.fetch = prevFetch;
  }
});

test("check_access: denied and expired don't unlock anything", async () => {
  for (const status of ["denied", "expired"]) {
    const mcp = await connectKeyless(fakeAccess([{ status }]), () => {
      throw new Error("must not build a client");
    });
    const res = await mcp.callTool({ name: "pedra_check_access", arguments: { requestId: "r1" } });
    assert.ok(!res.isError);
    const out = JSON.parse(textOf(res));
    assert.strictEqual(out.status, status);
    assert.strictEqual(out.apiKey, undefined);
    assert.strictEqual((await mcp.callTool({ name: "pedra_credits", arguments: {} })).isError, true);
  }
});

test("the stdio entrypoint starts without PEDRA_API_KEY and lists the access tools", async () => {
  const { StdioClientTransport } = require("@modelcontextprotocol/sdk/client/stdio.js");
  const env = { ...process.env };
  delete env.PEDRA_API_KEY;
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.join(__dirname, "..", "dist", "index.js")],
    env,
    stderr: "pipe",
  });
  const mcp = new Client({ name: "test", version: "0.0.0" });
  await mcp.connect(transport);
  try {
    const { tools } = await mcp.listTools();
    const names = tools.map((t) => t.name);
    assert.ok(names.includes("pedra_request_access"));
    assert.ok(names.includes("pedra_check_access"));
    const res = await mcp.callTool({ name: "pedra_list_properties", arguments: {} });
    assert.strictEqual(res.isError, true);
    assert.match(textOf(res), /No API key yet/);
  } finally {
    await mcp.close();
  }
});
