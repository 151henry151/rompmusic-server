# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extract embedded artwork from music files using Mutagen."""

import base64
import json
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC


def extract_artwork_from_file(file_path: Path) -> tuple[bytes, str] | None:
    """
    Extract embedded album artwork from a music file.
    Returns (image_bytes, mime_type) or None if no artwork found.
    """
    if not file_path.exists():
        return None
    try:
        audio = MutagenFile(str(file_path))
        if audio is None:
            return None

        # ID3 (MP3) - need full ID3 for APIC
        ext = file_path.suffix.lower()
        if ext in (".mp3", ".mp2", ".mp1"):
            try:
                id3 = ID3(str(file_path))
                for apic in id3.getall("APIC"):
                    if getattr(apic, "data", None):
                        mime = getattr(apic, "mime", "image/jpeg") or "image/jpeg"
                        return (bytes(apic.data), mime)
            except Exception:
                pass

        # MP4/M4A
        if isinstance(audio, MP4) and audio.tags:
            covr = audio.tags.get("covr")
            if covr and len(covr) > 0:
                data = bytes(covr[0])
                mime = "image/jpeg" if data[:2] == b"\xff\xd8" else "image/png"
                return (data, mime)

        # FLAC
        if isinstance(audio, FLAC) and hasattr(audio, "pictures"):
            for pic in audio.pictures:
                if pic.data:
                    mime = getattr(pic, "mime", "image/jpeg") or "image/jpeg"
                    return (bytes(pic.data), mime)

        # Ogg Vorbis/Opus
        if hasattr(audio, "tags") and audio.tags and "metadata_block_picture" in audio.tags:
            for b64 in audio.tags["metadata_block_picture"]:
                try:
                    raw = base64.b64decode(b64)
                    pic = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                    if isinstance(pic, dict) and pic.get("data"):
                        d = pic["data"]
                        if isinstance(d, list):
                            d = bytes(d)
                        elif isinstance(d, str):
                            d = base64.b64decode(d)
                        mime = pic.get("mime", "image/jpeg") or "image/jpeg"
                        return (bytes(d), mime)
                except Exception:
                    continue

        return None
    except Exception:
        return None
