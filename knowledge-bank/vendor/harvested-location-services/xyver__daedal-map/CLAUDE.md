# County Map - Public Repo Instructions

Rules for working inside `county-map/`, the public application repo. This file
holds durable rules only, not a map of the codebase.

**For architecture, request lifecycle, and which doc owns what, read
[docs/CONTEXT.md](docs/CONTEXT.md) first.** That is the start-here router and
it stays current. Do not use this file for orientation.

---

## This repo is public

Everything here is world-readable. Data processing scripts, internal planning,
business docs, and operational runbooks belong in the private repo, not here.

---

## Research and search

When asked to read, research, search, or investigate something, do it
completely before answering or building. Partial reads that agree with each
other feel like coverage and are not.

**Docs before code.** Start at [docs/CONTEXT.md](docs/CONTEXT.md), the
start-here router. Follow every route it names for the topic, not just the
first one that matches the immediate question - the owning doc usually names
the owning code and the known gaps.

**Read to the end.** Do not stop when the immediate question is answered.
Ownership tables, change procedures, and "remaining gaps" sections sit at the
bottom of a doc, and those are the parts that say whether the thing you are
about to build already exists.

**Finish the search before concluding.** Do not cap a discovery search with
`head` and treat the result as the inventory - results sort alphabetically, so
a cap silently hides whatever sorts late. Either take the full list, or count it
first and say out loud that you are looking at a sample.

**Search by concept, not by guessed implementation.** The thing that already
exists may be a `.md`, `.json`, or `.csv` rather than the `.py` you assumed.
Search all file types before concluding nothing owns a job.

**Assume an owner exists.** Before writing a new script, table, or mapping, find
the current owner and extend it. A parallel path that duplicates an existing one
is worse than no change.

---

## Serialization: MessagePack, not JSON

All API responses use MessagePack.

Backend:

- never `JSONResponse` or `json.dumps()` for API responses
- use `msgpack_response()` from `app.py`, and `msgpack_error()` for errors
- decode POST bodies with `decode_request_body()`

```python
return msgpack_response({"events": data, "count": len(data)})
return msgpack_error("Not found", 404)

body = await decode_request_body(request)
```

Frontend:

- never `response.json()` or `JSON.parse()` for API responses
- use `fetchMsgpack()` / `postMsgpack()` from `utils/fetch.js`

```javascript
import { fetchMsgpack, postMsgpack } from './utils/fetch.js';

const data = await fetchMsgpack('/api/earthquakes');
const result = await postMsgpack('/api/settings', { theme: 'dark' });
```

---

## Encoding

Plain alphanumerics and basic punctuation only - in code, comments, docs, and
commit messages. No emoji, box-drawing, arrows, checkmarks, or smart quotes.
They cause encoding failures on this Windows setup.

---

## Windows environment

Development happens on Windows. Prefer the dedicated tools over shell commands
for file work - they handle Windows paths without quoting problems:

1. **Glob** - find files by pattern
2. **Read** - read a file
3. **Grep** - search file contents
4. **Shell** - only when no tool fits

Do not use `ls`, `find`, or `cat` against Windows-style paths, and do not mix
PowerShell and Bash syntax in one command. PowerShell has no `&&`; chain with
`;`.

When searching for application code, search within this repo rather than
sibling build or test folders.

## Communication style

Write like an engineer or researcher in a design discussion. Normal paragraphs,
not one line per sentence.

- Lead with the result, blocker, or decision in plain language.
- End the message when the information ends. No closing sentence whose only
  job is to summarize, elevate, or say why the preceding point matters.
- State the observation, not what should be concluded from it. No "which is
  why," "the thing to notice," "worth flagging," or equivalents.
- Never give a number you did not count. No estimated percentages, no "four
  or five times." Count it or say you didn't.
- When corrected: state the correction and stop. Do not categorize the error,
  list what you got right, or note it as a lesson.
- Length follows information, not the apparent weight of the question. A
  three-sentence answer stays three sentences.
- Do not restate the user's position before responding to it.
- Do not announce file hygiene, formatting, or that a report is "clean" unless
  it affects the work.
- Headings and lists only when items are genuinely parallel or a decision
  depends on the structure.
- For audits: confirmed problem, evidence, impact, recommended next action,
  decision needed.
