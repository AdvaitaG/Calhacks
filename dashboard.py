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

_AGENT_DEFAULTS = {
    "vision":      {"summary": "—", "hazard": "NONE", "obstacles": [], "terrain": "—", "latency_ms": 0},
    "threat":      {"level": "NONE", "description": "—"},
    "conductor":   {"decision": "—", "reason": "—"},
    "upper_left":  {"arm_action": "—", "free_arm": "—"},
    "upper_right": {"arm_action": "—", "free_arm": "—"},
    "lower":       {"gait_action": "—", "pace_ms": 0},
    "safety":      {"status": "—", "reason": "—"},
    "spine":       {"status": "Standby"},
}

state = {
    **{k: {**v, "ts": 0, "thinking": "", "active": False, "last_tag": ""} for k, v in _AGENT_DEFAULTS.items()},
    "final_command": {"command": "—", "reason": "—", "path": "—", "left_arm": "—", "right_arm": "—", "free_arm": "—", "gait": "—", "ts": 0},
    "pipeline_latency_ms": None,
    "latency_history": [],
    "active_path": None,
    "message_count": 0,
    "connected": False,
    "log": [],
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


def _activate(agent: str, tag: str, thinking: str = ""):
    """Mark an agent as recently active for overlay pulse + link animation."""
    now = _now_ms()
    entry = state[agent]
    entry["ts"] = now
    entry["active"] = True
    entry["active_until"] = now + 2000
    entry["last_tag"] = tag
    if thinking:
        entry["thinking"] = thinking[:200]


def _thinking(content: str, max_len: int = 200) -> str:
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
        _scene_recv_ms = _now_ms()
        _log(sender, content, "SCENE")
        try:
            data = json.loads(content[7:].strip())
            summary = data.get("scene_summary", "—")
            state["vision"].update({
                "summary":    summary,
                "hazard":     data.get("hazard_level", "NONE"),
                "obstacles":  data.get("obstacles", []),
                "terrain":    data.get("terrain", "—"),
                "latency_ms": data.get("latency_ms", 0),
            })
            _activate("vision", "SCENE", summary)
        except Exception:
            _activate("vision", "SCENE", content[7:200])

    elif "[THREAT]" in content:
        _log(sender, content, "THREAT")
        try:
            start = content.index("[THREAT]") + 8
            data = json.loads(content[start:].strip())
            desc = data.get("description", "—")
            state["threat"].update({
                "level":       data.get("threat_level", "NONE"),
                "description": desc,
            })
            _activate("threat", "THREAT", desc)
            if data.get("fire_reflex"):
                state["active_path"] = "REFLEX"
        except Exception:
            state["threat"].update({"level": "UNKNOWN", "description": content[:80]})
            _activate("threat", "THREAT", content[:200])

    elif "[TASK]" in content:
        _log(sender, content, "TASK")
        state["active_path"] = "CORTICAL"
        try:
            start = content.index("[TASK]") + 6
            data = json.loads(content[start:].strip())
            reason = data.get("reason", "—")
            state["conductor"].update({
                "decision": data.get("decision", "—"),
                "reason":   reason,
            })
            _activate("conductor", "TASK", reason)
        except Exception:
            state["conductor"].update({"decision": "dispatched", "reason": content[:80]})
            _activate("conductor", "TASK", content[:200])

    elif "[READY]" in content:
        _log(sender, content, "READY")
        try:
            start = content.index("[READY]") + 7
            data = json.loads(content[start:].strip())
            thinking = _thinking(content)
            if "upperleft" in sender_lower or "upper_left" in sender_lower:
                state["upper_left"].update({
                    "arm_action": data.get("arm_action", "—"),
                    "free_arm":   data.get("free_arm_action", "—"),
                })
                _activate("upper_left", "READY", thinking)
            elif "upperright" in sender_lower or "upper_right" in sender_lower:
                state["upper_right"].update({
                    "arm_action": data.get("arm_action", "—"),
                    "free_arm":   data.get("free_arm_action", "—"),
                })
                _activate("upper_right", "READY", thinking)
            elif "lower" in sender_lower:
                state["lower"].update({
                    "gait_action": data.get("gait_action", "—"),
                    "pace_ms":     data.get("pace_ms", 0),
                })
                _activate("lower", "READY", thinking)
        except Exception:
            pass

    elif "[APPROVED]" in content:
        _log(sender, content, "APPROVED")
        state["safety"].update({"status": "APPROVED", "reason": "Command approved"})
        _activate("safety", "APPROVED", "Command approved ✓")

    elif "[VETOED]" in content:
        _log(sender, content, "VETOED")
        try:
            start = content.index("[VETOED]") + 8
            data = json.loads(content[start:].strip())
            reason = data.get("reason", "—")
            state["safety"].update({"status": "VETOED", "reason": reason})
            _activate("safety", "VETOED", reason)
        except Exception:
            state["safety"].update({"status": "VETOED", "reason": "—"})
            _activate("safety", "VETOED", "")

    elif "[REFLEX]" in content or "[HALT]" in content:
        tag = "REFLEX" if "[REFLEX]" in content else "HALT"
        _log(sender, content, tag)
        state["active_path"] = "REFLEX"
        state["spine"].update({"status": "REFLEX FIRED"})
        _activate("spine", tag, "Emergency reflex triggered!")
        state["safety"].update({"status": "—", "reason": "—", "ts": 0, "thinking": "", "active": False, "last_tag": ""})

    elif "[REFLEX_EXECUTED]" in content:
        _log(sender, content, "REFLEX_EXECUTED")
        state["spine"].update({"status": "REFLEX EXECUTED"})
        _activate("spine", "REFLEX_EXECUTED", "Reflex command sent to robot")

    elif "FINAL_COMMAND" in content:
        _log(sender, content, "FINAL_COMMAND")
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
            path = data.get("path", "—")
            state["active_path"] = path if path in ("CORTICAL", "REFLEX") else state.get("active_path")
            state["final_command"].update({
                "command":   data.get("command", "—"),
                "reason":    data.get("reason", "—"),
                "path":      path,
                "left_arm":  data.get("left_arm_action", "—"),
                "right_arm": data.get("right_arm_action", "—"),
                "free_arm":  data.get("free_arm_action", "—"),
                "gait":      data.get("gait_action", "—"),
                "ts":        data.get("timestamp", _now_ms()),
            })
            state["safety"].update({"status": "—", "reason": "—", "ts": 0, "thinking": "", "active": False, "last_tag": ""})
        except Exception:
            pass

    # Expire active flags
    now = _now_ms()
    for agent in _AGENT_DEFAULTS:
        until = state[agent].get("active_until", 0)
        if until and now > until:
            state[agent]["active"] = False

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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Baymax — Nervous System</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1117; color: #e6edf3;
  font-family: 'Segoe UI', system-ui, sans-serif;
  min-height: 100vh; display: flex; flex-direction: column;
  overflow-x: hidden;
}
h1 { font-size: 1.4rem; letter-spacing: 3px; color: #58a6ff; }
.subtitle { font-size: 0.72rem; color: #8b949e; margin-top: 2px; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-bottom: 1px solid #21262d; flex-shrink: 0;
}
.badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.badge.green { background: #1a4731; color: #3fb950; }
.badge.grey  { background: #21262d; color: #8b949e; }
.path-badge { font-size: 0.65rem; padding: 3px 10px; border-radius: 8px; font-weight: 700; letter-spacing: 1px; }
.path-CORTICAL { background: #0d2f5e; color: #58a6ff; }
.path-REFLEX { background: #3d1214; color: #f85149; }

/* ---- Robot stage (hero) ---- */
.stage-wrap { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.robot-stage {
  position: relative; flex: 1; min-height: 480px;
  display: flex; align-items: center; justify-content: center;
  padding: 8px 16px;
}
#robot-svg, #link-layer {
  position: absolute; width: min(65vw, 420px); height: auto;
  max-height: calc(100vh - 200px);
}
#link-layer { pointer-events: none; z-index: 2; }
#robot-svg { z-index: 1; }

.zone-glow { transition: filter 0.4s, opacity 0.4s; }
.zone-glow.active { filter: drop-shadow(0 0 8px var(--glow-color, #58a6ff)); opacity: 1; }
#zone-head { --glow-color: #58a6ff; }
#zone-neck { --glow-color: #f0883e; }
#zone-torso { --glow-color: #d2a8ff; }
#zone-spine { --glow-color: #f85149; }
#zone-arm-left { --glow-color: #7ee787; }
#zone-arm-right { --glow-color: #7ee787; }
#zone-lower { --glow-color: #79c0ff; }

.link-line { fill: none; stroke-width: 1.5; stroke: #30363d; opacity: 0.35; }
.link-line.peer { stroke-dasharray: 4 4; }
.link-line.pulse { animation: linkPulse 0.7s ease-out; }
@keyframes linkPulse {
  0% { stroke-opacity: 1; stroke-width: 3; }
  100% { stroke-opacity: 0.35; stroke-width: 1.5; }
}

/* ---- Agent overlay panels ---- */
.agent-panel {
  position: absolute; z-index: 10;
  width: 168px; padding: 8px 10px;
  background: rgba(22, 27, 34, 0.88);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid #30363d; border-radius: 8px;
  border-left: 3px solid var(--agent-color, #58a6ff);
  transition: border-color 0.3s, box-shadow 0.3s;
  pointer-events: none;
}
.agent-panel.active {
  box-shadow: 0 0 16px var(--agent-color, #58a6ff55);
  border-color: var(--agent-color, #58a6ff);
}
.agent-panel.flash-red { border-color: #f85149; box-shadow: 0 0 16px #f8514955; }
.agent-panel.flash-green { border-color: #3fb950; box-shadow: 0 0 16px #3fb95055; }
.panel-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.panel-dot { width: 6px; height: 6px; border-radius: 50%; background: #484f58; flex-shrink: 0; }
.panel-dot.live { background: #3fb950; animation: dotPulse 1.2s infinite; }
@keyframes dotPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.panel-name { font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #e6edf3; }
.panel-region { font-size: 0.55rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
.panel-action { font-size: 0.78rem; font-weight: 700; color: #e6edf3; margin: 3px 0; word-break: break-word; }
.panel-sub { font-size: 0.65rem; color: #8b949e; margin-bottom: 2px; }
.panel-thinking {
  font-size: 0.65rem; color: #58a6ff; font-style: italic;
  margin-top: 4px; line-height: 1.35; word-break: break-word;
  max-height: 3.2em; overflow: hidden;
}
.panel-ts { font-size: 0.55rem; color: #484f58; margin-top: 3px; }

.panel-vision { --agent-color: #58a6ff; }
.panel-threat { --agent-color: #f0883e; }
.panel-conductor { --agent-color: #d2a8ff; }
.panel-upper_left { --agent-color: #7ee787; }
.panel-upper_right { --agent-color: #7ee787; }
.panel-lower { --agent-color: #79c0ff; }
.panel-safety { --agent-color: #3fb950; }
.panel-safety.vetoed { --agent-color: #f85149; }
.panel-spine { --agent-color: #f85149; }

.hazard-NONE { color: #3fb950; }
.hazard-LOW { color: #d29922; }
.hazard-HIGH { color: #f0883e; }
.hazard-CRITICAL { color: #f85149; }
.status-APPROVED { color: #3fb950; }
.status-VETOED { color: #f85149; }

/* ---- Final command strip ---- */
.cmd-strip {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  z-index: 15; background: rgba(13, 47, 94, 0.92); border: 1px solid #388bfd;
  border-radius: 10px; padding: 8px 20px; text-align: center;
  backdrop-filter: blur(6px); min-width: 280px;
  transition: box-shadow 0.4s;
}
.cmd-strip.flash { box-shadow: 0 0 22px #388bfd88; }
.cmd-strip-label { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 1px; color: #388bfd; }
.cmd-strip-main { font-size: 1.1rem; font-weight: 800; color: #58a6ff; }
.cmd-strip-sub { font-size: 0.65rem; color: #8b949e; margin-top: 2px; }
.cmd-strip-grid { display: flex; gap: 12px; justify-content: center; margin-top: 4px; flex-wrap: wrap; }
.cmd-strip-item { font-size: 0.6rem; color: #8b949e; }
.cmd-strip-item span { color: #e6edf3; font-weight: 600; }

/* ---- Log drawer ---- */
.log-drawer {
  border-top: 1px solid #21262d; background: #0d1117; flex-shrink: 0;
}
.log-toggle {
  width: 100%; padding: 8px 20px; background: #161b22; border: none;
  color: #8b949e; font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; cursor: pointer; text-align: left;
  display: flex; justify-content: space-between; align-items: center;
}
.log-toggle:hover { color: #e6edf3; }
.log-body { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
.log-body.open { max-height: 180px; }
.log-box {
  height: 140px; overflow-y: auto; padding: 8px 20px;
  font-family: 'Courier New', monospace; font-size: 0.68rem;
}
.log-entry { padding: 2px 0; border-bottom: 1px solid #21262d; display: flex; gap: 8px; }
.log-entry:last-child { border-bottom: none; }
.log-time { color: #484f58; flex-shrink: 0; }
.log-sender { color: #d29922; flex-shrink: 0; min-width: 70px; }
.log-tag { flex-shrink: 0; min-width: 65px; }
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
.log-footer { padding: 4px 20px 8px; font-size: 0.65rem; color: #484f58; text-align: right; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>⚡ BAYMAX</h1>
    <div class="subtitle">Nervous System fMRI — UC Berkeley AI Hackathon 2026</div>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <span id="path-badge" class="path-badge" style="display:none;"></span>
    <div id="latency-box" style="text-align:right;display:none;">
      <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;">E2E Latency</div>
      <div style="display:flex;align-items:baseline;gap:4px;justify-content:flex-end;">
        <span id="latency-value" style="font-size:1.4rem;font-weight:800;color:#58a6ff;font-family:monospace;">—</span>
        <span style="font-size:0.75rem;color:#8b949e;">ms</span>
      </div>
      <canvas id="latency-spark" width="100" height="20" style="display:block;margin-top:2px;"></canvas>
    </div>
    <span id="conn-badge" class="badge grey">Connecting…</span>
  </div>
</div>

<div class="stage-wrap">
  <div class="robot-stage" id="robot-stage">

    <svg id="robot-svg" viewBox="0 0 400 600" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#1c2a3e"/><stop offset="100%" stop-color="#0f1923"/>
        </linearGradient>
      </defs>
      <ellipse cx="200" cy="300" rx="90" ry="160" fill="#0d2f5e" opacity="0.25"/>

      <!-- Spine (back channel) -->
      <g id="zone-spine" class="zone-glow">
        <line x1="228" y1="130" x2="228" y2="400" stroke="#f85149" stroke-width="3" opacity="0.25" stroke-linecap="round"/>
        <line x1="228" y1="130" x2="228" y2="400" stroke="#f85149" stroke-width="1" opacity="0.5" stroke-dasharray="6 8" id="spine-channel"/>
      </g>

      <!-- Lower body / legs -->
      <g id="zone-lower" class="zone-glow">
        <rect x="155" y="340" width="90" height="28" rx="8" fill="#21262d" stroke="#30363d" stroke-width="1.2"/>
        <g id="leg-left">
          <rect x="158" y="368" width="32" height="72" rx="10" fill="url(#bodyGrad)" stroke="#30363d" stroke-width="1.2"/>
          <rect x="158" y="438" width="32" height="64" rx="8" fill="url(#bodyGrad)" stroke="#30363d" stroke-width="1.2"/>
          <rect x="150" y="498" width="48" height="14" rx="6" fill="#21262d" stroke="#30363d"/>
        </g>
        <g id="leg-right">
          <rect x="210" y="368" width="32" height="72" rx="10" fill="url(#bodyGrad)" stroke="#30363d" stroke-width="1.2"/>
          <rect x="210" y="438" width="32" height="64" rx="8" fill="url(#bodyGrad)" stroke="#30363d" stroke-width="1.2"/>
          <rect x="202" y="498" width="48" height="14" rx="6" fill="#21262d" stroke="#30363d"/>
        </g>
      </g>

      <!-- Torso -->
      <g id="zone-torso" class="zone-glow">
        <rect x="140" y="200" width="120" height="145" rx="16" fill="url(#bodyGrad)" stroke="#388bfd" stroke-width="1.8"/>
        <circle cx="200" cy="260" r="18" fill="#0d2f5e" stroke="#58a6ff" stroke-width="2" filter="url(#glow)" id="chest-light"/>
        <circle cx="200" cy="260" r="28" fill="none" stroke="#d2a8ff" stroke-width="1" opacity="0.4" id="conductor-ring"/>
      </g>

      <!-- Left arm -->
      <g id="zone-arm-left" class="zone-glow">
        <g id="arm-left" transform="rotate(0, 120, 220)">
          <rect x="55" y="212" width="65" height="18" rx="8" fill="url(#bodyGrad)" stroke="#58a6ff" stroke-width="1.4"/>
          <circle cx="58" cy="221" r="7" fill="#21262d" stroke="#388bfd"/>
          <rect x="18" y="216" width="42" height="12" rx="6" fill="url(#bodyGrad)" stroke="#388bfd"/>
          <circle cx="14" cy="222" r="9" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.4" filter="url(#glow)"/>
        </g>
      </g>

      <!-- Right arm -->
      <g id="zone-arm-right" class="zone-glow">
        <g id="arm-right" transform="rotate(0, 280, 220)">
          <rect x="280" y="212" width="65" height="18" rx="8" fill="url(#bodyGrad)" stroke="#58a6ff" stroke-width="1.4"/>
          <circle cx="342" cy="221" r="7" fill="#21262d" stroke="#388bfd"/>
          <rect x="340" y="216" width="42" height="12" rx="6" fill="url(#bodyGrad)" stroke="#388bfd"/>
          <circle cx="386" cy="222" r="9" fill="#1c2a3e" stroke="#58a6ff" stroke-width="1.4" filter="url(#glow)"/>
        </g>
      </g>

      <!-- Neck -->
      <g id="zone-neck" class="zone-glow">
        <rect x="182" y="168" width="36" height="34" rx="6" fill="#21262d" stroke="#f0883e" stroke-width="1.2" opacity="0.9"/>
      </g>

      <!-- Head -->
      <g id="zone-head" class="zone-glow">
        <rect x="155" y="55" width="90" height="78" rx="20" fill="url(#bodyGrad)" stroke="#388bfd" stroke-width="1.8"/>
        <rect x="168" y="78" width="64" height="12" rx="4" fill="#0d1117" stroke="#58a6ff" stroke-width="1" opacity="0.8"/>
        <circle cx="178" cy="84" r="3" fill="#58a6ff" filter="url(#glow)" id="eye-l"/>
        <circle cx="222" cy="84" r="3" fill="#58a6ff" filter="url(#glow)" id="eye-r"/>
      </g>

      <text id="robot-status-text" x="200" y="545" text-anchor="middle" font-size="11" fill="#8b949e" font-family="monospace">STANDBY</text>
    </svg>

    <svg id="link-layer" viewBox="0 0 400 600" xmlns="http://www.w3.org/2000/svg"></svg>

    <!-- Agent panels -->
    <div class="agent-panel panel-vision" id="panel-vision" data-agent="vision">
      <div class="panel-header"><span class="panel-dot" id="dot-vision"></span><span class="panel-name">Vision</span></div>
      <div class="panel-region">Sensory Cortex · Head</div>
      <div class="panel-action hazard-NONE" id="pa-vision-action">—</div>
      <div class="panel-sub" id="pa-vision-sub">Waiting for scene…</div>
      <div class="panel-thinking" id="pa-vision-thinking"></div>
      <div class="panel-ts" id="pa-vision-ts"></div>
    </div>
    <div class="agent-panel panel-threat" id="panel-threat" data-agent="threat">
      <div class="panel-header"><span class="panel-dot" id="dot-threat"></span><span class="panel-name">Threat</span></div>
      <div class="panel-region">Amygdala · Neck</div>
      <div class="panel-action" id="pa-threat-action">—</div>
      <div class="panel-sub" id="pa-threat-sub"></div>
      <div class="panel-thinking" id="pa-threat-thinking"></div>
      <div class="panel-ts" id="pa-threat-ts"></div>
    </div>
    <div class="agent-panel panel-conductor" id="panel-conductor" data-agent="conductor">
      <div class="panel-header"><span class="panel-dot" id="dot-conductor"></span><span class="panel-name">Conductor</span></div>
      <div class="panel-region">Prefrontal Cortex · Torso</div>
      <div class="panel-action" id="pa-conductor-action">—</div>
      <div class="panel-sub" id="pa-conductor-sub"></div>
      <div class="panel-thinking" id="pa-conductor-thinking"></div>
      <div class="panel-ts" id="pa-conductor-ts"></div>
    </div>
    <div class="agent-panel panel-upper_left" id="panel-upper_left" data-agent="upper_left">
      <div class="panel-header"><span class="panel-dot" id="dot-upper_left"></span><span class="panel-name">Upper Left</span></div>
      <div class="panel-region">Motor Cortex L · Left Arm</div>
      <div class="panel-action" id="pa-upper_left-action">—</div>
      <div class="panel-sub" id="pa-upper_left-sub"></div>
      <div class="panel-thinking" id="pa-upper_left-thinking"></div>
      <div class="panel-ts" id="pa-upper_left-ts"></div>
    </div>
    <div class="agent-panel panel-upper_right" id="panel-upper_right" data-agent="upper_right">
      <div class="panel-header"><span class="panel-dot" id="dot-upper_right"></span><span class="panel-name">Upper Right</span></div>
      <div class="panel-region">Motor Cortex R · Right Arm</div>
      <div class="panel-action" id="pa-upper_right-action">—</div>
      <div class="panel-sub" id="pa-upper_right-sub"></div>
      <div class="panel-thinking" id="pa-upper_right-thinking"></div>
      <div class="panel-ts" id="pa-upper_right-ts"></div>
    </div>
    <div class="agent-panel panel-lower" id="panel-lower" data-agent="lower">
      <div class="panel-header"><span class="panel-dot" id="dot-lower"></span><span class="panel-name">Lower</span></div>
      <div class="panel-region">Cerebellum · Legs</div>
      <div class="panel-action" id="pa-lower-action">—</div>
      <div class="panel-sub" id="pa-lower-sub"></div>
      <div class="panel-thinking" id="pa-lower-thinking"></div>
      <div class="panel-ts" id="pa-lower-ts"></div>
    </div>
    <div class="agent-panel panel-spine" id="panel-spine" data-agent="spine">
      <div class="panel-header"><span class="panel-dot" id="dot-spine"></span><span class="panel-name">Spine</span></div>
      <div class="panel-region">Spinal Cord · Reflex</div>
      <div class="panel-action" id="pa-spine-action">Standby</div>
      <div class="panel-sub" id="pa-spine-sub"></div>
      <div class="panel-thinking" id="pa-spine-thinking"></div>
      <div class="panel-ts" id="pa-spine-ts"></div>
    </div>
    <div class="agent-panel panel-safety" id="panel-safety" data-agent="safety">
      <div class="panel-header"><span class="panel-dot" id="dot-safety"></span><span class="panel-name">Safety</span></div>
      <div class="panel-region">Brainstem · Shield</div>
      <div class="panel-action" id="pa-safety-action">—</div>
      <div class="panel-sub" id="pa-safety-sub"></div>
      <div class="panel-thinking" id="pa-safety-thinking"></div>
      <div class="panel-ts" id="pa-safety-ts"></div>
    </div>

    <div class="cmd-strip" id="cmd-strip">
      <div class="cmd-strip-label">Final Command → Robot</div>
      <div class="cmd-strip-main" id="cmd-main">Waiting…</div>
      <div class="cmd-strip-sub" id="cmd-sub">—</div>
      <div class="cmd-strip-grid">
        <div class="cmd-strip-item">L: <span id="cmd-left">—</span></div>
        <div class="cmd-strip-item">R: <span id="cmd-right">—</span></div>
        <div class="cmd-strip-item">Free: <span id="cmd-free">—</span></div>
        <div class="cmd-strip-item">Gait: <span id="cmd-gait">—</span></div>
      </div>
    </div>
  </div>

  <div class="log-drawer">
    <button class="log-toggle" id="log-toggle" type="button">
      <span>Band Message Log</span>
      <span id="log-chevron">▼</span>
    </button>
    <div class="log-body" id="log-body">
      <div class="log-box" id="log-box"></div>
      <div class="log-footer" id="msg-count">messages seen: 0</div>
    </div>
  </div>
</div>

<script>
const ARM_ANGLES = {
  "HOLD_STEADY": { l: 0, r: 0 },
  "GENTLE_LEFT_PULL": { l: -40, r: -15 },
  "GENTLE_RIGHT_PULL": { l: -15, r: 40 },
  "FORWARD_PUSH": { l: -70, r: 70 },
  "RELEASE": { l: 20, r: -20 },
  "HALT_EXTEND": { l: -90, r: 90 },
};
const L_PIVOT = [120, 220], R_PIVOT = [280, 220];

const AGENT_ANCHORS = {
  vision:      { x: 50, y: 10,  panelSide: 'center' },
  threat:      { x: 50, y: 22,  panelSide: 'right' },
  conductor:   { x: 50, y: 38,  panelSide: 'left' },
  upper_left:  { x: 8,  y: 38,  panelSide: 'left' },
  upper_right: { x: 92, y: 38,  panelSide: 'right' },
  lower:       { x: 50, y: 78,  panelSide: 'center' },
  spine:       { x: 78, y: 42,  panelSide: 'right' },
  safety:      { x: 22, y: 38,  panelSide: 'left' },
};

const LINK_DEFS = [
  { from: 'vision', to: 'conductor', tags: ['SCENE'], peer: false },
  { from: 'vision', to: 'threat', tags: ['SCENE'], peer: false },
  { from: 'threat', to: 'spine', tags: ['REFLEX', 'THREAT'], peer: false },
  { from: 'threat', to: 'conductor', tags: ['THREAT'], peer: false },
  { from: 'conductor', to: 'upper_left', tags: ['TASK'], peer: false },
  { from: 'conductor', to: 'upper_right', tags: ['TASK'], peer: false },
  { from: 'conductor', to: 'lower', tags: ['TASK'], peer: false },
  { from: 'upper_left', to: 'lower', tags: ['READY'], peer: true },
  { from: 'upper_right', to: 'lower', tags: ['READY'], peer: true },
  { from: 'upper_left', to: 'safety', tags: ['READY'], peer: false },
  { from: 'upper_right', to: 'safety', tags: ['READY'], peer: false },
  { from: 'lower', to: 'safety', tags: ['READY'], peer: false },
  { from: 'safety', to: 'conductor', tags: ['APPROVED', 'VETOED'], peer: false },
  { from: 'spine', to: 'upper_left', tags: ['REFLEX', 'HALT'], peer: false },
  { from: 'spine', to: 'upper_right', tags: ['REFLEX', 'HALT'], peer: false },
  { from: 'spine', to: 'lower', tags: ['REFLEX', 'HALT'], peer: false },
];

const ZONE_MAP = {
  vision: 'zone-head', threat: 'zone-neck', conductor: 'zone-torso',
  upper_left: 'zone-arm-left', upper_right: 'zone-arm-right',
  lower: 'zone-lower', spine: 'zone-spine', safety: 'zone-torso',
};

let currentLAngle = 0, currentRAngle = 0, targetLAngle = 0, targetRAngle = 0;
let legPhase = 0, legAnimating = false, lastAnimTs = 0;
let prevAgentTs = {}, linkEls = {};

function lerp(a, b, t) { return a + (b - a) * t; }
function ts(ms) { return ms ? new Date(ms).toLocaleTimeString() : ''; }
function hazardClass(h) { return 'hazard-' + (h || 'NONE'); }

function svgPoint(agent) {
  const a = AGENT_ANCHORS[agent];
  return { x: a.x * 4, y: a.y * 6 };
}

function buildLinks() {
  const layer = document.getElementById('link-layer');
  layer.innerHTML = '';
  linkEls = {};
  LINK_DEFS.forEach((def, i) => {
    const p1 = svgPoint(def.from), p2 = svgPoint(def.to);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2 - 20;
    path.setAttribute('d', `M${p1.x},${p1.y} Q${mx},${my} ${p2.x},${p2.y}`);
    path.setAttribute('class', 'link-line' + (def.peer ? ' peer' : ''));
    path.setAttribute('id', 'link-' + i);
    path.dataset.from = def.from;
    path.dataset.to = def.to;
    layer.appendChild(path);
    linkEls[def.from + '->' + def.to] = path;
  });
}

function pulseLink(from, to, color) {
  const el = linkEls[from + '->' + to];
  if (!el) return;
  el.style.stroke = color || '#58a6ff';
  el.classList.remove('pulse');
  void el.offsetWidth;
  el.classList.add('pulse');
}

function pulseLinksForTag(tag, pathMode) {
  const color = (pathMode === 'REFLEX' || tag === 'REFLEX' || tag === 'HALT') ? '#f85149' : '#58a6ff';
  LINK_DEFS.forEach(def => {
    if (def.tags.includes(tag)) pulseLink(def.from, def.to, color);
  });
}

function pulseZone(agent) {
  const zoneId = ZONE_MAP[agent];
  if (!zoneId) return;
  const z = document.getElementById(zoneId);
  if (!z) return;
  z.classList.add('active');
  setTimeout(() => z.classList.remove('active'), 1200);
}

function positionPanels() {
  const stage = document.getElementById('robot-stage');
  const rect = stage.getBoundingClientRect();
  const svg = document.getElementById('robot-svg');
  const svgRect = svg.getBoundingClientRect();
  const offX = svgRect.left - rect.left;
  const offY = svgRect.top - rect.top;

  Object.entries(AGENT_ANCHORS).forEach(([agent, anchor]) => {
    const panel = document.getElementById('panel-' + agent);
    if (!panel) return;
    const px = offX + (anchor.x / 100) * svgRect.width;
    const py = offY + (anchor.y / 100) * svgRect.height;
    let tx = -50, ty = -108;
    if (anchor.panelSide === 'left') { tx = -90; }
    else if (anchor.panelSide === 'right') { tx = -10; }
    panel.style.left = px + 'px';
    panel.style.top = py + 'px';
    panel.style.transform = `translate(${tx}%, ${ty}%)`;
  });
}

function flashPanel(agent, cls) {
  const el = document.getElementById('panel-' + agent);
  if (!el) return;
  el.classList.remove('flash-red', 'flash-green', 'active');
  if (cls) el.classList.add(cls);
  el.classList.add('active');
  setTimeout(() => { el.classList.remove('active', cls || ''); }, 1000);
}

function updateAgentPanel(agent, data, opts) {
  opts = opts || {};
  const prefix = 'pa-' + agent;
  const set = (suffix, val) => {
    const el = document.getElementById(prefix + '-' + suffix);
    if (el) el.textContent = val || '';
  };
  set('thinking', data.thinking);
  set('ts', data.ts ? ts(data.ts) : '');

  const dot = document.getElementById('dot-' + agent);
  if (dot) dot.classList.toggle('live', !!data.active);

  if (data.ts && data.ts !== prevAgentTs[agent]) {
    prevAgentTs[agent] = data.ts;
    pulseZone(agent);
    if (data.last_tag) pulseLinksForTag(data.last_tag, opts.pathMode);
    let flashCls = '';
    if (agent === 'safety' && data.status === 'VETOED') flashCls = 'flash-red';
    else if (agent === 'safety' && data.status === 'APPROVED') flashCls = 'flash-green';
    else if (agent === 'spine') flashCls = 'flash-red';
    flashPanel(agent, flashCls);
    if (agent === 'safety') {
      const safetyPanel = document.getElementById('panel-safety');
      if (safetyPanel) safetyPanel.classList.toggle('vetoed', data.status === 'VETOED');
    }
  }
}

function animLoop(ts) {
  const dt = Math.min((ts - lastAnimTs) / 1000, 0.1);
  lastAnimTs = ts;
  const speed = 6;
  currentLAngle = lerp(currentLAngle, targetLAngle, Math.min(speed * dt, 1));
  currentRAngle = lerp(currentRAngle, targetRAngle, Math.min(speed * dt, 1));
  document.getElementById('arm-left').setAttribute('transform', `rotate(${currentLAngle}, ${L_PIVOT[0]}, ${L_PIVOT[1]})`);
  document.getElementById('arm-right').setAttribute('transform', `rotate(${currentRAngle}, ${R_PIVOT[0]}, ${R_PIVOT[1]})`);
  if (legAnimating) {
    legPhase += dt * 3;
    const lStep = Math.sin(legPhase) * 12;
    const rStep = Math.sin(legPhase + Math.PI) * 12;
    document.getElementById('leg-left').setAttribute('transform', `translate(0, ${lStep})`);
    document.getElementById('leg-right').setAttribute('transform', `translate(0, ${rStep})`);
  } else {
    document.getElementById('leg-left').setAttribute('transform', 'translate(0,0)');
    document.getElementById('leg-right').setAttribute('transform', 'translate(0,0)');
  }
  requestAnimationFrame(animLoop);
}

function setArmTargets(leftAction, rightAction, freeAction) {
  if (freeAction === 'HALT_EXTEND') { targetLAngle = -90; targetRAngle = 90; return; }
  const la = ARM_ANGLES[leftAction] || ARM_ANGLES['HOLD_STEADY'];
  const ra = ARM_ANGLES[rightAction] || ARM_ANGLES['HOLD_STEADY'];
  targetLAngle = la.l; targetRAngle = ra.r;
}

function setChestColor(command) {
  const colors = {
    'EMERGENCY_STOP': '#f85149', 'STOP': '#d29922', 'SLOW_DOWN': '#d2a8ff',
    'MOVE_FORWARD': '#3fb950', 'GUIDE_LEFT': '#58a6ff', 'GUIDE_RIGHT': '#58a6ff',
  };
  const c = colors[command] || '#58a6ff';
  document.getElementById('chest-light').setAttribute('fill', c + '33');
  document.getElementById('chest-light').setAttribute('stroke', c);
  document.getElementById('eye-l').setAttribute('fill', c);
  document.getElementById('eye-r').setAttribute('fill', c);
}

function update(s) {
  const pathMode = s.active_path;

  // Vision
  const v = s.vision;
  document.getElementById('pa-vision-action').textContent = v.hazard || 'NONE';
  document.getElementById('pa-vision-action').className = 'panel-action ' + hazardClass(v.hazard);
  document.getElementById('pa-vision-sub').textContent = (v.summary || '—') + (v.terrain && v.terrain !== '—' ? ' · ' + v.terrain : '');
  updateAgentPanel('vision', v, { pathMode });

  // Threat
  const t = s.threat;
  document.getElementById('pa-threat-action').textContent = t.level || '—';
  document.getElementById('pa-threat-action').className = 'panel-action ' + hazardClass(t.level);
  document.getElementById('pa-threat-sub').textContent = t.description || '—';
  updateAgentPanel('threat', t, { pathMode });

  // Conductor
  const c = s.conductor;
  document.getElementById('pa-conductor-action').textContent = c.decision || '—';
  document.getElementById('pa-conductor-sub').textContent = c.reason || '—';
  updateAgentPanel('conductor', c, { pathMode });

  // Upper Left
  const ul = s.upper_left;
  document.getElementById('pa-upper_left-action').textContent = ul.arm_action || '—';
  document.getElementById('pa-upper_left-sub').textContent = ul.free_arm && ul.free_arm !== '—' ? 'Free: ' + ul.free_arm : '';
  updateAgentPanel('upper_left', ul, { pathMode });

  // Upper Right
  const ur = s.upper_right;
  document.getElementById('pa-upper_right-action').textContent = ur.arm_action || '—';
  document.getElementById('pa-upper_right-sub').textContent = ur.free_arm && ur.free_arm !== '—' ? 'Free: ' + ur.free_arm : '';
  updateAgentPanel('upper_right', ur, { pathMode });

  // Lower
  const lo = s.lower;
  document.getElementById('pa-lower-action').textContent = lo.gait_action || '—';
  document.getElementById('pa-lower-sub').textContent = lo.pace_ms ? lo.pace_ms + 'ms pace' : '';
  updateAgentPanel('lower', lo, { pathMode });
  legAnimating = !!(lo.gait_action && lo.gait_action !== '—' && lo.gait_action !== 'HALT' && lo.gait_action !== 'PAUSE');

  // Safety
  const sa = s.safety;
  document.getElementById('pa-safety-action').textContent = sa.status || '—';
  document.getElementById('pa-safety-action').className = 'panel-action status-' + (sa.status || '');
  document.getElementById('pa-safety-sub').textContent = sa.reason || '—';
  updateAgentPanel('safety', sa, { pathMode });
  document.getElementById('panel-safety').classList.toggle('vetoed', sa.status === 'VETOED');

  // Spine
  const sp = s.spine;
  document.getElementById('pa-spine-action').textContent = sp.status || 'Standby';
  document.getElementById('pa-spine-sub').textContent = '';
  updateAgentPanel('spine', sp, { pathMode });
  const spineCh = document.getElementById('spine-channel');
  if (spineCh) spineCh.setAttribute('opacity', sp.active ? '1' : '0.5');

  // Final command strip
  const f = s.final_command;
  document.getElementById('cmd-main').textContent = f.command || 'Waiting…';
  document.getElementById('cmd-sub').textContent = f.reason || '—';
  document.getElementById('cmd-left').textContent = f.left_arm || '—';
  document.getElementById('cmd-right').textContent = f.right_arm || '—';
  document.getElementById('cmd-free').textContent = f.free_arm || '—';
  document.getElementById('cmd-gait').textContent = f.gait || '—';
  document.getElementById('robot-status-text').textContent = f.command || 'STANDBY';
  if (f.ts) {
    const strip = document.getElementById('cmd-strip');
    strip.classList.add('flash');
    setTimeout(() => strip.classList.remove('flash'), 900);
    pulseLinksForTag('FINAL_COMMAND', f.path);
  }
  if (f.command && f.command !== '—') {
    setArmTargets(f.left_arm, f.right_arm, f.free_arm);
    setChestColor(f.command);
  }

  // Path badge
  const pb = document.getElementById('path-badge');
  if (pathMode === 'CORTICAL' || pathMode === 'REFLEX') {
    pb.style.display = 'inline-block';
    pb.textContent = pathMode + ' PATH';
    pb.className = 'path-badge path-' + pathMode;
  } else {
    pb.style.display = 'none';
  }

  // Log
  const box = document.getElementById('log-box');
  const atTop = box.scrollTop < 10;
  box.innerHTML = (s.log || []).slice().reverse().map(e =>
    `<div class="log-entry">
      <span class="log-time">${new Date(e.ts).toLocaleTimeString()}</span>
      <span class="log-sender">${(e.sender||'').split('/').pop()}</span>
      <span class="log-tag tag-${e.tag}">[${e.tag}]</span>
      <span class="log-content">${e.content.replace(/</g,'&lt;')}</span>
    </div>`
  ).join('');
  if (atTop) box.scrollTop = 0;
  document.getElementById('msg-count').textContent = 'messages seen: ' + (s.message_count || 0);

  // Latency
  if (s.pipeline_latency_ms != null) {
    document.getElementById('latency-box').style.display = 'block';
    const val = document.getElementById('latency-value');
    val.textContent = s.pipeline_latency_ms;
    val.style.color = s.pipeline_latency_ms < 3000 ? '#3fb950' : s.pipeline_latency_ms < 6000 ? '#d29922' : '#f85149';
    drawSparkline(s.latency_history || []);
  }

  const badge = document.getElementById('conn-badge');
  if (s.connected) { badge.textContent = '● Live'; badge.className = 'badge green'; }
  else { badge.textContent = '○ Waiting for Band'; badge.className = 'badge grey'; }
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
    const x = i * w, y = canvas.height - (v / max) * (canvas.height - 2) - 1;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

document.getElementById('log-toggle').addEventListener('click', () => {
  const body = document.getElementById('log-body');
  const open = body.classList.toggle('open');
  document.getElementById('log-chevron').textContent = open ? '▲' : '▼';
});

buildLinks();
positionPanels();
window.addEventListener('resize', positionPanels);
requestAnimationFrame(animLoop);

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
