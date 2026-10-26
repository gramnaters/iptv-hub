#!/usr/bin/env python3
"""
ZEE5 playlist generator.
Generates playlists/zee5.m3u containing all active ZEE5 channels with verified ClearKeys
and streams from catalogs/zee5_blocks.json.
"""
import json
import os
import sys
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKS_FILE = os.path.join(ROOT, "catalogs", "zee5_blocks.json")
STATUS = os.path.join(ROOT, "catalogs", "zee5_status.json")
OUT = os.path.join(ROOT, "playlists", "zee5.m3u")


def main():
    if not os.path.exists(BLOCKS_FILE):
        print(f"Missing ZEE5 blocks catalog: {BLOCKS_FILE}")
        return 1

    with open(BLOCKS_FILE, "r", encoding="utf-8") as f:
        blocks = json.load(f)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(blocks)}",
        "",
    ]

    for b in blocks:
        lines.extend(b)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"updated_at": stamp, "total_channels": len(blocks)}, f, indent=2)

    print(f"ZEE5: generated {OUT} ({len(blocks)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
