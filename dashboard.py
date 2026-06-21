"""
dashboard.py — Baymax Live Pipeline Dashboard

Connects to Band as a passive observer and shows what every agent is doing
in real time. Open http://localhost:8000 in a browser while agents are running.

Setup:
  1. Register a "dashboard" agent at app.band.ai
  2. Add DashboardID + DashboardBandAPI to .env
  3. Invite the dashboard agent to your Band room
  4. Run: python dashboard.py

"""
import asyncio
import json
import os
import sys
import time
import threading
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

from band.platform.link import BandLink
from band.platform.event import RoomAddedEvent, MessageEvent
from band.client.rest import DEFAULT_REQUEST_OPTIONS
from agents.shared.config import WS_URL, REST_URL

# ---------------------------------------------------------------------------
# Shared state — updated by Band listener, read by SSE clients
# ---------------------------------------------------------------------------

state = {
    "vision":        {"summary": "—", "hazard": "NONE", "obstacles": [], "terrain": "—", "latency_ms": 0, "ts": 0, "thinking": ""},
    "threat":        {"level": "NONE", "description": "—", "ts": 0, "thinking": ""},
    "conductor":     {"decision": "—", "reason": "—", "ts": 0, "thinking": ""},
    "upper_left":    {"arm_action": "—", "free_arm": "—", "ts": 0, "thinking": ""},
    "upper_right":   {"arm_action": "—", "free_arm": "—", "ts": 0, "thinking": ""},
    "lower":         {"gait_action": "—", "pace_ms": 0, "ts": 0, "thinking": ""},
    "safety":        {"status": "—", "reason": "—", "ts": 0, "thinking": ""},
    "spine":         {"status": "—", "ts": 0, "thinking": ""},
    "final_command": {"command": "—", "reason": "—", "path": "—", "left_arm": "—", "right_arm": "—", "free_arm": "—", "gait": "—", "ts": 0},
    "pipeline_latency_ms": None,   # wall-clock ms from [SCENE] recv to [FINAL_COMMAND] recv
    "latency_history": [],         # last 10 latency values for sparkline
    "message_count": 0,
    "connected":     False,
    "log":           [],
}
_scene_recv_ms: int | None = None   # wall-clock time the last [SCENE] arrived
_log_deque: deque = deque(maxlen=30)
_listeners: list[asyncio.Queue] = []
_loop: asyncio.AbstractEventLoop | None = None


def _now_ms() -> int:
    return round(time.time() * 1000)


def _ts_label(ts: int) -> str:
    if ts == 0:
        return "—"
    return datetime.fromtimestamp(ts / 1000).strftime("%H:%M:%S")


def _push_update():
    state["log"] = list(_log_deque)
    for q in list(_listeners):
        try:
            q.put_nowait(json.dumps(state))
        except Exception:
            pass


def _log(sender: str, content: str, tag: str):
    _log_deque.append({
        "ts": _now_ms(),
        "sender": sender,
        "content": content[:200],
        "tag": tag,
    })


def _thinking(content: str, max_len: int = 120) -> str:
    """Extract a short readable excerpt for the 'thinking' field."""
    text = content.strip()
    # strip tag prefix
    for tag in ("[SCENE]", "[THREAT]", "[TASK]", "[READY]", "[APPROVED]",
                "[VETOED]", "[REFLEX]", "[HALT]", "[REFLEX_EXECUTED]", "[FINAL_COMMAND]"):
        if tag in text:
            idx = text.index(tag)
            text = text[idx + len(tag):].strip()
            break
    # try to extract 'reason' from JSON
    try:
        data = json.loads(text[:text.rindex("}") + 1] if "}" in text else text)
        if "reason" in data:
            return data["reason"][:max_len]
        if "description" in data:
            return data["description"][:max_len]
        if "scene_summary" in data:
            return data["scene_summary"][:max_len]
    except Exception:
        pass
    return text[:max_len]


def _parse_message(content: str, sender: str):
    global _scene_recv_ms
    content = content.strip()
    state["message_count"] += 1
    sender_lower = sender.lower()

    if content.startswith("[SCENE]"):
        _scene_recv_ms = _now_ms()   # start the pipeline clock
        _log(sender, content, "SCENE")
        try:
            data = json.loads(content[7:].strip())
            state["vision"].update({
                "summary":    data.get("scene_summary", "—"),
                "hazard":     data.get("hazard_level", "NONE"),
                "obstacles":  data.get("obstacles", []),
                "terrain":    data.get("terrain", "—"),
                "latency_ms": data.get("latency_ms", 0),
                "ts":         data.get("timestamp", _now_ms()),
                "thinking":   data.get("scene_summary", "")[:120],
            })
        except Exception:
            state["vision"]["thinking"] = content[7:120]

    elif "[THREAT]" in content:
        _log(sender, content, "THREAT")
        try:
            start = content.index("[THREAT]") + 8
            data = json.loads(content[start:].strip())
            state["threat"].update({
                "level":       data.get("threat_level", "NONE"),
                "description": data.get("description", "—"),
                "ts":          _now_ms(),
                "thinking":    data.get("description", "")[:120],
            })
        except Exception:
            state["threat"].update({"level": "UNKNOWN", "description": content[:80], "ts": _now_ms(),
                                    "thinking": content[:120]})

    elif "[TASK]" in content:
        _log(sender, content, "TASK")
        try:
            start = content.index("[TASK]") + 6
            data = json.loads(content[start:].strip())
            state["conductor"].update({
                "decision": data.get("decision", "—"),
                "reason":   data.get("reason", "—"),
                "ts":       _now_ms(),
                "thinking": data.get("reason", "")[:120],
            })
        except Exception:
            state["conductor"].update({"decision": "dispatched", "reason": content[:80], "ts": _now_ms(),
                                       "thinking": content[:120]})

    elif "[READY]" in content:
        _log(sender, content, "READY")
        try:
            start = content.index("[READY]") + 7
            data = json.loads(content[start:].strip())
            entry = {
                "arm_action": data.get("arm_action", "—"),
                "free_arm":   data.get("free_arm_action", "—"),
                "ts":         _now_ms(),
                "thinking":   _thinking(content),
            }
            if "upperleft" in sender_lower or "upper_left" in sender_lower:
                state["upper_left"].update(entry)
            elif "upperright" in sender_lower or "upper_right" in sender_lower:
                state["upper_right"].update(entry)
            elif "lower" in sender_lower:
                state["lower"].update({
                    "gait_action": data.get("gait_action", "—"),
                    "pace_ms":     data.get("pace_ms", 0),
                    "ts":          _now_ms(),
                    "thinking":    _thinking(content),
                })
        except Exception:
            pass

    elif "[APPROVED]" in content:
        _log(sender, content, "APPROVED")
        state["safety"].update({"status": "APPROVED", "reason": "Command approved", "ts": _now_ms(),
                                "thinking": "Command approved ✓"})

    elif "[VETOED]" in content:
        _log(sender, content, "VETOED")
        try:
            start = content.index("[VETOED]") + 8
            data = json.loads(content[start:].strip())
            reason = data.get("reason", "—")
            state["safety"].update({"status": "VETOED", "reason": reason, "ts": _now_ms(),
                                    "thinking": reason[:120]})
        except Exception:
            state["safety"].update({"status": "VETOED", "reason": "—", "ts": _now_ms(), "thinking": ""})

    elif "[REFLEX]" in content or "[HALT]" in content:
        tag = "REFLEX" if "[REFLEX]" in content else "HALT"
        _log(sender, content, tag)
        state["spine"].update({"status": "REFLEX FIRED", "ts": _now_ms(),
                               "thinking": "Emergency reflex triggered!"})
        state["safety"].update({"status": "—", "reason": "—", "ts": 0, "thinking": ""})

    elif "[REFLEX_EXECUTED]" in content:
        _log(sender, content, "REFLEX_EXECUTED")
        state["spine"].update({"status": "REFLEX EXECUTED", "ts": _now_ms(),
                               "thinking": "Reflex command sent to robot"})

    elif "FINAL_COMMAND" in content:
        _log(sender, content, "FINAL_COMMAND")
        # measure end-to-end pipeline latency
        if _scene_recv_ms is not None:
            latency = _now_ms() - _scene_recv_ms
            state["pipeline_latency_ms"] = latency
            history = state["latency_history"]
            history.append(latency)
            if len(history) > 10:
                history.pop(0)
        try:
            brace = content.index("{")
            data = json.loads(content[brace:content.rindex("}") + 1])
            state["final_command"].update({
                "command":   data.get("command", "—"),
                "reason":    data.get("reason", "—"),
                "path":      data.get("path", "—"),
                "left_arm":  data.get("left_arm_action", "—"),
                "right_arm": data.get("right_arm_action", "—"),
                "free_arm":  data.get("free_arm_action", "—"),
                "gait":      data.get("gait_action", "—"),
                "ts":        data.get("timestamp", _now_ms()),
            })
            state["safety"].update({"status": "—", "reason": "—", "ts": 0, "thinking": ""})
        except Exception:
            pass

    _push_update()


# ---------------------------------------------------------------------------
# Band listener (runs in asyncio thread)
# ---------------------------------------------------------------------------

async def _band_listener():
    agent_id = os.environ.get("DashboardID", "")
    api_key  = os.environ.get("DashboardBandAPI", "")
    if not agent_id or not api_key:
        print("[Dashboard] No DashboardID/DashboardBandAPI in .env — add them and restart.")
        print("[Dashboard] UI is still available at http://localhost:8000 (no live data until credentials added)")
        return

    link = BandLink(agent_id=agent_id, api_key=api_key, ws_url=WS_URL, rest_url=REST_URL)
    await link.connect()
    state["connected"] = True
    print("[Dashboard] Connected to Band.")

    try:
        resp = await link.rest.agent_api_chats.list_agent_chats(request_options=DEFAULT_REQUEST_OPTIONS)
        for room in (resp.data or []):
            await link.subscribe_room(room.id)
            print(f"[Dashboard] Monitoring room {room.id}")
    except Exception as e:
        print(f"[Dashboard] Could not list rooms: {e}")

    await link.subscribe_agent_rooms(agent_id)

    async for event in link:
        if isinstance(event, RoomAddedEvent) and event.room_id:
            await link.subscribe_room(event.room_id)
            print(f"[Dashboard] Joined room {event.room_id}")
        elif isinstance(event, MessageEvent) and event.payload:
            content = event.payload.content or ""
            sender  = event.payload.sender_handle or event.payload.sender_name or ""
            if content:
                _parse_message(content, sender)


def _start_band_thread():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_band_listener())


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI()


@app.get("/state")
def get_state():
    return state


@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    _listeners.append(q)
    async def generate():
        try:
            yield f"data: {json.dumps(state)}\n\n"
            while True:
                data = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {data}\n\n"
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _listeners:
                _listeners.remove(q)
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTML


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Baymax — Live Pipeline</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', system-ui, sans-serif; padding: 16px; min-height: 100vh; }

h1 { font-size: 1.5rem; letter-spacing: 3px; color: #58a6ff; }
.subtitle { font-size: 0.75rem; color: #8b949e; margin-top: 2px; }
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.badge.green { background: #1a4731; color: #3fb950; }
.badge.grey  { background: #21262d; color: #8b949e; }

/* Layout: left pipeline + right robot */
.main { display: grid; grid-template-columns: 1fr 340px; gap: 16px; align-items: start; }

/* ---- Pipeline (left) ---- */
.pipeline { display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; gap: 8px; }
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 10px;
  padding: 12px 14px; flex: 1;
  transition: border-color 0.4s, box-shadow 0.4s;
  min-width: 0;
}
.card.flash { border-color: #58a6ff; box-shadow: 0 0 14px #58a6ff55; }
.card.flash-red { border-color: #f85149; box-shadow: 0 0 14px #f8514955; }
.card.flash-green { border-color: #3fb950; box-shadow: 0 0 14px #3fb95055; }
.card-title { font-size: 0.65rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #8b949e; margin-bottom: 6px; }
.card-main { font-size: 0.95rem; font-weight: 700; color: #e6edf3; margin-bottom: 3px; }
.card-sub  { font-size: 0.72rem; color: #8b949e; margin-bottom: 2px; }
.card-thinking {
  font-size: 0.7rem; color: #58a6ff; margin-top: 6px;
  font-style: italic; min-height: 1.2em;
  border-left: 2px solid #21262d; padding-left: 6px;
  word-break: break-word;
  transition: color 0.3s;
}
.card-ts { font-size: 0.62rem; color: #484f58; margin-top: 4px; }

.hazard-NONE     { color: #3fb950; }
.hazard-LOW      { color: #d29922; }
.hazard-HIGH     { color: #f0883e; }
.hazard-CRITICAL { color: #f85149; }
.status-APPROVED { color: #3fb950; }
.status-VETOED   { color: #f85149; }

.arrow { text-align: center; color: #30363d; font-size: 1rem; line-height: 1; padding: 1px 0; }

/* Final command bar */
.final-bar {
  background: #0d2f5e; border: 1px solid #388bfd; border-radius: 10px;
  padding: 14px 18px; margin-top: 4px;
  transition: box-shadow 0.4s;
}
.final-bar.flash { box-shadow: 0 0 22px #388bfd88; }
.final-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #388bfd; margin-bottom: 6px; }
.final-command { font-size: 1.4rem; font-weight: 800; color: #58a6ff; margin-bottom: 4px; }
.final-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 8px; }
.fi { background: #0d1b2e; border-radius: 6px; padding: 6px 8px; }
.fi-label { font-size: 0.6rem; color: #388bfd; text-transform: uppercase; letter-spacing: 1px; }
.fi-val { font-size: 0.78rem; color: #e6edf3; font-weight: 600; margin-top: 1px; }

/* ---- Robot panel (right) ---- */
.robot-panel {
  background: #161b22; border: 1px solid #30363d; border-radius: 12px;
  padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 12px;
  position: sticky; top: 16px;
}
.robot-panel h2 { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 2px; color: #8b949e; }
#robot-svg { width: 100%; max-width: 280px; }

.cmd-label { font-size: 0.65rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
.cmd-value { font-size: 1.1rem; font-weight: 800; color: #58a6ff; text-align: center; }

.arm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; width: 100%; }
.arm-item { background: #0d1117; border-radius: 6px; padding: 6px 8px; text-align: center; }
.arm-lbl { font-size: 0.6rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
.arm-val { font-size: 0.78rem; color: #e6edf3; font-weight: 600; margin-top: 2px; }

/* ---- Activity log ---- */
.log-section { margin-top: 14px; }
.log-title { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #8b949e; margin-bottom: 6px; }
.log-box {
  background: #0d1117; border: 1px solid #21262d; border-radius: 8px;
  height: 160px; overflow-y: auto; padding: 8px;
  font-family: 'Courier New', monospace; font-size: 0.68rem;
}
.log-entry { padding: 2px 0; border-bottom: 1px solid #21262d; display: flex; gap: 8px; }
.log-entry:last-child { border-bottom: none; }
.log-time { color: #484f58; flex-shrink: 0; }
.log-sender { color: #d29922; flex-shrink: 0; min-width: 80px; }
.log-tag { flex-shrink: 0; min-width: 70px; }
.log-content { color: #8b949e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.tag-SCENE { color: #58a6ff; }
.tag-THREAT { color: #f0883e; }
.tag-TASK { color: #d2a8ff; }
.tag-READY { color: #7ee787; }
.tag-APPROVED { color: #3fb950; }
.tag-VETOED { color: #f85149; }
.tag-REFLEX, .tag-HALT { color: #f85149; font-weight: 700; }
.tag-REFLEX_EXECUTED { color: #f0883e; }
.tag-FINAL_COMMAND { color: #388bfd; font-weight: 700; }

.msg-count { font-size: 0.68rem; color: #484f58; text-align: right; margin-top: 4px; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>⚡ BAYMAX</h1>
    <div class="subtitle">Live Multi-Agent Pipeline — UC Berkeley AI Hackathon 2026</div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <div id="latency-box" style="text-align:right;display:none;">
      <div style="font-size:0.62rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;">End-to-End Latency</div>
      <div style="display:flex;align-items:baseline;gap:4px;">
        <span id="latency-value" style="font-size:1.8rem;font-weight:800;color:#58a6ff;font-family:monospace;">—</span>
        <span style="font-size:0.8rem;color:#8b949e;">ms</span>
      </div>
      <canvas id="latency-spark" width="120" height="24" style="display:block;margin-top:2px;"></canvas>
    </div>
    <span id="conn-badge" class="badge grey">Connecting…</span>
  </div>
</div>

<div class="main">

  <!-- LEFT: Pipeline -->
  <div class="pipeline">

    <!-- Row 1: Vision + Threat -->
    <div class="row">
      <div class="card" id="card-vision">
        <div class="card-title">👁 Vision Agent</div>
        <div class="card-main" id="v-hazard">—</div>
        <div class="card-sub" id="v-summary">Waiting for scene…</div>
        <div class="card-sub" id="v-terrain"></div>
        <div class="card-thinking" id="v-thinking"></div>
        <div class="card-ts" id="v-ts"></div>
      </div>
      <div class="card" id="card-threat">
        <div class="card-title">⚠️ Threat Agent</div>
        <div class="card-main" id="t-level">—</div>
        <div class="card-sub" id="t-desc">—</div>
        <div class="card-thinking" id="t-thinking"></div>
        <div class="card-ts" id="t-ts"></div>
      </div>
    </div>

    <div class="arrow">↓</div>

    <!-- Row 2: Conductor -->
    <div class="row">
      <div class="card" id="card-conductor">
        <div class="card-title">🧠 Conductor (Prefrontal Cortex)</div>
        <div class="card-main" id="c-decision">—</div>
        <div class="card-sub" id="c-reason">—</div>
        <div class="card-thinking" id="c-thinking"></div>
        <div class="card-ts" id="c-ts"></div>
      </div>
    </div>

    <div class="arrow">↓  dispatches simultaneously  ↓</div>

    <!-- Row 3: Upper Left, Lower, Upper Right -->
    <div class="row">
      <div class="card" id="card-upperleft">
        <div class="card-title">💪 Upper Left</div>
        <div class="card-main" id="ul-arm">—</div>
        <div class="card-sub" id="ul-free"></div>
        <div class="card-thinking" id="ul-thinking"></div>
        <div class="card-ts" id="ul-ts"></div>
      </div>
      <div class="card" id="card-lower">
        <div class="card-title">🦵 Lower Body</div>
        <div class="card-main" id="lo-gait">—</div>
        <div class="card-sub" id="lo-pace"></div>
        <div class="card-thinking" id="lo-thinking"></div>
        <div class="card-ts" id="lo-ts"></div>
      </div>
      <div class="card" id="card-upperright">
        <div class="card-title">💪 Upper Right</div>
        <div class="card-main" id="ur-arm">—</div>
        <div class="card-sub" id="ur-free"></div>
        <div class="card-thinking" id="ur-thinking"></div>
        <div class="card-ts" id="ur-ts"></div>
      </div>
    </div>

    <div class="arrow">↓  safety review  ↓</div>

    <!-- Row 4: Safety + Spine -->
    <div class="row">
      <div class="card" id="card-safety">
        <div class="card-title">🛡 Safety Agent</div>
        <div class="card-main" id="s-status">—</div>
        <div class="card-sub" id="s-reason">—</div>
        <div class="card-thinking" id="s-thinking"></div>
        <div class="card-ts" id="s-ts"></div>
      </div>
      <div class="card" id="card-spine">
        <div class="card-title">⚡ Spine (Reflex)</div>
        <div class="card-main" id="sp-status">Standby</div>
        <div class="card-thinking" id="sp-thinking"></div>
        <div class="card-ts" id="sp-ts"></div>
      </div>
    </div>

    <div class="arrow">↓</div>

    <!-- Final Command -->
    <div class="final-bar" id="card-final">
      <div class="final-label">🤖 Final Command → Robot</div>
      <div class="final-command" id="f-command">Waiting…</div>
      <div class="card-sub" id="f-reason" style="color:#8b949e;font-size:0.75rem;">—</div>
      <div class="final-grid">
        <div class="fi"><div class="fi-label">Left Arm</div><div class="fi-val" id="f-left">—</div></div>
        <div class="fi"><div class="fi-label">Right Arm</div><div class="fi-val" id="f-right">—</div></div>
        <div class="fi"><div class="fi-label">Free Arm</div><div class="fi-val" id="f-free">—</div></div>
        <div class="fi"><div class="fi-label">Gait</div><div class="fi-val" id="f-gait">—</div></div>
      </div>
      <div class="card-ts" id="f-ts" style="margin-top:8px;"></div>
    </div>

    <!-- Activity Log -->
    <div class="log-section">
      <div class="log-title">Band Message Log</div>
      <div class="log-box" id="log-box"></div>
      <div class="msg-count" id="msg-count">messages seen: 0</div>
    </div>

  </div>

  <!-- RIGHT: Robot Visualization -->
  <div class="robot-panel">
    <h2>Robot State</h2>

    <svg id="robot-svg" viewBox="0 0 200 320" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <!-- Body glow bg -->
      <ellipse cx="100" cy="160" rx="28" ry="55" fill="#0d2f5e" opacity="0.5"/>

      <!-- Torso -->
      <rect x="72" y="110" width="56" height="70" rx="10" fill="#1c2a3e" stroke="#388bfd" stroke-width="1.5"/>
      <!-- Chest light -->
      <circle cx="100" cy="138" r="8" fill="#0d2f5e" stroke="#58a6ff" stroke-width="1.5" filter="url(#glow)" id="chest-light"/>

      <!-- Head -->
      <rect x="80" y="76" width="40" height="34" rx="8" fill="#1c2a3e" stroke="#388bfd" stroke-width="1.5"/>
      <!-- Eyes -->
      <circle cx="91" cy="91" r="4" fill="#58a6ff" filter="url(#glow)" id="eye-l"/>
      <circle cx="109" cy="91" r="4" fill="#58a6ff" filter="url(#glow)" id="eye-r"/>
      <!-- Neck -->
      <rect x="94" y="108" width="12" height="5" rx="2" fill="#21262d"/>

      <!-- LEFT ARM group (rotates at shoulder = 72,120) -->
      <g id="arm-left" transform="rotate(0, 72, 125)">
        <!-- upper arm -->
        <rect x="48" y="118" width="24" height="12" rx="5" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.2"/>
        <!-- elbow joint -->
        <circle cx="50" cy="124" r="4" fill="#21262d" stroke="#388bfd" stroke-width="1"/>
        <!-- forearm -->
        <rect x="26" y="120" width="24" height="8" rx="4" fill="#1c2a3e" stroke="#388bfd" stroke-width="1"/>
        <!-- hand -->
        <circle cx="24" cy="124" r="5" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.2" filter="url(#glow)"/>
      </g>

      <!-- RIGHT ARM group (rotates at shoulder = 128,120) -->
      <g id="arm-right" transform="rotate(0, 128, 125)">
        <rect x="128" y="118" width="24" height="12" rx="5" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.2"/>
        <circle cx="150" cy="124" r="4" fill="#21262d" stroke="#388bfd" stroke-width="1"/>
        <rect x="150" y="120" width="24" height="8" rx="4" fill="#1c2a3e" stroke="#388bfd" stroke-width="1"/>
        <circle cx="176" cy="124" r="5" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.2" filter="url(#glow)"/>
      </g>

      <!-- Hips -->
      <rect x="76" y="178" width="48" height="12" rx="5" fill="#21262d" stroke="#30363d" stroke-width="1"/>

      <!-- LEFT LEG -->
      <g id="leg-left">
        <rect x="78" y="190" width="20" height="40" rx="6" fill="#1c2a3e" stroke="#30363d" stroke-width="1"/>
        <rect x="78" y="228" width="20" height="32" rx="5" fill="#1c2a3e" stroke="#30363d" stroke-width="1"/>
        <rect x="73" y="256" width="28" height="8" rx="4" fill="#21262d" stroke="#30363d" stroke-width="1"/>
      </g>

      <!-- RIGHT LEG -->
      <g id="leg-right">
        <rect x="102" y="190" width="20" height="40" rx="6" fill="#1c2a3e" stroke="#30363d" stroke-width="1"/>
        <rect x="102" y="228" width="20" height="32" rx="5" fill="#1c2a3e" stroke="#30363d" stroke-width="1"/>
        <rect x="99" y="256" width="28" height="8" rx="4" fill="#21262d" stroke="#30363d" stroke-width="1"/>
      </g>

      <!-- Status text -->
      <text id="robot-status-text" x="100" y="292" text-anchor="middle" font-size="10" fill="#8b949e" font-family="monospace">STANDBY</text>
    </svg>

    <div style="width:100%;text-align:center;">
      <div class="cmd-label">Command</div>
      <div class="cmd-value" id="r-command">—</div>
    </div>

    <div class="arm-grid">
      <div class="arm-item">
        <div class="arm-lbl">Left Arm</div>
        <div class="arm-val" id="r-left">—</div>
      </div>
      <div class="arm-item">
        <div class="arm-lbl">Right Arm</div>
        <div class="arm-val" id="r-right">—</div>
      </div>
      <div class="arm-item">
        <div class="arm-lbl">Free Arm</div>
        <div class="arm-val" id="r-free">—</div>
      </div>
      <div class="arm-item">
        <div class="arm-lbl">Gait</div>
        <div class="arm-val" id="r-gait">—</div>
      </div>
    </div>
  </div>

</div>

<script>
// ---- Arm rotation angles per action (degrees at shoulder pivot) ----
// Left arm: positive = arm goes up, negative = arm goes down
// For left arm group pivoting at (72,125): rotate(deg, 72, 125)
// For right arm group pivoting at (128,125): rotate(deg, 128, 125)
const ARM_ANGLES = {
  "HOLD_STEADY":        { l: 0,    r: 0 },
  "GENTLE_LEFT_PULL":   { l: -40,  r: -15 },
  "GENTLE_RIGHT_PULL":  { l: -15,  r: 40 },
  "FORWARD_PUSH":       { l: -70,  r: 70 },
  "RELEASE":            { l: 20,   r: -20 },
  "HALT_EXTEND":        { l: -90,  r: 90 },
};

const LEG_ANIM = {
  "WALK_NORMAL": true,
  "WALK_SLOW": true,
  "STEP_HIGH": true,
  "STEP_DOWN": true,
};

// Smooth arm lerp state
let currentLAngle = 0, currentRAngle = 0;
let targetLAngle = 0, targetRAngle = 0;
let legPhase = 0, legAnimating = false;
let lastTs = 0;

function lerp(a, b, t) { return a + (b - a) * t; }

function animLoop(ts) {
  const dt = Math.min((ts - lastTs) / 1000, 0.1);
  lastTs = ts;
  const speed = 6;
  currentLAngle = lerp(currentLAngle, targetLAngle, Math.min(speed * dt, 1));
  currentRAngle = lerp(currentRAngle, targetRAngle, Math.min(speed * dt, 1));

  document.getElementById('arm-left').setAttribute('transform', `rotate(${currentLAngle}, 72, 125)`);
  document.getElementById('arm-right').setAttribute('transform', `rotate(${currentRAngle}, 128, 125)`);

  if (legAnimating) {
    legPhase += dt * 3;
    const lStep = Math.sin(legPhase) * 10;
    const rStep = Math.sin(legPhase + Math.PI) * 10;
    document.getElementById('leg-left').setAttribute('transform', `translate(0, ${lStep})`);
    document.getElementById('leg-right').setAttribute('transform', `translate(0, ${rStep})`);
  } else {
    document.getElementById('leg-left').setAttribute('transform', 'translate(0,0)');
    document.getElementById('leg-right').setAttribute('transform', 'translate(0,0)');
  }

  requestAnimationFrame(animLoop);
}
requestAnimationFrame(animLoop);

function setArmTargets(leftAction, rightAction, freeAction) {
  // If HALT_EXTEND override both arms
  if (freeAction === 'HALT_EXTEND') {
    targetLAngle = -90;
    targetRAngle = 90;
    return;
  }
  const la = ARM_ANGLES[leftAction] || ARM_ANGLES['HOLD_STEADY'];
  const ra = ARM_ANGLES[rightAction] || ARM_ANGLES['HOLD_STEADY'];
  // Left arm uses left component, right arm uses right component
  targetLAngle = la.l;
  targetRAngle = ra.r;
}

function setChestColor(command) {
  const light = document.getElementById('chest-light');
  const eyeL = document.getElementById('eye-l');
  const eyeR = document.getElementById('eye-r');
  const colors = {
    'EMERGENCY_STOP': '#f85149',
    'STOP':           '#d29922',
    'SLOW_DOWN':      '#d2a8ff',
    'MOVE_FORWARD':   '#3fb950',
    'GUIDE_LEFT':     '#58a6ff',
    'GUIDE_RIGHT':    '#58a6ff',
  };
  const c = colors[command] || '#58a6ff';
  light.setAttribute('fill', c + '33');
  light.setAttribute('stroke', c);
  eyeL.setAttribute('fill', c);
  eyeR.setAttribute('fill', c);
}

// ---- State update ----
function ts(ms) {
  if (!ms) return '';
  return new Date(ms).toLocaleTimeString();
}
function flash(id, cls) {
  cls = cls || 'flash';
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add(cls);
  setTimeout(() => { el.classList.remove('flash'); el.classList.remove('flash-red'); el.classList.remove('flash-green'); }, 900);
}
function hazardClass(h) { return 'card-main hazard-' + (h || 'NONE'); }

function update(s) {
  // Vision
  const v = s.vision;
  document.getElementById('v-hazard').textContent = v.hazard || 'NONE';
  document.getElementById('v-hazard').className = hazardClass(v.hazard);
  document.getElementById('v-summary').textContent = v.summary || '—';
  document.getElementById('v-terrain').textContent = v.terrain ? 'Terrain: ' + v.terrain : '';
  document.getElementById('v-thinking').textContent = v.thinking || '';
  document.getElementById('v-ts').textContent = v.ts ? ts(v.ts) + (v.latency_ms ? ' · ' + v.latency_ms + 'ms' : '') : '';
  if (v.ts) flash('card-vision');

  // Threat
  const t = s.threat;
  document.getElementById('t-level').textContent = t.level || '—';
  document.getElementById('t-level').className = hazardClass(t.level);
  document.getElementById('t-desc').textContent = t.description || '—';
  document.getElementById('t-thinking').textContent = t.thinking || '';
  document.getElementById('t-ts').textContent = t.ts ? ts(t.ts) : '';
  if (t.ts) flash('card-threat');

  // Conductor
  const c = s.conductor;
  document.getElementById('c-decision').textContent = c.decision || '—';
  document.getElementById('c-reason').textContent = c.reason || '—';
  document.getElementById('c-thinking').textContent = c.thinking || '';
  document.getElementById('c-ts').textContent = c.ts ? ts(c.ts) : '';
  if (c.ts) flash('card-conductor');

  // Upper Left
  const ul = s.upper_left;
  document.getElementById('ul-arm').textContent = ul.arm_action || '—';
  document.getElementById('ul-free').textContent = ul.free_arm ? 'Free: ' + ul.free_arm : '';
  document.getElementById('ul-thinking').textContent = ul.thinking || '';
  document.getElementById('ul-ts').textContent = ul.ts ? ts(ul.ts) : '';
  if (ul.ts) flash('card-upperleft');

  // Upper Right
  const ur = s.upper_right;
  document.getElementById('ur-arm').textContent = ur.arm_action || '—';
  document.getElementById('ur-free').textContent = ur.free_arm ? 'Free: ' + ur.free_arm : '';
  document.getElementById('ur-thinking').textContent = ur.thinking || '';
  document.getElementById('ur-ts').textContent = ur.ts ? ts(ur.ts) : '';
  if (ur.ts) flash('card-upperright');

  // Lower
  const lo = s.lower;
  document.getElementById('lo-gait').textContent = lo.gait_action || '—';
  document.getElementById('lo-pace').textContent = lo.pace_ms ? lo.pace_ms + 'ms pace' : '';
  document.getElementById('lo-thinking').textContent = lo.thinking || '';
  document.getElementById('lo-ts').textContent = lo.ts ? ts(lo.ts) : '';
  if (lo.ts) flash('card-lower');
  legAnimating = !!(lo.gait_action && lo.gait_action !== '—' && lo.gait_action !== 'HALT' && lo.gait_action !== 'PAUSE');

  // Safety
  const sa = s.safety;
  document.getElementById('s-status').textContent = sa.status || '—';
  document.getElementById('s-status').className = 'card-main status-' + (sa.status || '');
  document.getElementById('s-reason').textContent = sa.reason || '—';
  document.getElementById('s-thinking').textContent = sa.thinking || '';
  document.getElementById('s-ts').textContent = sa.ts ? ts(sa.ts) : '';
  if (sa.ts) {
    flash('card-safety', sa.status === 'VETOED' ? 'flash-red' : 'flash-green');
  }

  // Spine
  const sp = s.spine;
  document.getElementById('sp-status').textContent = sp.status || 'Standby';
  document.getElementById('sp-thinking').textContent = sp.thinking || '';
  document.getElementById('sp-ts').textContent = sp.ts ? ts(sp.ts) : '';
  if (sp.ts) flash('card-spine', 'flash-red');

  // Final command
  const f = s.final_command;
  document.getElementById('f-command').textContent = f.command || 'Waiting…';
  document.getElementById('f-reason').textContent = f.reason || '—';
  document.getElementById('f-left').textContent = f.left_arm || '—';
  document.getElementById('f-right').textContent = f.right_arm || '—';
  document.getElementById('f-free').textContent = f.free_arm || '—';
  document.getElementById('f-gait').textContent = f.gait || '—';
  document.getElementById('f-ts').textContent = f.ts ? 'Sent ' + ts(f.ts) + ' · path: ' + (f.path || '—') : '';
  if (f.ts) flash('card-final');

  // Robot panel
  document.getElementById('r-command').textContent = f.command || '—';
  document.getElementById('r-left').textContent = f.left_arm || '—';
  document.getElementById('r-right').textContent = f.right_arm || '—';
  document.getElementById('r-free').textContent = f.free_arm || '—';
  document.getElementById('r-gait').textContent = f.gait || '—';
  document.getElementById('robot-status-text').textContent = f.command || 'STANDBY';
  if (f.command && f.command !== '—') {
    setArmTargets(f.left_arm, f.right_arm, f.free_arm);
    setChestColor(f.command);
  }

  // Log
  const box = document.getElementById('log-box');
  const atBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 10;
  box.innerHTML = (s.log || []).slice().reverse().map(e =>
    `<div class="log-entry">
      <span class="log-time">${new Date(e.ts).toLocaleTimeString()}</span>
      <span class="log-sender">${(e.sender||'').split('/').pop()}</span>
      <span class="log-tag tag-${e.tag}">[${e.tag}]</span>
      <span class="log-content">${e.content.replace(/</g,'&lt;')}</span>
    </div>`
  ).join('');
  if (atBottom) box.scrollTop = 0; // newest at top since we reversed

  document.getElementById('msg-count').textContent = 'messages seen: ' + (s.message_count || 0);

  // Latency display
  if (s.pipeline_latency_ms != null) {
    const box = document.getElementById('latency-box');
    box.style.display = 'block';
    const val = document.getElementById('latency-value');
    val.textContent = s.pipeline_latency_ms;
    // color-code: green <3s, yellow <6s, red >=6s
    val.style.color = s.pipeline_latency_ms < 3000 ? '#3fb950' : s.pipeline_latency_ms < 6000 ? '#d29922' : '#f85149';
    drawSparkline(s.latency_history || []);
  }

  const badge = document.getElementById('conn-badge');
  if (s.connected) { badge.textContent = '● Live'; badge.className = 'badge green'; }
  else { badge.textContent = '○ Waiting for Band credentials'; badge.className = 'badge grey'; }
}

function drawSparkline(history) {
  const canvas = document.getElementById('latency-spark');
  if (!canvas || history.length < 2) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const max = Math.max(...history, 1);
  const w = canvas.width / (history.length - 1);
  ctx.beginPath();
  ctx.strokeStyle = '#58a6ff88';
  ctx.lineWidth = 1.5;
  history.forEach((v, i) => {
    const x = i * w;
    const y = canvas.height - (v / max) * (canvas.height - 2) - 1;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
  // dot at latest
  const lx = (history.length - 1) * w;
  const ly = canvas.height - (history[history.length-1] / max) * (canvas.height - 2) - 1;
  ctx.beginPath();
  ctx.arc(lx, ly, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = '#58a6ff';
  ctx.fill();
}

const es = new EventSource('/events');
es.onmessage = e => { try { update(JSON.parse(e.data)); } catch(_) {} };
es.onerror = () => {
  document.getElementById('conn-badge').textContent = '✕ Disconnected';
  document.getElementById('conn-badge').className = 'badge grey';
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    t = threading.Thread(target=_start_band_thread, daemon=True)
    t.start()
    print("[Dashboard] Starting at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
