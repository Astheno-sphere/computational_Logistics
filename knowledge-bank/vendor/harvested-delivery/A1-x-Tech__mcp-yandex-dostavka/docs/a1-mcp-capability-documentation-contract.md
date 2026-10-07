# A1 MCP Capability Documentation Contract

Use this contract when creating or materially changing a public MCP tool. It defines the human-facing documentation that accompanies the runtime contract.

## Canonical folder

Store every public capability page under <code>docs/capabilities/</code>:

- <code>docs/capabilities/index.md</code> is the user-facing catalog;
- <code>docs/capabilities/&lt;tool-name&gt;.md</code> documents one registered MCP tool.

The neutral folder name is shared with repositories whose capabilities are implemented as skills, tools, commands or workflows. The page itself must name the concrete implementation type.

## Internal analysis, public language

Use Next Move Theory / AJTBD internally to identify the desired transition, the user's success criteria, the preceding and following steps, and the exact point where the tool changes real data.

Publish the result in ordinary Russian. Public capability pages must not expose methodology labels such as Core Job, Big Job, Micro Job, Job Graph, Critical Chain of Jobs, AJTBD or NMT. Translate the analysis into:

- one sentence beginning with «Я хочу»;
- when the tool is useful;
- what the user must provide;
- what the user receives;
- what changes in Яндекс Доставке;
- what action normally comes before or after.

## Page opening

Use the title grammar <code>A1 · Яндекс Доставка · &lt;понятное действие&gt;</code>.

Immediately below the title, before the first level-two heading, add a unique category sentence:

<code>**MCP-инструмент (tool) для Яндекс Доставки:** помогает &lt;получить узнаваемый результат&gt;.</code>

Place the exact registered tool name on the next line. The category sentence is the canonical short web summary and may be reused as a meta description after removing Markdown emphasis.

## Required content

Every tool page must contain these sections in this order:

1. <code>## Какую задачу решает</code> — one blockquote in the form «Я хочу + глагол».
2. <code>## Когда использовать</code>.
3. <code>## Что нужно передать</code>.
4. <code>## Что вернёт</code>.
5. <code>## Что изменится в Яндекс Доставке</code>.
6. <code>## Пример запроса</code>.
7. <code>## Возможные ошибки и ограничения</code>.
8. <code>## Связанные MCP-инструменты</code>.
9. <code>## Технические сведения</code>.

Keep the page useful to a non-developer. Link to <code>docs/TOOLS.md</code> for exhaustive schemas instead of copying every field.

## State-change boundary

Copy the impact class from the tool annotations and use exactly one label:

- <code>**Воздействие:** только чтение</code>;
- <code>**Воздействие:** изменяет данные</code>;
- <code>**Воздействие:** опасная операция</code>.

State the real effect in plain language. For price checks and offer calculations, say whether an order is created. For claim creation, distinguish a prepared claim from a confirmed delivery. For confirmation and cancellation, state that the call changes a real order.

Never promise retries, idempotency, rollback, cancellation availability or price stability beyond what the implementation proves.

## Source hierarchy

Use repository evidence in this order:

1. registered tool description and input schema in <code>src/tools/</code>;
2. per-tool annotations pinned by <code>src/tools/annotations.test.ts</code>;
3. client behavior and tests;
4. <code>docs/TOOLS.md</code> and README summaries.

When sources disagree, implementation and tests win. Treat an unsupported marketing claim as unknown rather than filling the gap.

## Web publication

Treat every Markdown page as the canonical source for GitHub, the website and agent-readable delivery. Keep calls to action in the website layout so the same content can be published without a rewritten copy.

When the hosting stack supports it, expose the same source through a stable <code>.md</code> URL or <code>Accept: text/markdown</code>, and advertise that representation with HTML and HTTP <code>Link</code> alternates. Do not create a parallel Markdown content store.

## Completion

A public tool change is complete when:

- its capability page and catalog entry exist;
- state-change language matches the annotation;
- related-tool links reflect the actual delivery sequence;
- the capability documentation test passes;
- <code>docs/TOOLS.md</code> remains aligned with the wire-level contract.
