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

## Docker

```bash
docker build -t rompmusic-server .
docker run -p 8080:8080 -v /path/to/music:/music rompmusic-server
```
