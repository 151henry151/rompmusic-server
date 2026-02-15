# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY rompmusic_server ./rompmusic_server
COPY .env.example .env

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "rompmusic_server.main:app", "--host", "0.0.0.0", "--port", "8080"]
