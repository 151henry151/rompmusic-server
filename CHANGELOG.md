# Changelog

All notable changes to rompmusic-server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Normalize search input into lowercase tokens before applying filters.

### Fixed

- Replace phrase-level `ilike` matching with tokenized case-insensitive matching in `/search` for artists, albums, and tracks.
- Apply tokenized case-insensitive matching to `/library/artists`, `/library/albums`, and `/library/tracks` search filters.

## [0.1.5] - 2026-03-05

### Changed

- Synchronize server version metadata with umbrella/client `0.1.5` release references.
- Set `pyproject.toml` project version to `0.1.5`.

## [0.1.4] - 2026-02-14

Synchronize server version metadata with umbrella/client `0.1.4` release references.

## [0.1.3] - 2026-02-14

Synchronize server version metadata with umbrella/client `0.1.3` release references.

## [0.1.1] - 2026-02-14

Synchronize server version metadata with umbrella/client `0.1.1` release references.

## [0.1.0] - 2026-02-14

First stable release. Version sync with umbrella and client.

### Changed

- Set version to `0.1.0` and drop beta designation.

## [0.1.0-beta.17] - 2026-03-01

### Changed

- Synchronize version metadata with umbrella/client beta.17 release references (no server-specific code changes).

## [0.1.0-beta.16] - 2026-03-01

### Changed

- Synchronize version metadata with umbrella/client beta.16 release references (no server-specific code changes).

## [0.1.0-beta.15] - 2026-03-01

### Changed

- Synchronize version metadata with umbrella/client beta.15 release references (no server-specific code changes).

## [0.1.0-beta.14] - 2026-03-01

### Changed

- Synchronize version metadata with umbrella/client beta.14 release references (no server-specific code changes).

## [0.1.0-beta.1] - 2025-02-15

First beta release. Part of RompMusic 0.1.0-beta.1.

### Added

- Build FastAPI backend services with PostgreSQL and Redis.
- Implement library scanning with Mutagen metadata parsing (MP3, FLAC, M4A, OGG, OGA, Opus).
- Stream live scan progress over Server-Sent Events (SSE).
- Add admin dashboard login, library statistics, and scan controls.
- Emit startup status messages ("Opening music directory", "Discovering files", "Found N files") plus per-file progress.
- Add JWT authentication and admin-user creation.
- Expose REST APIs for library, search, streaming, playlists, and artwork.
- Publish Swagger and ReDoc API documentation.

### Fixed

- Emit per-file scan progress callbacks and apply SSE-friendly nginx buffering settings so progress updates stream continuously.

[Unreleased]: https://github.com/151henry151/rompmusic-server/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.5
[0.1.4]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.4
[0.1.3]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.3
[0.1.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.1
[0.1.0]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0
[0.1.0-beta.17]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.17
[0.1.0-beta.16]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.16
[0.1.0-beta.15]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.15
[0.1.0-beta.14]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.14
[0.1.0-beta.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.1
