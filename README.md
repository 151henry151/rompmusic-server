# RompMusic Server

Libre self-hosted music streaming server. Part of the [RompMusic](https://rompmusic.com) project.

## License

GPL-3.0-or-later. See [LICENSE](../LICENSE).

## Features

- Multi-user authentication (JWT)
- Music library management
- HTTP range request streaming
- RESTful API at `/api/v1/`
- Web admin panel
- Metadata extraction (Mutagen)
- Optional beets integration

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install
pip install -e .

# Configure (copy and edit)
cp .env.example .env

# Run
uvicorn rompmusic_server.main:app --reload
```

## Configuration

Environment variables (see `.env.example`). Notable options:

| Variable | Default | Description |
|----------|--------|-------------|
| `MUSIC_PATH` | `/music` | Path to your music library |
| `AUTO_SCAN_INTERVAL_HOURS` | `0` (disabled) | Run a library scan every N hours (e.g. `24` for daily). Scan runs in the background. |
| `BEETS_AUTO_INTERVAL_HOURS` | `0` (disabled) | Run `beet fetch-art -y` in the music directory every N hours (e.g. `24` for daily). Requires `beet` on the PATH. |

The library scan triggered from the admin dashboard runs in a background task with its own database session, so it continues even if you close the browser tab.

## Docker

```bash
docker build -t rompmusic-server .
docker run -p 8080:8080 -v /path/to/music:/music rompmusic-server
```
