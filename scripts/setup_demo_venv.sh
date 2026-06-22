#!/bin/bash
# One-time: add the BRAIN's libraries to the 3.11 venv (~/baymax-bridge) so the
# ENTIRE demo — agents + camera + listener — runs in ONE distro from ONE script.
# The SDK, Band, LiveKit, dotenv are already in this venv; this adds the agent LLM
# stack + OpenCV (for the synthetic camera).
#
#   bash scripts/setup_demo_venv.sh
set -e

VENV="$HOME/baymax-bridge"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[demo-venv] installing brain deps into $VENV ..."
# langchain (umbrella, for band's adapter's `from langchain.agents import create_agent`)
# + the integrations + langgraph + opencv (camera) + pillow (vision frame decode).
"$VENV/bin/pip" install langchain langgraph langchain-google-genai langchain-openai opencv-python pillow

echo "[demo-venv] verifying the agents import cleanly on Python 3.11 ..."
cd "$REPO"
"$VENV/bin/python" - <<'PY'
import langgraph, cv2, band, PIL
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter
from langchain.agents import create_agent          # band adapter needs this
from langchain_google_genai import ChatGoogleGenerativeAI
import booster_robotics_sdk_python
print("brain deps OK")
PY
echo "[demo-venv] DONE — now run scripts/run_demo.sh"
