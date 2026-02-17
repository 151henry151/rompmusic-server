# Changelog

All notable changes to rompmusic-server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- (Changes since last release will be listed here)

## [0.1.0-beta.2] - 2026-02-17

### Added

- Optional automated library scan: set `AUTO_SCAN_INTERVAL_HOURS` (e.g. 24 for daily). See Configuration in README.
- Optional Beets automation: set `BEETS_AUTO_INTERVAL_HOURS` (e.g. 24) to run `beet fetch-art` in the music directory.
- Album list supports `artwork_first` query param (default true) to put albums with artwork first; client setting `albums_artwork_first` in default client settings.

### Changed

- Library scan runs in a background task with its own DB session; progress streamed via SSE. Closing the admin tab no longer cancels the scan.
- Album search matches artist name and any track title on the album (not only album title).
- Album tracks ordered by disc number then track number when requested by album (correct multi-disc order).
- Dashboard shows scan error message when a scan fails instead of reloading.

## [0.1.0-beta.1] - 2025-02-15

First beta release. Part of RompMusic 0.1.0-beta.1.

### Added

- FastAPI backend with PostgreSQL and Redis
- Library scanner with Mutagen for metadata (MP3, FLAC, M4A, OGG, OGA, Opus)
- Server-Sent Events (SSE) stream for live scan progress
- Admin dashboard with login, library statistics, and scan UI
- Live startup status messages: "Opening music directory", "Discovering files", "Found N files", per-file progress
- JWT authentication and admin user creation
- REST API for library, search, streaming, playlists, artwork
- Swagger and ReDoc API documentation

### Fixed

- Library scan progress stuck at 0% (per-file progress callbacks, SSE-friendly nginx config)

[Unreleased]: https://github.com/151henry151/rompmusic-server/compare/v0.1.0-beta.2...HEAD
[0.1.0-beta.2]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.1
