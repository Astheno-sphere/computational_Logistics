# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-24

### Added
- New `book_batch_and_label` tool: book many Royal Mail orders in one call and get back a single merged PDF of every label, ready to print. All orders share the same service, package format and sender.
- `get_label` now saves the label to disk and returns a file path instead of a base64 string in JSON. Default location: `~/Downloads/parcel-toolkit/`, overridable via `PARCEL_TOOLKIT_LABELS_DIR`.
- New dependency: `pdf-lib` for merging PDFs.

### Changed
- **Breaking:** `get_label` response shape changed. Old response had `labelBase64`; new response has `filePath`. The label file is written to disk as part of the call. Callers expecting the base64 payload should either read the file from `filePath` or pin to `0.1.x`.

### Fixed
- `createOrder` now includes `unitWeightInGrams` when building the `contents` array from `goodsDescription`. Without it, Click & Drop's API rejected the booking with *"When value 'SKU' is not provided values 'UnitValue' and 'UnitWeightInGrams' are required."* This bug blocked any booking that passed `goodsDescription`.

## [0.1.0] - 2026-04-22

### Added
- Initial release.
- Five MCP tools: `book_order`, `get_label`, `track_order`, `cancel_order`, `list_services`.
- Friendly keys for 33 Royal Mail and Parcelforce services (UK 1st/2nd Class, Tracked 24/48, Special Delivery, Parcelforce express, international).
- Raw Service Register codes (`OLP1`, `TOLP24`, `PFE48`, etc.) also accepted at booking.
- Verified against the live Click & Drop API on 2026-04-22: booking, tracking and cancellation tested end-to-end on a real account; label retrieval verified against spec for OBA accounts.
