# Knowledge bank

Central research store for Abhinav-level computational design and computational
logistics: skills, plugins, MCP servers, solvers, routing engines and guides,
pulled from open-source repositories and arranged so nothing collides.

- `sources.yaml`: the only input. One entry per upstream repo.
- `vendor/<category>/<owner>__<repo>/`: verbatim snapshot, no git history.
- `MANIFEST.json`: per source: license, commit, status, files, bytes, what was skipped.
- `SOURCES.md`, `ATTRIBUTION.md`: generated. Do not edit.

## Rules that keep it conflict-free and legal
1. **One folder per source**, named `owner__repo`. Sources never share files.
2. **Never edit `vendor/`.** Our code lives outside `knowledge-bank/`
   (`tools/`, `tests/`, and later `skills/`, `lib/`). Re-running the tool overwrites `vendor/`.
3. **License is read from the repo's own license file, not from memory or search snippets.**
   Vendored only if permissive (MIT, Apache-2.0, BSD, ISC, Unlicense, CC0, BSL-1.0, Zlib, CC-BY-4.0),
   or CC-BY-SA-4.0 when the entry opts in. Copyleft (GPL/AGPL/LGPL/EPL/MPL), non-commercial,
   no-license and unknown become **link-only**: recorded in the manifest, never copied.
4. **Every vendored folder keeps upstream LICENSE/NOTICE/README.** Credit is in `ATTRIBUTION.md`.
5. **Not copied:** git history, `.gitignore`/`.gitattributes`/`.gitmodules`, videos, archives,
   binaries, files over 3 MB. Big repos use `include:`/`exclude:` so the bank stays reviewable.
6. **The license check covers the repo root only.** A permissive repo can still contain
   a third-party subfolder under another license. Check before reusing code outside this bank.
7. Share-alike material (CC-BY-SA-4.0) stays in its own folder; credit the author and
   release any changes under the same license.

## Use
```
python3 tools/kb_sync.py --check            # classify licenses only, copy nothing
python3 tools/kb_sync.py                    # rebuild everything
python3 tools/kb_sync.py --only owner__repo # refresh one source
python3 -m pytest tests                     # license classifier tests
```
Add a source: append to `sources.yaml` (`id`, `url`, `category`, `why`; optional `include`,
`exclude`, `license_note`, `allow_sharealike`, `policy: link-only`), run `--check`, then sync.

## Not covered yet
Frontier model weights, datasets, and logistics benchmark instances (e.g. VRP benchmarks)
are not in the bank. Hugging Face is unreachable from this environment, so model licenses
could not be verified, and I will not list a model's license from memory.
Datasets such as OpenStreetMap extracts are ODbL (share-alike): fetch at use time, do not vendor.
