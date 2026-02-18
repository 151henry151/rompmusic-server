#!/usr/bin/env python3
"""One-off: try extract_metadata on paths that are on disk but not in DB.
Run from repo root with: docker exec -i rompmusic-server-1 python3 - < rompmusic-server/scripts/diagnose_metadata.py
Or with paths passed via stdin.
"""
import sys
from pathlib import Path

# Add app to path when run inside container
sys.path.insert(0, "/app")
from rompmusic_server.services.scanner import extract_metadata

MUSIC = Path("/music")

def main():
    paths = [line.strip() for line in sys.stdin if line.strip()]
    ok = 0
    fail = 0
    errors = {}
    for i, rel in enumerate(paths):
        if i >= 200:  # Sample first 200 missing
            break
        path = MUSIC / rel
        if not path.exists():
            print(f"NOT_FOUND: {rel}", file=sys.stderr)
            fail += 1
            continue
        try:
            meta = extract_metadata(path)
            if meta:
                ok += 1
            else:
                fail += 1
                # Try again with exception to see why
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(str(path))
                    if audio is None:
                        errors["MutagenFile returned None"] = errors.get("MutagenFile returned None", 0) + 1
                    else:
                        errors["metadata returned None (no exception)"] = errors.get("metadata returned None (no exception)", 0) + 1
                except Exception as e:
                    key = type(e).__name__ + ": " + str(e)[:80]
                    errors[key] = errors.get(key, 0) + 1
        except Exception as e:
            fail += 1
            key = type(e).__name__ + ": " + str(e)[:80]
            errors[key] = errors.get(key, 0) + 1
    print(f"OK: {ok}, FAIL: {fail}", file=sys.stderr)
    for k, v in sorted(errors.items(), key=lambda x: -x[1]):
        print(f"  {v}: {k}", file=sys.stderr)

if __name__ == "__main__":
    main()
