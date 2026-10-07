Generate or revise a single paper section through EasyPaper.

## Required inputs

- `section_type` (one of: `introduction`, `method`, `experiment`, `result`, `related_work`, `discussion`, `abstract`, `conclusion`)
- `metadata` object with core paper fields

## Optional inputs

- `prior_sections` for synthesis sections (`abstract`, `conclusion`)
- `style_guide`

## Action

Send a request to `POST /metadata/generate/section` and return:

- section status
- generated LaTeX content
- word count and citation notes when available

$ARGUMENTS
