"""
Smoke test — runs the Vision Agent on a local image without LiveKit.
Usage: python agents/test_vision_agent.py <image.jpg>

Reads .env from the project root automatically.
"""

import asyncio
import os
import sys
from pathlib import Path

# load .env from project root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# stubs so VisionAgent imports cleanly without LiveKit env vars
os.environ.setdefault("LIVEKIT_URL", "")
os.environ.setdefault("LIVEKIT_TOKEN", "")

from vision_agent import describe_frame_sync


def main(image_path: str) -> None:
    with open(image_path, "rb") as f:
        jpeg_bytes = f.read()

    print(f"Sending {image_path} to Claude claude-sonnet-4-6 via Anthropic...\n")
    scene = describe_frame_sync(jpeg_bytes)

    import json
    print(json.dumps(scene, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agents/test_vision_agent.py <image.jpg>")
        sys.exit(1)
    main(sys.argv[1])
