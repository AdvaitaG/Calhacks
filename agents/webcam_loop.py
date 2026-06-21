"""
Live demo — Vision Agent + Conductor Agent on laptop webcam.
No LiveKit or robot needed. Press Q in the preview window to quit.
Usage: python agents/webcam_loop.py
"""
import os
import sys
import time
from pathlib import Path

# load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault("LIVEKIT_URL", "")
os.environ.setdefault("LIVEKIT_TOKEN", "")

try:
    import cv2
except ImportError:
    print("Install opencv: pip install opencv-python")
    sys.exit(1)

from vision_agent import describe_frame_sync
from conductor_agent import process_scene

FRAME_INTERVAL = 3.0  # seconds between API calls


def capture_jpeg(cap) -> bytes | None:
    ret, frame = cap.read()
    if not ret:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ok else None


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        sys.exit(1)

    print("Baymax live — Vision + Conductor active")
    print("Press Q in the preview window to quit.\n")

    last_call = 0.0

    try:
        while True:
            now = time.monotonic()

            if now - last_call >= FRAME_INTERVAL:
                last_call = now
                jpeg = capture_jpeg(cap)
                if jpeg:
                    try:
                        t0 = time.monotonic()
                        scene = describe_frame_sync(jpeg)
                        scene["latency_ms"] = round((time.monotonic() - t0) * 1000)
                        print(f"\n[Vision] {scene['scene_summary']} ({scene['latency_ms']}ms)")
                        process_scene(scene)
                    except Exception as e:
                        print(f"[Error] {e}")

            ret, frame = cap.read()
            if ret:
                cv2.imshow("Baymax Vision (Q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
