# Changelog

All notable changes to rompmusic-server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Account deletion** — `DELETE /api/v1/auth/me` (authenticated): permanently deletes the current user and all related data (verification codes, password reset tokens, play history, playlists; invitations’ `invited_by_id` set to null). Returns 401 without token. Required for App Store account-deletion policy.

## [0.1.0-beta.7] - 2026-02-26

### Changed

- **Scanner** — Album key is now `(album_title, year)` instead of `(artist_name, album_title)`. One album row per release so tracks with different per-track artists (e.g. "Miles Davis" vs "Miles Davis Feat. Easy Mo Bee" on "Doo-Bop") stay in the same album. Lookup by title + year; new albums use the first track's artist as the album's primary artist.

## [0.1.0-beta.6] - 2026-02-16

### Added

- **Admin** — Full re-scan: dashboard "Full re-scan" button and `POST /server/scan/stream?full_rescan=1`. Clears all library data (play history, playlist tracks, tracks, albums, artists) then rescans. Runs in the same background task as normal scan, so it continues even if the browser is closed.

### Changed

- **Scanner** — `clear_library(session)` for full re-scan; imports for `delete`, `PlayHistory`, `PlaylistTrack`.
- **Streaming** — Range requests use `StreamingResponse` instead of `Response` for compatibility with iOS/Safari.

## [0.1.0-beta.5] - 2026-02-19

### Changed

- **Artwork endpoint** — When no artwork is found (or album/tracks not found), the handler now **commits** the album update (`artwork_hash` / `has_artwork` cleared) before raising 404, so the correction persists instead of being rolled back. Also clears and commits on “Album or tracks not found” 404.
- **Stream endpoint** — Defensive error handling: check for missing `track.file_path`; wrap `stat` and file read in `OSError` handling with logging; pass `str(full_path)` to `FileResponse`; top-level try/except logs any uncaught exception and returns 500 with a safe detail so server logs show the real cause of stream failures.
- **List albums** — Track counts are fetched in a single batched query (by `album_id` in the result set) instead of one query per album (N+1), improving response time for the library page.

## [0.1.0-beta.4] - 2026-02-18

### Added

- **Artwork hash for album grouping** — Each album can store an `artwork_hash` (SHA-256 of the cover image bytes). It is set when artwork is first served (`GET /api/v1/artwork/album/{id}`) and during library scan when embedded art is found. The album list API returns `artwork_hash` so the client can group albums with identical cover art into one entry.

### Changed

- **Default scan and Beets intervals** — `AUTO_SCAN_INTERVAL_HOURS` and `BEETS_AUTO_INTERVAL_HOURS` now default to `24` (daily) instead of `0` (disabled). Set to `0` in config to disable automation.

## [0.1.0-beta.3] - 2026-02-16

### Added

- Resend welcome email: admin can send a welcome email to any user from the dashboard (username + login link; suggests "Forgot password" if needed).
- Logo and favicon in admin dashboard (static `/logo.png`, favicon in base template).

### Changed

- Invite flow: admin sets only username (no password field); password defaults to the same value as username. Invite email tells the user their username and that password is the same when set, or asks them to choose username and password when opening the link when not set.
- Dashboard invite form: password field removed; optional username and optional personal message only.

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

[Unreleased]: https://github.com/151henry151/rompmusic-server/compare/v0.1.0-beta.5...HEAD
[0.1.0-beta.5]: https://github.com/151henry151/rompmusic-server/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/151henry151/rompmusic-server/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/151henry151/rompmusic-server/releases/tag/v0.1.0-beta.1
