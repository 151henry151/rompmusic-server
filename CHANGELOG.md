# Changelog

All notable changes to rompmusic-server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- (Changes since last release will be listed here)

## [0.1.4] - 2026-02-14

Version sync with umbrella and client.

## [0.1.3] - 2026-02-14

Version sync with umbrella and client.

## [0.1.1] - 2026-02-14

Version sync with umbrella and client.

## [0.1.0] - 2026-02-14

First stable release. Version sync with umbrella and client.

### Changed

- Version set to 0.1.0 (no longer beta)

## [0.1.0-beta.17] - 2026-03-01

### Changed

- Version sync with umbrella and other submodules (no server-specific changes this release)

## [0.1.0-beta.16] - 2026-02-16

### Changed

- Version sync with umbrella and other submodules (no server-specific changes this release)

## [0.1.0-beta.15] - 2026-03-16

### Changed

- Version sync with umbrella and other submodules (no server-specific changes this release)

## [0.1.0-beta.14] - 2026-03-01

### Changed

- Version sync with umbrella and other submodules (no server-specific changes this release)

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

[Unreleased]: https://github.com/151henry151/rompmusic-server/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.4
[0.1.3]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.3
[0.1.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.1
[0.1.0]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0
[0.1.0-beta.17]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.17
[0.1.0-beta.16]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.16
[0.1.0-beta.15]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.15
[0.1.0-beta.14]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.14
[0.1.0-beta.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.1
