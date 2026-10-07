import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { extname } from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  Pedra,
  PedraError,
  PedraApiError,
  requestAccess as sdkRequestAccess,
  getAccessStatus as sdkGetAccessStatus,
  type ImageResponse,
} from "@pedra-ai/sdk";

export const SERVER_NAME = "pedra";
export const SERVER_VERSION = "0.6.0";

/** A Pedra-shaped client. Typed structurally so tests can inject a fake. */
export type PedraClient = Pick<
  Pedra,
  | "enhance"
  | "enhanceAndCorrectPerspective"
  | "empty"
  | "furnish"
  | "renovation"
  | "editViaPrompt"
  | "sky"
  | "remove"
  | "blur"
  | "createVideo"
  | "updateVideo"
  | "generateVoiceScript"
  | "generateVoice"
  | "musicLibrary"
  | "listProperties"
  | "listPropertyImages"
  | "createProperty"
  | "addImagesToProperty"
  | "addLocalPanoramas"
  | "createUploadLink"
  | "createVirtualTour"
  | "getVirtualTour"
  | "listVirtualTours"
  | "updateVirtualTour"
  | "addVirtualTourScenes"
  | "credits"
  | "feedback"
>;

/** The agent-signup calls, injectable so tests don't hit the network. */
export type AccessApi = {
  requestAccess: typeof sdkRequestAccess;
  getAccessStatus: typeof sdkGetAccessStatus;
};

export interface ServerOptions {
  /** Signup calls. Defaults to the SDK's `requestAccess` / `getAccessStatus`. */
  access?: AccessApi;
  /** Builds the client once access is approved. Defaults to `new Pedra(apiKey)`. */
  createClient?: (apiKey: string) => PedraClient;
}

/** What every account tool says until there's a key. */
export const NO_API_KEY_MESSAGE =
  "No API key yet: call pedra_request_access with the user's email. Pedra emails them a link to confirm " +
  "(new users create their account there), then pedra_check_access returns the key and every tool works for " +
  "the rest of this session. If they already have a key, set PEDRA_API_KEY in this MCP server's config instead.";

type ToolResult = {
  content: { type: "text"; text: string }[];
  isError?: boolean;
};

/** Wrap an arbitrary value as a text tool result. */
function ok(data: unknown): ToolResult {
  const text =
    typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return { content: [{ type: "text", text }] };
}

/** Turn any thrown error into an `isError` tool result the model can read. */
function fail(err: unknown): ToolResult {
  let text: string;
  if (err instanceof PedraApiError) {
    const meta = [err.status ? `HTTP ${err.status}` : "", err.code ?? ""].filter(Boolean).join(", ");
    text = `Pedra API error${meta ? ` (${meta})` : ""}: ${err.message}`;
  } else if (err instanceof PedraError) {
    text = err.message;
  } else {
    text = err instanceof Error ? err.message : String(err);
  }
  return { content: [{ type: "text", text }], isError: true };
}

/** Image endpoints all return the same normalized shape. */
function imageOut(res: ImageResponse): ToolResult {
  return ok({
    message: res.message,
    url: res.url,
    urls: res.urls,
    ...(res.source ? { source: res.source } : {}),
  });
}

/** Catch errors from every handler so they surface as tool errors, not crashes. */
function guard(
  fn: (args: any) => Promise<ToolResult>,
): (args: any) => Promise<ToolResult> {
  return async (args: any) => {
    try {
      return await fn(args);
    } catch (err) {
      return fail(err);
    }
  };
}

// --- local image inlining ----------------------------------------------------

/**
 * Extension → image MIME type. Pedra accepts a `data:` URI, so a local file a
 * user drags or drops in becomes a base64 data URI we build from one of these.
 */
const MIME_BY_EXT: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".bmp": "image/bmp",
  ".tif": "image/tiff",
  ".tiff": "image/tiff",
  ".heic": "image/heic",
  ".heif": "image/heif",
  ".avif": "image/avif",
};

/** Ceiling on an inlined local file, so a stray path can't build a runaway data URI. */
const MAX_LOCAL_IMAGE_BYTES = 40 * 1024 * 1024;

/**
 * Turn a local path as a terminal or drag-and-drop inserts it into a plain
 * filesystem path: strips wrapping quotes, unescapes "\ ", and expands
 * `file://` URLs and `~`.
 */
function normalizeLocalPath(value: string): string {
  let path = value.trim();
  // Drag-and-drop and shells wrap or escape paths in a few predictable ways.
  if (
    (path.startsWith('"') && path.endsWith('"')) ||
    (path.startsWith("'") && path.endsWith("'"))
  ) {
    path = path.slice(1, -1);
  }
  if (path.startsWith("file://")) {
    path = fileURLToPath(path);
  } else {
    path = path.replace(/\\ /g, " "); // unescape "\ " from dragged paths
    if (path === "~" || path.startsWith("~/")) {
      path = homedir() + path.slice(1);
    }
  }
  return path;
}

/**
 * Resolve one image input into a value the Pedra API accepts. Remote URLs and
 * existing `data:` URIs pass through untouched; anything else is treated as a
 * path to a local file — the form a terminal or drag-and-drop inserts — and
 * read off disk into a base64 `data:` URI. This is what lets a user point a
 * tool at a local image instead of having to host it somewhere first.
 */
function resolveImageInput(value: string): string {
  const raw = value.trim();
  if (/^(https?:|data:)/i.test(raw)) return raw;

  const path = normalizeLocalPath(raw);
  const ext = extname(path).toLowerCase();
  const mime = MIME_BY_EXT[ext];
  if (!mime) {
    throw new PedraError(
      `Unsupported local image type "${ext || "(none)"}" for ${path}. ` +
        `Supported: ${Object.keys(MIME_BY_EXT).join(", ")}. ` +
        `Otherwise pass a public https:// URL or a data: URI.`,
    );
  }

  let bytes: Buffer;
  try {
    bytes = readFileSync(path);
  } catch (err) {
    const why = err instanceof Error ? err.message : String(err);
    throw new PedraError(`Could not read local image at ${path}: ${why}`);
  }
  if (bytes.byteLength > MAX_LOCAL_IMAGE_BYTES) {
    const mb = (bytes.byteLength / 1024 / 1024).toFixed(1);
    throw new PedraError(
      `Local image at ${path} is ${mb} MB, over the ` +
        `${MAX_LOCAL_IMAGE_BYTES / 1024 / 1024} MB inline limit. ` +
        `Resize it or host it at a public URL.`,
    );
  }
  return `data:${mime};base64,${bytes.toString("base64")}`;
}

/**
 * Return a shallow copy of a tool's args with every image-bearing field
 * resolved (see {@link resolveImageInput}). Covers the flat image tools plus
 * the per-frame images in `pedra_create_video`. Intentionally does NOT touch
 * `pedra_feedback`, whose `imageUrl` is an already-generated asset URL.
 */
function withResolvedImages<T extends Record<string, any>>(args: T): T {
  if (!args || typeof args !== "object") return args;
  const out: Record<string, any> = { ...args };
  if (typeof out.imageUrl === "string")
    out.imageUrl = resolveImageInput(out.imageUrl);
  if (typeof out.maskUrl === "string")
    out.maskUrl = resolveImageInput(out.maskUrl);
  if (typeof out.secondImageUrl === "string")
    out.secondImageUrl = resolveImageInput(out.secondImageUrl);
  if (Array.isArray(out.images)) {
    out.images = out.images.map((frame: any) => {
      if (!frame || typeof frame !== "object") return frame;
      const f = { ...frame };
      if (typeof f.imageUrl === "string")
        f.imageUrl = resolveImageInput(f.imageUrl);
      if (typeof f.secondImageUrl === "string")
        f.secondImageUrl = resolveImageInput(f.secondImageUrl);
      return f;
    });
  }
  return out as T;
}

type ToolAnnotations = {
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  openWorldHint?: boolean;
};

type ToolConfig = {
  title: string;
  description: string;
  inputSchema: Record<string, unknown>;
  annotations?: ToolAnnotations;
};

/**
 * Register a tool while erasing `registerTool`'s generic inference. Inferring
 * the args type from a zod `ZodRawShape` across all 12 tools makes `tsc` blow
 * its heap; we don't need the inference (handlers take `any` and validate at
 * runtime), so cast through to keep type-checking bounded and fast.
 */
function register(
  server: McpServer,
  name: string,
  config: ToolConfig,
  handler: (args: any) => Promise<ToolResult>,
): void {
  // Every tool advertises a `title` + behavioral hints (required for the
  // Claude connectors directory). All endpoints hit the external Pedra API and
  // create new assets — none mutate or delete existing data — so the default is
  // non-read-only, non-destructive, open-world; tools override as needed.
  const fullConfig = {
    ...config,
    annotations: {
      title: config.title,
      readOnlyHint: false,
      destructiveHint: false,
      openWorldHint: true,
      ...config.annotations,
    },
  };
  (server.registerTool as any)(name, fullConfig, handler);
}

// --- shared field schemas ----------------------------------------------------

const imageUrl = z
  .string()
  .describe(
    "Source image: a public https:// URL, a data: URI, or an absolute path to a local image file on this computer (the file is read and inlined automatically). If the photo is on the user's device and can't be read from here (e.g. it's on their phone), get a link from pedra_create_upload_link.",
  );
const preserveOriginalFraming = z
  .boolean()
  .describe(
    "Preserve the original framing/aspect ratio/resolution exactly (for verification verticals where the output must legally represent the captured photo). Defaults to false.",
  );

// Shared by every image-editing tool; same wording as Pedra's hosted MCP server.
const editOptions = {
  preserveAspectRatio: z
    .boolean()
    .describe(
      "By default the output comes back at whatever size the AI model produces, which may not match the input's aspect ratio or resolution. Set to true to get the result at the exact width and height of the input image (center-cropped to the original aspect ratio, never stretched). Defaults to false.",
    )
    .optional(),
  propertyId: z
    .string()
    .describe(
      "Optional id of the Pedra property (from pedra_list_properties) this photo belongs to. When set, the result is saved into that property's gallery — visible and editable from the app — instead of only being returned as a URL.",
    )
    .optional(),
  name: z
    .string()
    .max(200)
    .describe(
      "Optional name for the original photo (e.g. its file name), up to 200 characters. Only used with propertyId: if the photo isn't in that property yet, it's saved there under this name in the same call and returned as source.name. A photo already in the property keeps its name. Never shown on the image.",
    )
    .optional(),
};
const SAVE_TO_PROPERTY =
  " Pass `propertyId` to save the result into that property's gallery instead of only returning a URL.";

// Shared video building blocks, reused by pedra_create_video and pedra_update_video.
const videoImage = z.object({
  imageUrl,
  effect: z
    .enum(["zoom-in", "zoom-out", "transition", "static"])
    .describe('Animation for this image. Defaults to "zoom-in".')
    .optional(),
  secondImageUrl: z
    .string()
    .describe('Required when effect is "transition".')
    .optional(),
  subtitle: z.string().optional(),
  title: z.string().optional(),
  watermark: z
    .object({
      enabled: z.boolean().optional(),
      position: z.string().optional(),
      opacity: z.number().optional(),
    })
    .optional(),
  characteristics: z.object({ enabled: z.boolean().optional() }).optional(),
});

const videoMusic = z
  .object({
    enabled: z.boolean().optional(),
    track: z
      .string()
      .describe(
        "Genre key from pedra_music_library (e.g. acoustic, chill, cinematic, electronic, upbeat).",
      )
      .optional(),
  })
  .optional();

const videoVoice = z
  .object({
    enabled: z.boolean().optional(),
    audioId: z
      .string()
      .describe(
        "Id of a voiceover from pedra_generate_voice. Drives the narration and its synced subtitles.",
      )
      .optional(),
    audioUrl: z.string().describe("Legacy alias for audioId.").optional(),
    showSubtitles: z
      .boolean()
      .describe("Burn in word-synced subtitles. Defaults to true.")
      .optional(),
  })
  .optional();

const videoBranding = z
  .object({
    showWatermark: z.boolean().optional(),
    showProfessionalPicture: z.boolean().optional(),
  })
  .optional();

const propertyCharacteristics = z
  .array(z.object({ label: z.string(), value: z.string() }))
  .optional();

// Shared virtual-tour building blocks (same wording as the remote server).
const imageType = z.enum(["photo", "360"]).optional();

const tourLanguage = z
  .enum(["en", "es", "fr", "de", "it", "pt"])
  .describe('Language of the tour page and of AI room names. Defaults to "en".')
  .optional();

/**
 * Agent signup tools, registered only when the server starts without an API
 * key. `onApproved` swaps the session's client in, so the other tools work
 * right away.
 */
function registerAccessTools(
  server: McpServer,
  options: ServerOptions,
  onApproved: (apiKey: string) => void,
): void {
  const access: AccessApi = options.access ?? {
    requestAccess: sdkRequestAccess,
    getAccessStatus: sdkGetAccessStatus,
  };

  register(
    server,
    "pedra_request_access",
    {
      title: "Get a Pedra account",
      description:
        "This Pedra server has no API key yet. Use this when the user wants to use Pedra (photo editing, virtual staging, videos, 360° tours): ask for their email, then call this. Pedra emails them a link to confirm: a new user creates their account there (chooses a password), an existing user clicks Allow. Nothing is created until they click. Tell the user to check their inbox, then call pedra_check_access with the requestId.",
      inputSchema: {
        email: z.string().describe("The user's email address (ask them for it; don't guess)."),
        agentName: z
          .string()
          .describe('Shown to the user in the email, e.g. "Claude Code". Defaults to this MCP client\'s name.')
          .optional(),
      },
    },
    guard(async (a) => {
      const agentName =
        a.agentName || server.server.getClientVersion()?.name || "Pedra MCP server";
      const res = await access.requestAccess({ email: a.email, agentName });
      return ok({
        requestId: res.requestId,
        status: res.status,
        expiresAt: res.expiresAt,
        message:
          `Pedra emailed a confirmation link to ${a.email} (valid 30 minutes). Tell the user to open it and ` +
          "confirm (new users choose a password there). Then call pedra_check_access with this requestId; " +
          "if it's still pending, wait a few seconds and check again.",
      });
    }),
  );

  register(
    server,
    "pedra_check_access",
    {
      title: "Check Pedra account access",
      description:
        'Check whether the user confirmed the access request from pedra_request_access. "pending": they haven\'t clicked yet, check again in a few seconds. "approved": every Pedra tool works from now on in this session; show the user the result\'s message so they can keep their API key. "denied" or "expired": ask before requesting again.',
      inputSchema: {
        requestId: z.string().describe("The requestId from pedra_request_access."),
      },
      annotations: { readOnlyHint: true },
    },
    guard(async (a) => {
      const res = await access.getAccessStatus(a.requestId);
      if (res.status === "approved") {
        onApproved(res.apiKey);
        return ok({
          status: "approved",
          email: res.email,
          newAccount: res.newAccount,
          plan: res.plan,
          creditsRemaining: res.creditsRemaining,
          appUrl: res.appUrl,
          ...(res.note ? { note: res.note } : {}),
          apiKey: res.apiKey,
          message:
            "Access approved: every Pedra tool works now, for the rest of this session. The key is only kept in " +
            "memory, so tell the user how to keep it: add PEDRA_API_KEY with this apiKey to the `env` block of " +
            "this server's entry in their MCP client config (Claude Desktop extension: Settings > Extensions > " +
            "Pedra > API key; Claude Code: `claude mcp add pedra -e PEDRA_API_KEY=<apiKey> -- npx -y @pedra-ai/mcp`). " +
            "The key can also be found later in Settings at https://app.pedra.ai. Treat it like a password.",
        });
      }
      const message = {
        pending:
          "The user hasn't confirmed yet. Ask them to open the link in the email from Pedra, then check again in a few seconds.",
        denied: "The user declined access. Don't request it again unless they ask you to.",
        expired:
          "The request expired (links last 30 minutes). If the user still wants to use Pedra, call pedra_request_access again.",
      }[res.status];
      return ok({ status: res.status, message });
    }),
  );
}

/**
 * Build a Pedra MCP server with one tool per API endpoint. Each tool is a
 * single blocking call that returns the final asset URL(s); the API's 4xx
 * errors (insufficient credits, bad image, …) come back as tool errors.
 *
 * Without a client (no PEDRA_API_KEY), the server still starts: it adds
 * `pedra_request_access` + `pedra_check_access` (agent signup), and every
 * other tool answers with {@link NO_API_KEY_MESSAGE} until access is approved.
 * The approved key then lives in memory for the session; it's never written
 * to disk.
 */
export function createServer(
  client?: PedraClient | null,
  options: ServerOptions = {},
): McpServer {
  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  let current: PedraClient | null = client ?? null;
  const api = (): PedraClient => {
    if (!current) throw new PedraError(NO_API_KEY_MESSAGE);
    return current;
  };

  if (!client) registerAccessTools(server, options, (apiKey) => {
    current = (options.createClient ?? ((key: string) => new Pedra(key)))(apiKey);
  });

  register(
    server,
    "pedra_enhance",
    {
      title: "Enhance image",
      description:
        "Enhance a real-estate photo: improve lighting, color, and sharpness. Returns the enhanced image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        preserveOriginalFraming: preserveOriginalFraming.optional(),
      },
    },
    guard(async (a) => imageOut(await api().enhance(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_enhance_and_correct_perspective",
    {
      title: "Enhance + correct perspective",
      description:
        "Enhance a photo and correct vertical/horizontal perspective (straighten walls and lines). Returns the corrected image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        preserveOriginalFraming: preserveOriginalFraming.optional(),
      },
    },
    guard(async (a) =>
      imageOut(await api().enhanceAndCorrectPerspective(withResolvedImages(a))),
    ),
  );

  register(
    server,
    "pedra_empty_room",
    {
      title: "Empty room",
      description:
        "Remove all furniture and objects from a room, leaving an empty space. Returns the emptied image URL." + SAVE_TO_PROPERTY,
      inputSchema: { imageUrl, ...editOptions },
    },
    guard(async (a) => imageOut(await api().empty(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_furnish",
    {
      title: "Furnish / virtually stage",
      description:
        "Virtually stage (furnish) a room with AI-generated furniture. Returns the staged image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        roomType: z
          .string()
          .describe('e.g. "Living room", "Bedroom", "Kitchen". Auto-detected if omitted.')
          .optional(),
        style: z
          .string()
          .describe('e.g. "Minimalist", "Scandinavian", "Modern".')
          .optional(),
      },
    },
    guard(async (a) => imageOut(await api().furnish(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_renovation",
    {
      title: "Renovate space",
      description:
        "Renovate a space (walls, floors, finishes), optionally furnished. Returns the renovated image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        style: z.string().describe("Renovation style.").optional(),
        furnish: z
          .union([
            z.boolean(),
            z.enum(["With furniture", "Empty", "Auto"]),
          ])
          .describe(
            "Whether the renovated room should be furnished (true → with furniture, false → empty).",
          )
          .optional(),
        roomType: z.string().describe("Room type. Auto-detected if omitted.").optional(),
      },
    },
    guard(async (a) => imageOut(await api().renovation(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_edit_via_prompt",
    {
      title: "Edit via prompt",
      description:
        "Edit an image from a natural-language instruction (e.g. \"paint the walls sage green\"). Returns the edited image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        prompt: z
          .string()
          .describe("Natural-language description of the edit to apply."),
      },
    },
    guard(async (a) => imageOut(await api().editViaPrompt(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_sky_blue",
    {
      title: "Replace sky",
      description:
        "Replace a dull or overcast sky with a clear blue one. Returns the image URL with the new sky." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        skyStyle: z.string().describe("Optional named sky style.").optional(),
      },
    },
    guard(async (a) => imageOut(await api().sky(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_remove_object",
    {
      title: "Remove object",
      description:
        "Remove an object from an image using a mask. Returns the cleaned image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        maskUrl: z
          .string()
          .describe(
            "Mask image marking the region to remove: a public https:// URL, a data: URI, or a local file path.",
          ),
      },
    },
    guard(async (a) => imageOut(await api().remove(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_blur",
    {
      title: "Blur objects",
      description:
        "Blur objects in an image (e.g. faces, license plates) for privacy. Returns the blurred image URL." + SAVE_TO_PROPERTY,
      inputSchema: {
        imageUrl,
        ...editOptions,
        objectsToBlur: z
          .array(z.string())
          .describe('Labels/regions to blur, e.g. ["faces", "license plates"].'),
      },
    },
    guard(async (a) => imageOut(await api().blur(withResolvedImages(a)))),
  );

  register(
    server,
    "pedra_create_video",
    {
      title: "Create property video",
      description:
        "Create a property video from a list of images. Blocks server-side until the video is rendered (up to ~10 min) and returns the finished video URL inline.",
      inputSchema: {
        images: z
          .array(videoImage)
          .min(1)
          .describe("Ordered list of images that make up the video."),
        music: videoMusic,
        voice: videoVoice,
        branding: videoBranding,
        endingTitle: z.string().optional(),
        endingSubtitle: z.string().optional(),
        isVertical: z
          .boolean()
          .describe("Force a vertical (9:16) video.")
          .optional(),
        propertyCharacteristics,
      },
    },
    guard(async (a) => {
      const res = await api().createVideo(withResolvedImages(a));
      return ok({
        message: res.message,
        videoId: res.videoId,
        videoUrl: res.videoUrl,
      });
    }),
  );

  register(
    server,
    "pedra_update_video",
    {
      title: "Edit existing video",
      description:
        "Edit an existing video (by videoId) without re-rendering unchanged clips — only new/changed photos re-animate and cost credits; reordering, music, voice, branding and text re-stitch for free. Omit `images` to change only audio/text/branding while keeping the current timeline. Omit `music`/`voice`/`branding`/ending text to leave them unchanged. Blocks until rendered and returns the new video URL.",
      inputSchema: {
        videoId: z
          .string()
          .describe("Id of the video to edit (from pedra_create_video)."),
        images: z
          .array(videoImage)
          .describe(
            "Full ordered image list to rebuild the timeline; matching photo+effect clips are reused. Omit to edit only audio/text and keep the current timeline.",
          )
          .optional(),
        music: videoMusic,
        voice: videoVoice,
        branding: videoBranding,
        endingTitle: z.string().optional(),
        endingSubtitle: z.string().optional(),
        isVertical: z
          .boolean()
          .describe("Force a vertical (9:16) video (only when images are sent).")
          .optional(),
        propertyCharacteristics,
      },
    },
    guard(async (a) => {
      const res = await api().updateVideo(withResolvedImages(a));
      return ok({
        message: res.message,
        videoId: res.videoId,
        videoUrl: res.videoUrl,
      });
    }),
  );

  register(
    server,
    "pedra_generate_voice_script",
    {
      title: "Generate voiceover script",
      description:
        "Write a short voiceover script from property photos (and optional facts). GPT-4o vision reads the images so the script reflects what's actually shown. Returns the script text — pass it to pedra_generate_voice.",
      inputSchema: {
        images: z
          .array(z.union([imageUrl, z.object({ imageUrl })]))
          .describe("Photos to base the script on (URLs or { imageUrl }).")
          .optional(),
        propertyCharacteristics,
        language: z
          .string()
          .describe('Script language, e.g. "English", "Español". Defaults to English.')
          .optional(),
      },
    },
    guard(async (a) => {
      const res = await api().generateVoiceScript(a);
      return ok({ message: res.message, script: res.script });
    }),
  );

  register(
    server,
    "pedra_generate_voice",
    {
      title: "Generate voiceover audio",
      description:
        "Render a voiceover from a script via text-to-speech. Returns an audioId — pass it to pedra_create_video / pedra_update_video as voice.audioId to attach the narration (with synced subtitles).",
      inputSchema: {
        text: z.string().describe("The script to narrate (max 1000 characters)."),
        language: z
          .string()
          .describe('Voice language, e.g. "English", "Español". Defaults to English.')
          .optional(),
        voiceId: z
          .string()
          .describe(
            "Which voice narrates. Call pedra_music_library for the voices offered per language — a voice is only valid for the language it is listed under. Defaults to that language's first voice.",
          )
          .optional(),
      },
    },
    guard(async (a) => {
      const res = await api().generateVoice(a);
      return ok({
        message: res.message,
        audioId: res.audioId,
        audioUrl: res.audioUrl,
        alignmentUrl: res.alignmentUrl,
        duration: res.duration,
      });
    }),
  );

  register(
    server,
    "pedra_music_library",
    {
      title: "List music tracks",
      description:
        "List the background-music catalog: valid `music.track` values (genre keys), plus the voice languages and the narration voices offered for each of them. Read-only.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    guard(async () => {
      const res = await api().musicLibrary();
      return ok({
        tracks: res.tracks,
        variantsPerTrack: res.variantsPerTrack,
        defaultTrack: res.defaultTrack,
        voiceLanguages: res.voiceLanguages,
        voicesByLanguage: res.voicesByLanguage ?? [],
      });
    }),
  );

  register(
    server,
    "pedra_list_properties",
    {
      title: "List properties",
      description:
        "List the user's Pedra properties (id, name, photo count, and an appUrl to open each in Pedra). Use this to find photos already in the account — e.g. to build a video from a listing's photos.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    guard(async () => {
      const res = await api().listProperties();
      return ok({ properties: res.properties });
    }),
  );

  register(
    server,
    "pedra_list_property_images",
    {
      title: "List property photos",
      description:
        'List the photos in a Pedra property as img.pedra.ai URLs, ready to pass straight to pedra_create_video or the image-editing tools. Get the propertyId from pedra_list_properties. Pass type "360" to list its 360° photos instead (their imageIds are the scenes of a virtual tour).',
      inputSchema: {
        propertyId: z
          .string()
          .describe("The property's id (from pedra_list_properties)."),
        type: imageType.describe(
          'Which images to list: regular photos ("photo", the default) or 360° photos ("360").',
        ),
      },
      annotations: { readOnlyHint: true },
    },
    guard(async (a) => {
      const res = await api().listPropertyImages(a);
      return ok({ propertyId: res.propertyId, name: res.name, images: res.images });
    }),
  );

  register(
    server,
    "pedra_create_property",
    {
      title: "Create property",
      description:
        "Create a new Pedra property. Returns its propertyId and an appUrl. To add photos that are on the user's device, pedra_create_upload_link is simpler (no login); or give the user the appUrl to open the property in Pedra and drop their photos in, then use pedra_list_property_images.",
      inputSchema: {
        name: z
          .string()
          .describe("Property name, e.g. the listing address.")
          .optional(),
      },
    },
    guard(async (a) => {
      const res = await api().createProperty(a);
      return ok({ message: res.message, propertyId: res.propertyId, appUrl: res.appUrl });
    }),
  );

  register(
    server,
    "pedra_add_images_to_property",
    {
      title: "Add photos to property",
      description:
        'Add photos to a property by URL (the server fetches each one, so any public https image URL or small data: URI works). Returns the stored img.pedra.ai URLs to use with the editing, video and tour tools. For photos on the user\'s device, use pedra_create_upload_link instead. Pass type "360" for 360° photos (checked to be 2:1 equirectangular), which can then become a virtual tour. (With this local server, 360° photo files on this computer can go through pedra_add_local_panoramas instead.)',
      inputSchema: {
        propertyId: z
          .string()
          .describe("Target property id (from pedra_list_properties or pedra_create_property)."),
        imageUrls: z
          .array(z.string())
          .describe(
            'Image URLs to fetch and add to the property: up to 20 photos, or up to 10 when type is "360".',
          ),
        names: z
          .array(z.string())
          .describe(
            "Optional names, one per image in the same order as imageUrls (e.g. the original file names), up to 200 characters each. Returned by pedra_list_property_images and as source.name when the photo is edited. Never shown on the image.",
          )
          .optional(),
        type: imageType.describe(
          'What the images are: regular photos ("photo", the default) or 360° photos ("360").',
        ),
      },
    },
    guard(async (a) => {
      const res = await api().addImagesToProperty(a);
      return ok({
        message: res.message,
        propertyId: res.propertyId,
        type: res.type,
        added: res.added,
        failed: res.failed,
        appUrl: res.appUrl,
      });
    }),
  );

  register(
    server,
    "pedra_add_local_panoramas",
    {
      title: "Add local 360° photos to property",
      description:
        "LOCAL-ONLY TOOL (this Pedra MCP server runs on the user's own computer, so it can read files from its disk). Upload 360° photo files (2:1 equirectangular JPEG, PNG or WebP) from absolute local paths into a property, in the order given — that order becomes the walking order when you then call pedra_create_virtual_tour with just the propertyId. Files are sent in batches (10 per call, under the 50 MB request limit); a file over ~33 MB can't be sent this way — use pedra_create_upload_link for those. Prefer this over pedra_create_upload_link whenever the 360° photos are files on this computer. Returns the added photos (imageIds are scene ids) and any that failed, each with its path.",
      inputSchema: {
        propertyId: z
          .string()
          .describe("Target property id (from pedra_list_properties or pedra_create_property)."),
        paths: z
          .array(z.string())
          .min(1)
          .describe(
            "Absolute paths to 360° photo files on this computer, in walking order (file:// URLs and ~ are accepted).",
          ),
      },
      annotations: { openWorldHint: false },
    },
    guard(async (a) => {
      const res = await api().addLocalPanoramas(
        a.propertyId,
        (a.paths as string[]).map(normalizeLocalPath),
      );
      return ok({
        message: res.message,
        propertyId: res.propertyId,
        type: res.type,
        added: res.added,
        failed: res.failed,
        appUrl: res.appUrl,
      });
    }),
  );

  register(
    server,
    "pedra_create_upload_link",
    {
      title: "Create photo upload link",
      description:
        'Get a link where the user (or their photographer) uploads photos from their phone or computer into a property. No login, valid 24 hours. Use this whenever the photos are files on the user\'s device that weren\'t attached to the chat: for editing, videos or virtual tours. Regular photos and 360° photos both work (360° photos are recognised automatically); pass type "360" for a virtual tour so anything else is refused. Creates the property if no propertyId is given. Give the user the uploadUrl, wait until they say they\'re done, then use pedra_list_property_images (type "360" for 360° photos), or pedra_create_virtual_tour with the propertyId. (With this local server, files on this computer can also be passed directly: a local path as imageUrl, or pedra_add_local_panoramas for 360° photos.)',
      inputSchema: {
        propertyId: z
          .string()
          .describe("Property to upload into (from pedra_list_properties). Omit to create a new one.")
          .optional(),
        name: z
          .string()
          .describe("Name for the new property, e.g. the listing address. Ignored when propertyId is given.")
          .optional(),
        type: z
          .enum(["any", "360"])
          .describe('"any" (default) takes photos and 360° photos; "360" only takes 360° photos.')
          .optional(),
        language: tourLanguage,
      },
      annotations: { openWorldHint: false },
    },
    guard(async (a) => {
      const res = await api().createUploadLink(a);
      const { raw, ...rest } = res;
      return ok(rest);
    }),
  );

  register(
    server,
    "pedra_create_virtual_tour",
    {
      title: "Create virtual tour",
      description:
        'Build a hosted 360° virtual tour: the rooms are named and linked with navigation points by AI, and you get a shareable link and embed code. Pass the 360° photos as scenes (URLs, or imageIds of 360° photos already in the property) in the order someone would walk through the home, or just a propertyId to use all its 360° photos. Linking: "sequential" (default) links each room to the next and costs max(3, ceil(rooms/3)) credits; "smart" lets AI work out which rooms connect (slower, 5-160 credits by room count); "none" is free. Returns a tourId immediately — the build takes about 10 seconds per room, so poll pedra_get_virtual_tour until status is "ready". One tour per property.',
      inputSchema: {
        scenes: z
          .array(
            z.object({
              imageUrl: z
                .string()
                .describe("A 360° photo (2:1 equirectangular): public https URL or data: URI.")
                .optional(),
              imageId: z
                .string()
                .describe('Id of a 360° photo already in the property (from pedra_list_property_images with type "360").')
                .optional(),
              name: z
                .string()
                .describe('Room name shown in the tour, e.g. "Kitchen". Omit and AI names the room.')
                .optional(),
            }),
          )
          .describe("The rooms in walking order. Omit to use every 360° photo in propertyId.")
          .optional(),
        propertyId: z
          .string()
          .describe("Property the tour belongs to. Omit to create a new property.")
          .optional(),
        name: z.string().describe("Tour title, e.g. the listing address.").optional(),
        linking: z
          .enum(["sequential", "smart", "none"])
          .describe('How rooms get connected. Defaults to "sequential".')
          .optional(),
        language: tourLanguage,
      },
      annotations: { openWorldHint: true },
    },
    guard(async (a) => {
      const { raw, ...rest } = await api().createVirtualTour(a);
      return ok(rest);
    }),
  );

  register(
    server,
    "pedra_get_virtual_tour",
    {
      title: "Check virtual tour",
      description:
        'Get a virtual tour: status ("processing", "ready" or "failed", with the reason), the shareable tourUrl, an embedCode iframe for a website, and its scenes and navigation links. Poll this after pedra_create_virtual_tour or pedra_add_virtual_tour_scenes. Read-only.',
      inputSchema: {
        tourId: z
          .string()
          .describe("Id from pedra_create_virtual_tour or pedra_list_virtual_tours."),
      },
      annotations: { readOnlyHint: true },
    },
    guard(async (a) => {
      const { raw, ...rest } = await api().getVirtualTour(a.tourId);
      return ok(rest);
    }),
  );

  register(
    server,
    "pedra_list_virtual_tours",
    {
      title: "List virtual tours",
      description:
        "List the account's virtual tours (newest first) with status, share link and room count. Optionally only one property's. Read-only.",
      inputSchema: {
        propertyId: z.string().describe("Only this property's tour.").optional(),
      },
      annotations: { readOnlyHint: true },
    },
    guard(async (a) => {
      const res = await api().listVirtualTours(a);
      return ok({ tours: res.tours });
    }),
  );

  register(
    server,
    "pedra_update_virtual_tour",
    {
      title: "Edit virtual tour",
      description:
        "Change a finished virtual tour in place: rename it or its rooms, reorder rooms (the first one is where the tour opens), remove rooms, replace its navigation links, or change how the navigation points look. Free and instant. The tour's public link shows the change right away. Get sceneIds from pedra_get_virtual_tour.",
      inputSchema: {
        tourId: z.string().describe("The tour to change."),
        name: z.string().describe("New tour title.").optional(),
        sceneNames: z
          .record(z.string())
          .describe('New room names, as { sceneId: "Kitchen" }.')
          .optional(),
        sceneOrder: z
          .array(z.string())
          .describe("Every sceneId of the tour in the new order. The first one opens the tour.")
          .optional(),
        removeScenes: z
          .array(z.string())
          .describe("sceneIds to take out of the tour (the photos stay in the property). Their links go too.")
          .optional(),
        links: z
          .array(
            z.object({
              fromSceneId: z.string(),
              toSceneId: z.string(),
              yaw: z
                .number()
                .describe("Horizontal angle of the navigation point in the from-scene, -180 to 180 (0 = centre of the photo)."),
              pitch: z
                .number()
                .describe("Vertical angle, -90 to 90 (0 = horizon, the default).")
                .optional(),
            }),
          )
          .describe("Replaces ALL navigation links. Each is one direction; add the return link separately.")
          .optional(),
        navigationStyle: z
          .enum(["white", "blue"])
          .describe("Look of the navigation points.")
          .optional(),
        navigationSize: z
          .enum(["small", "medium", "large"])
          .describe("Size of the navigation points.")
          .optional(),
        showLabels: z
          .boolean()
          .describe("Always show room names next to the navigation points.")
          .optional(),
        language: tourLanguage,
      },
      annotations: { destructiveHint: true },
    },
    guard(async (a) => {
      const { raw, ...rest } = await api().updateVirtualTour(a);
      return ok(rest);
    }),
  );

  register(
    server,
    "pedra_add_virtual_tour_scenes",
    {
      title: "Add rooms to virtual tour",
      description:
        'Add rooms to the end of an existing virtual tour. With "sequential" linking (default) only the new stretch is linked: the last existing room to the first new one, then each new room to the next. That costs max(3, ceil(new rooms/3)) credits; "none" is free. The tour stays live while this runs; poll pedra_get_virtual_tour until status is "ready".',
      inputSchema: {
        tourId: z.string().describe("The tour to extend."),
        scenes: z
          .array(
            z.object({
              imageUrl: z
                .string()
                .describe("A 360° photo: public https URL or data: URI.")
                .optional(),
              imageId: z
                .string()
                .describe("Id of a 360° photo already in the tour's property.")
                .optional(),
              name: z
                .string()
                .describe("Room name. Omit and AI names the room.")
                .optional(),
            }),
          )
          .describe("The new rooms, in walking order."),
        linking: z
          .enum(["sequential", "none"])
          .describe('Defaults to "sequential".')
          .optional(),
      },
      annotations: { openWorldHint: true },
    },
    guard(async (a) => {
      const { raw, ...rest } = await api().addVirtualTourScenes(a);
      return ok(rest);
    }),
  );

  register(
    server,
    "pedra_credits",
    {
      title: "Get credits",
      description:
        "Read the account's plan and remaining credits. Never deducts credits.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    guard(async () => {
      const res = await api().credits();
      return ok({ plan: res.plan, creditsRemaining: res.creditsRemaining });
    }),
  );

  register(
    server,
    "pedra_feedback",
    {
      title: "Submit feedback",
      description:
        "Submit thumbs up/down feedback on a generated image, with an optional credit-back on a thumbs-down (subject to the API's eligibility rules).",
      inputSchema: {
        imageUrl: z
          .string()
          .describe("The generated image URL to vote on (id is parsed from it).")
          .optional(),
        imageId: z
          .string()
          .describe("Explicit image id. One of imageUrl/imageId is required.")
          .optional(),
        vote: z
          .enum(["up", "down", "positive", "negative", ""])
          .describe("Thumbs up/down. An empty string clears a previous vote.")
          .optional(),
        comment: z.string().optional(),
        creditBack: z
          .boolean()
          .describe("Request a credit refund (only honored on a thumbs-down).")
          .optional(),
      },
    },
    guard(async (a) => {
      const res = await api().feedback(a);
      const { raw, ...rest } = res;
      return ok(rest);
    }),
  );

  return server;
}
