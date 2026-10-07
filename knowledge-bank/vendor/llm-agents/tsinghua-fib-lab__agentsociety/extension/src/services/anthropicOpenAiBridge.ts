type JsonObject = Record<string, unknown>;

const BILLING_HEADER_PREFIX = 'x-anthropic-billing-header:';

function isObject(value: unknown): value is JsonObject {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function stripLeadingAnthropicBillingHeader(text: string): string {
  if (!text.startsWith(BILLING_HEADER_PREFIX)) {
    return text;
  }
  const lineEnd = text.search(/\r?\n/);
  if (lineEnd < 0) {
    return '';
  }
  return text.slice(lineEnd).replace(/^\r?\n\r?\n?/, '');
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {});
  } catch {
    return '{}';
  }
}

function textFromAnthropicContent(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }
  if (!Array.isArray(content)) {
    return '';
  }
  return content
    .filter((block): block is JsonObject => isObject(block))
    .filter((block) => block.type === 'text')
    .map((block) => (typeof block.text === 'string' ? block.text : ''))
    .join('\n');
}

function anthropicContentToOpenAiContent(content: unknown): unknown {
  if (typeof content === 'string') {
    return content;
  }
  if (!Array.isArray(content)) {
    return '';
  }
  const parts: JsonObject[] = [];
  for (const raw of content) {
    if (!isObject(raw)) {
      continue;
    }
    if (raw.type === 'text') {
      parts.push({ type: 'text', text: typeof raw.text === 'string' ? raw.text : '' });
    } else if (raw.type === 'image' && isObject(raw.source)) {
      const source = raw.source;
      const mediaType = typeof source.media_type === 'string' ? source.media_type : 'image/png';
      if (typeof source.data === 'string') {
        parts.push({ type: 'image_url', image_url: { url: `data:${mediaType};base64,${source.data}` } });
      } else if (typeof source.url === 'string') {
        parts.push({ type: 'image_url', image_url: { url: source.url } });
      }
    }
  }
  if (parts.length === 1 && parts[0].type === 'text') {
    return parts[0].text ?? '';
  }
  return parts;
}

function mapToolChoiceToOpenAi(toolChoice: unknown): unknown {
  if (typeof toolChoice === 'string') {
    return toolChoice === 'any' ? 'required' : toolChoice;
  }
  if (!isObject(toolChoice)) {
    return undefined;
  }
  const type = toolChoice.type;
  if (type === 'any') {
    return 'required';
  }
  if (type === 'auto' || type === 'none') {
    return type;
  }
  if (type === 'tool' && typeof toolChoice.name === 'string') {
    return { type: 'function', function: { name: toolChoice.name } };
  }
  return undefined;
}

function supportsReasoningEffort(model: string): boolean {
  const lower = model.toLowerCase();
  return /^o\d/.test(lower) || /^gpt-[5-9]/.test(lower);
}

function resolveReasoningEffort(body: JsonObject): string | undefined {
  const outputConfig = isObject(body.output_config) ? body.output_config : {};
  if (typeof outputConfig.effort === 'string') {
    const effort = outputConfig.effort.trim().toLowerCase();
    if (effort === 'max' || effort === 'xhigh') {
      return 'xhigh';
    }
    if (effort === 'low' || effort === 'medium' || effort === 'high') {
      return effort;
    }
    return undefined;
  }
  const thinking = isObject(body.thinking) ? body.thinking : {};
  if (thinking.type === 'adaptive') {
    return 'xhigh';
  }
  if (thinking.type === 'enabled') {
    const budget = typeof thinking.budget_tokens === 'number' ? thinking.budget_tokens : undefined;
    if (budget === undefined) {
      return 'high';
    }
    if (budget < 4000) {
      return 'low';
    }
    if (budget < 16000) {
      return 'medium';
    }
    return 'high';
  }
  return undefined;
}

/**
 * Translate an Anthropic Messages API request to an OpenAI Chat Completions request.
 *
 * Converts:
 * - `system` (string/array) → `messages[0].role: "system"`
 * - `messages[]` → `messages[]` (tool_result → tool role, tool_use → tool_calls)
 * - `tools[]` → `tools[].function` format
 * - `tool_choice` → OpenAI-compatible format
 * - `thinking` → `reasoning_effort` (for o1/GPT-5+ models)
 * - `max_tokens` → `max_tokens` or `max_completion_tokens` (for o1 series)
 * - Strips `x-anthropic-billing-header` prefix from system prompts
 *
 * @see OpenAiChatToAnthropicStreamTranslator for the reverse (response → Anthropic) translation
 */
export function translateAnthropicMessagesToOpenAiChat(
  body: JsonObject,
  model: string
): JsonObject {
  const messages: JsonObject[] = [];
  const system = body.system;
  if (typeof system === 'string') {
    const text = stripLeadingAnthropicBillingHeader(system);
    if (text) {
      messages.push({ role: 'system', content: text });
    }
  } else if (Array.isArray(system)) {
    const text = system
      .filter((part): part is JsonObject => isObject(part))
      .map((part) => (typeof part.text === 'string' ? stripLeadingAnthropicBillingHeader(part.text) : ''))
      .filter(Boolean)
      .join('\n\n');
    if (text) {
      messages.push({ role: 'system', content: text });
    }
  }

  for (const rawMessage of Array.isArray(body.messages) ? body.messages : []) {
    if (!isObject(rawMessage)) {
      continue;
    }
    const role = rawMessage.role === 'assistant' ? 'assistant' : 'user';
    const content = rawMessage.content;
    if (Array.isArray(content)) {
      const toolResults = content.filter((block): block is JsonObject => isObject(block) && block.type === 'tool_result');
      const toolUses = content.filter((block): block is JsonObject => isObject(block) && block.type === 'tool_use');
      const textContent = textFromAnthropicContent(content);
      if (role === 'assistant') {
        messages.push({
          role,
          content: textContent || null,
          ...(toolUses.length
            ? {
                tool_calls: toolUses.map((block, index) => ({
                  id: typeof block.id === 'string' ? block.id : `toolu_${index}`,
                  type: 'function',
                  function: {
                    name: typeof block.name === 'string' ? block.name : 'tool',
                    arguments: safeJson(block.input),
                  },
                })),
              }
            : {}),
        });
      } else {
        const regularContent = anthropicContentToOpenAiContent(
          content.filter((block) => !(isObject(block) && block.type === 'tool_result'))
        );
        if ((typeof regularContent === 'string' && regularContent) || Array.isArray(regularContent)) {
          messages.push({ role: 'user', content: regularContent });
        }
        for (const block of toolResults) {
          messages.push({
            role: 'tool',
            tool_call_id: typeof block.tool_use_id === 'string' ? block.tool_use_id : '',
            content: textFromAnthropicContent(block.content) || (typeof block.content === 'string' ? block.content : safeJson(block.content)),
          });
        }
      }
    } else {
      messages.push({ role, content: anthropicContentToOpenAiContent(content) });
    }
  }

  const out: JsonObject = {
    model,
    messages,
    stream: body.stream !== false,
  };
  if (body.max_tokens !== undefined) {
    if (/^o\d/i.test(model)) {
      out.max_completion_tokens = body.max_tokens;
    } else {
      out.max_tokens = body.max_tokens;
    }
  }
  for (const key of ['temperature', 'top_p', 'metadata']) {
    if (body[key] !== undefined) {
      out[key] = body[key];
    }
  }
  if (body.stop_sequences !== undefined) {
    out.stop = body.stop_sequences;
  }
  const effort = supportsReasoningEffort(model) ? resolveReasoningEffort(body) : undefined;
  if (effort) {
    out.reasoning_effort = effort;
  }
  if (Array.isArray(body.tools)) {
    out.tools = body.tools
      .filter((tool): tool is JsonObject => isObject(tool) && tool.type !== 'BatchTool')
      .map((tool) => ({
        type: 'function',
        function: {
          name: typeof tool.name === 'string' ? tool.name : '',
          description: typeof tool.description === 'string' ? tool.description : undefined,
          parameters: isObject(tool.input_schema) ? tool.input_schema : {},
        },
      }));
  }
  const toolChoice = mapToolChoiceToOpenAi(body.tool_choice);
  if (toolChoice) {
    out.tool_choice = toolChoice;
  }
  if (out.stream) {
    out.stream_options = { include_usage: true };
  }
  return out;
}

function anthropicUsageFromOpenAi(usage: unknown): JsonObject {
  if (!isObject(usage)) {
    return { input_tokens: 0, output_tokens: 0 };
  }
  const prompt = typeof usage.prompt_tokens === 'number' ? usage.prompt_tokens : 0;
  const completion = typeof usage.completion_tokens === 'number' ? usage.completion_tokens : 0;
  const promptDetails = isObject(usage.prompt_tokens_details) ? usage.prompt_tokens_details : {};
  const cached = typeof promptDetails.cached_tokens === 'number' ? promptDetails.cached_tokens : 0;
  return {
    input_tokens: Math.max(prompt - cached, 0),
    output_tokens: completion,
    ...(cached > 0 ? { cache_read_input_tokens: cached } : {}),
  };
}

function mapFinishReason(reason: unknown, hasToolUse: boolean): string {
  if (hasToolUse) {
    return 'tool_use';
  }
  if (reason === 'length') {
    return 'max_tokens';
  }
  if (reason === 'stop') {
    return 'end_turn';
  }
  return 'end_turn';
}

export function translateOpenAiChatToAnthropicMessage(body: JsonObject, fallbackModel: string): JsonObject {
  const choice = Array.isArray(body.choices) && isObject(body.choices[0]) ? body.choices[0] : {};
  const message = isObject(choice.message) ? choice.message : {};
  const content: JsonObject[] = [];
  // Thinking / reasoning content (non-streaming: full text in reasoning_content)
  const reasoningContent = typeof message.reasoning_content === 'string' ? message.reasoning_content : '';
  if (reasoningContent) {
    content.push({ type: 'thinking', thinking: reasoningContent });
  }
  // Also check thinking_blocks (provider-specific field)
  const thinkingBlocks = Array.isArray(message.thinking_blocks) ? message.thinking_blocks.filter(isObject) : [];
  if (!reasoningContent && thinkingBlocks.length > 0) {
    const combinedThinking = thinkingBlocks
      .map((block) => typeof block.thinking === 'string' ? block.thinking : '')
      .join('');
    if (combinedThinking) {
      content.push({ type: 'thinking', thinking: combinedThinking });
    }
  }
  if (typeof message.content === 'string' && message.content) {
    content.push({ type: 'text', text: message.content });
  }
  const toolCalls = Array.isArray(message.tool_calls) ? message.tool_calls.filter(isObject) : [];
  for (const call of toolCalls) {
    const fn = isObject(call.function) ? call.function : {};
    let input: unknown = {};
    if (typeof fn.arguments === 'string' && fn.arguments) {
      try {
        input = JSON.parse(fn.arguments);
      } catch {
        input = {};
      }
    }
    content.push({
      type: 'tool_use',
      id: typeof call.id === 'string' ? call.id : '',
      name: typeof fn.name === 'string' ? fn.name : 'tool',
      input,
    });
  }
  return {
    id: typeof body.id === 'string' ? body.id : `msg_${Date.now()}`,
    type: 'message',
    role: 'assistant',
    model: typeof body.model === 'string' ? body.model : fallbackModel,
    content,
    stop_reason: mapFinishReason(choice.finish_reason, toolCalls.length > 0),
    stop_sequence: null,
    usage: anthropicUsageFromOpenAi(body.usage),
  };
}

export function formatAnthropicSseEvent(event: string, data: JsonObject): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/**
 * Translates an OpenAI Chat Completions SSE stream into Anthropic Messages SSE stream.
 *
 * ## Supported conversions
 *
 * | OpenAI Chat delta field | Anthropic Messages SSE event |
 * |-------------------------|-----------------------------|
 * | `delta.reasoning_content` | `content_block_start/delta/stop` (type: thinking) |
 * | `delta.content`          | `content_block_start/delta/stop` (type: text) |
 * | `delta.tool_calls[]`     | `content_block_start/delta/stop` (type: tool_use) |
 * | `choice.finish_reason`   | `message_delta` + `message_stop` |
 *
 * ## Content block ordering & indexing
 *
 * Blocks are emitted in the order they appear in the upstream stream
 * (typically thinking → text → tool_use, but the translator makes no
 * assumption about order). Each block is assigned a sequential `index`
 * the first time it opens, and that exact index is reused for every
 * subsequent delta/stop on that block — there is no shared mutable
 * "current index" that could drift. This keeps multi-block responses
 * (e.g. reasoning + several tool calls + text) correct even when block
 * types interleave.
 *
 * ## Usage
 *
 * ```typescript
 * const translator = new OpenAiChatToAnthropicStreamTranslator('glm-5.1');
 * // For each SSE chunk from the upstream:
 * const events = translator.acceptChunk(chunk);
 * events.forEach(event => clientRes.write(event));
 * ```
 */
export class OpenAiChatToAnthropicStreamTranslator {
  private messageStarted = false;
  private thinkingStarted = false;
  private textStarted = false;
  /**
   * Block index assigned to the thinking block, or null until it starts.
   *
   * Index management: each content block (thinking / text / each tool_use)
   * records the exact `index` it was opened with, so the matching
   * `content_block_delta` / `content_block_stop` events always reference the
   * right block regardless of the order in which block types appear or
   * interleave in the upstream stream. We never rely on a single mutable
   * counter that "happens to" point at the open block.
   */
  private thinkingIndex: number | null = null;
  private textIndex: number | null = null;
  /** Maps OpenAI tool_calls index → Anthropic content block index. */
  private toolUseIndexMap = new Map<number, number>();
  private nextBlockIndex = 0;
  private latestUsage: JsonObject | null = null;
  private messageId = `msg_${Date.now()}`;
  private model: string;
  private hasToolUse = false;

  constructor(model: string) {
    this.model = model;
  }

  /** Allocate the next sequential content block index. */
  private allocIndex(): number {
    return this.nextBlockIndex++;
  }

  acceptChunk(chunk: JsonObject): string[] {
    const events: string[] = [];
    if (typeof chunk.id === 'string') {
      this.messageId = chunk.id;
    }
    if (typeof chunk.model === 'string') {
      this.model = chunk.model;
    }
    if (chunk.usage) {
      this.latestUsage = anthropicUsageFromOpenAi(chunk.usage);
    }
    if (!this.messageStarted) {
      this.messageStarted = true;
      events.push(formatAnthropicSseEvent('message_start', {
        type: 'message_start',
        message: {
          id: this.messageId,
          type: 'message',
          role: 'assistant',
          model: this.model,
          content: [],
          stop_reason: null,
          stop_sequence: null,
          usage: { input_tokens: 0, output_tokens: 0 },
        },
      }));
    }
    const choice = Array.isArray(chunk.choices) && isObject(chunk.choices[0]) ? chunk.choices[0] : {};
    const delta = isObject(choice.delta) ? choice.delta : {};

    // --- Thinking / reasoning content ---
    // OpenAI-compatible providers (e.g. deepseek) send reasoning in delta.reasoning_content
    // or delta.thinking_blocks. Translate to Anthropic thinking content blocks.
    const reasoningText =
      typeof delta.reasoning_content === 'string' ? delta.reasoning_content : '';
    if (reasoningText) {
      if (!this.thinkingStarted) {
        this.thinkingStarted = true;
        this.thinkingIndex = this.allocIndex();
        events.push(formatAnthropicSseEvent('content_block_start', {
          type: 'content_block_start',
          index: this.thinkingIndex,
          content_block: { type: 'thinking', thinking: '' },
        }));
      }
      events.push(formatAnthropicSseEvent('content_block_delta', {
        type: 'content_block_delta',
        index: this.thinkingIndex,
        delta: { type: 'thinking_delta', thinking: reasoningText },
      }));
    }

    // --- Text content ---
    if (typeof delta.content === 'string' && delta.content) {
      // Close thinking block if it was open and we're transitioning to text
      if (this.thinkingStarted) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: this.thinkingIndex,
        }));
        this.thinkingStarted = false;
        this.thinkingIndex = null;
      }
      if (!this.textStarted) {
        this.textStarted = true;
        this.textIndex = this.allocIndex();
        events.push(formatAnthropicSseEvent('content_block_start', {
          type: 'content_block_start',
          index: this.textIndex,
          content_block: { type: 'text', text: '' },
        }));
      }
      events.push(formatAnthropicSseEvent('content_block_delta', {
        type: 'content_block_delta',
        index: this.textIndex,
        delta: { type: 'text_delta', text: delta.content },
      }));
    }

    // --- Tool calls ---
    // OpenAI format: delta.tool_calls is an array where each entry has index, id, function.name, function.arguments
    const toolCalls = Array.isArray(delta.tool_calls) ? delta.tool_calls.filter(isObject) : [];
    if (toolCalls.length > 0) {
      this.hasToolUse = true;
      // Close text block if transitioning from text to tool_use
      if (this.textStarted) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: this.textIndex,
        }));
        this.textStarted = false;
        this.textIndex = null;
      }
      // Close thinking block if transitioning from thinking to tool_use
      if (this.thinkingStarted) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: this.thinkingIndex,
        }));
        this.thinkingStarted = false;
        this.thinkingIndex = null;
      }
      for (const tc of toolCalls) {
        const tcIndex = typeof tc.index === 'number' ? tc.index : 0;
        // First chunk for this tool call: contains id and name
        if (!this.toolUseIndexMap.has(tcIndex)) {
          const blockIndex = this.allocIndex();
          this.toolUseIndexMap.set(tcIndex, blockIndex);
          const tcId = typeof tc.id === 'string' ? tc.id : `toolu_${tcIndex}`;
          const fn = isObject(tc.function) ? tc.function : {};
          const fnName = typeof fn.name === 'string' ? fn.name : 'tool';
          events.push(formatAnthropicSseEvent('content_block_start', {
            type: 'content_block_start',
            index: blockIndex,
            content_block: {
              type: 'tool_use',
              id: tcId,
              name: fnName,
              input: {},
            },
          }));
          // Stream any partial arguments that arrive in the first chunk.
          // Anthropic's input_json_delta carries the JSON arguments piece by piece.
          const fnArgs = typeof fn.arguments === 'string' ? fn.arguments : '';
          if (fnArgs) {
            events.push(formatAnthropicSseEvent('content_block_delta', {
              type: 'content_block_delta',
              index: blockIndex,
              delta: { type: 'input_json_delta', partial_json: fnArgs },
            }));
          }
        } else {
          // Subsequent chunks: streaming arguments
          const blockIndex = this.toolUseIndexMap.get(tcIndex)!;
          const fn = isObject(tc.function) ? tc.function : {};
          const fnArgs = typeof fn.arguments === 'string' ? fn.arguments : '';
          if (fnArgs) {
            events.push(formatAnthropicSseEvent('content_block_delta', {
              type: 'content_block_delta',
              index: blockIndex,
              delta: { type: 'input_json_delta', partial_json: fnArgs },
            }));
          }
        }
      }
    }

    // --- Finish ---
    if (choice.finish_reason) {
      // Close any still-open blocks using their own recorded index.
      if (this.thinkingStarted) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: this.thinkingIndex,
        }));
      }
      if (this.textStarted) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: this.textIndex,
        }));
      }
      // Close all tool_use blocks
      for (const [, blockIndex] of this.toolUseIndexMap) {
        events.push(formatAnthropicSseEvent('content_block_stop', {
          type: 'content_block_stop',
          index: blockIndex,
        }));
      }
      events.push(formatAnthropicSseEvent('message_delta', {
        type: 'message_delta',
        delta: { stop_reason: mapFinishReason(choice.finish_reason, this.hasToolUse), stop_sequence: null },
        usage: this.latestUsage ?? { input_tokens: 0, output_tokens: 0 },
      }));
      events.push(formatAnthropicSseEvent('message_stop', { type: 'message_stop' }));
    }
    return events;
  }

  getLatestUsage(): JsonObject | null {
    return this.latestUsage;
  }
}
