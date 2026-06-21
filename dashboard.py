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
    "vision":        {"summary": "—", "hazard": "NONE", "obstacles": [], "terrain": "—", "latency_ms": 0, "ts": 0},
    "threat":        {"level": "NONE", "description": "—", "ts": 0},
    "conductor":     {"decision": "—", "reason": "—", "ts": 0},
    "upper_left":    {"arm_action": "—", "free_arm": "—", "ts": 0},
    "upper_right":   {"arm_action": "—", "free_arm": "—", "ts": 0},
    "lower":         {"gait_action": "—", "pace_ms": 0, "ts": 0},
    "safety":        {"status": "—", "reason": "—", "ts": 0},
    "spine":         {"status": "—", "ts": 0},
    "final_command": {"command": "—", "reason": "—", "path": "—", "left_arm": "—", "right_arm": "—", "free_arm": "—", "gait": "—", "ts": 0},
    "message_count": 0,
    "connected":     False,
}
_listeners: list[asyncio.Queue] = []
_loop: asyncio.AbstractEventLoop | None = None


def _now_ms() -> int:
    return round(time.time() * 1000)


def _ts_label(ts: int) -> str:
    if ts == 0:
        return "—"
    return datetime.fromtimestamp(ts / 1000).strftime("%H:%M:%S")


def _push_update():
    for q in list(_listeners):
        try:
            q.put_nowait(json.dumps(state))
        except Exception:
            pass


def _parse_message(content: str, sender: str):
    content = content.strip()
    state["message_count"] += 1

    if content.startswith("[SCENE]"):
        try:
            data = json.loads(content[7:].strip())
            state["vision"].update({
                "summary":    data.get("scene_summary", "—"),
                "hazard":     data.get("hazard_level", "NONE"),
                "obstacles":  data.get("obstacles", []),
                "terrain":    data.get("terrain", "—"),
                "latency_ms": data.get("latency_ms", 0),
                "ts":         data.get("timestamp", _now_ms()),
            })
        except Exception:
            pass

    elif "[THREAT]" in content:
        try:
            start = content.index("[THREAT]") + 8
            data = json.loads(content[start:].strip())
            state["threat"].update({
                "level":       data.get("threat_level", "NONE"),
                "description": data.get("description", "—"),
                "ts":          _now_ms(),
            })
        except Exception:
            state["threat"].update({"level": "UNKNOWN", "description": content[:80], "ts": _now_ms()})

    elif "[TASK]" in content:
        try:
            start = content.index("[TASK]") + 6
            data = json.loads(content[start:].strip())
            state["conductor"].update({
                "decision": data.get("decision", "—"),
                "reason":   data.get("reason", "—"),
                "ts":       _now_ms(),
            })
        except Exception:
            state["conductor"].update({"decision": "dispatched", "reason": content[:80], "ts": _now_ms()})

    elif "[READY]" in content:
        try:
            start = content.index("[READY]") + 7
            data = json.loads(content[start:].strip())
            sender_lower = sender.lower()
            if "upperleft" in sender_lower or "upper_left" in sender_lower:
                state["upper_left"].update({
                    "arm_action": data.get("arm_action", "—"),
                    "free_arm":   data.get("free_arm_action", "—"),
                    "ts":         _now_ms(),
                })
            elif "upperright" in sender_lower or "upper_right" in sender_lower:
                state["upper_right"].update({
                    "arm_action": data.get("arm_action", "—"),
                    "free_arm":   data.get("free_arm_action", "—"),
                    "ts":         _now_ms(),
                })
            elif "lower" in sender_lower:
                state["lower"].update({
                    "gait_action": data.get("gait_action", "—"),
                    "pace_ms":     data.get("pace_ms", 0),
                    "ts":          _now_ms(),
                })
        except Exception:
            pass

    elif "[APPROVED]" in content:
        state["safety"].update({"status": "APPROVED", "reason": "—", "ts": _now_ms()})

    elif "[VETOED]" in content:
        try:
            start = content.index("[VETOED]") + 8
            data = json.loads(content[start:].strip())
            state["safety"].update({"status": "VETOED", "reason": data.get("reason", "—"), "ts": _now_ms()})
        except Exception:
            state["safety"].update({"status": "VETOED", "reason": "—", "ts": _now_ms()})

    elif "[REFLEX]" in content or "[HALT]" in content:
        state["spine"].update({"status": "REFLEX FIRED", "ts": _now_ms()})
        state["safety"].update({"status": "—", "reason": "—", "ts": 0})

    elif "[REFLEX_EXECUTED]" in content:
        state["spine"].update({"status": "REFLEX EXECUTED", "ts": _now_ms()})

    elif content.startswith("[FINAL_COMMAND]"):
        try:
            data = json.loads(content[15:].strip())
            state["final_command"].update({
                "command":  data.get("command", "—"),
                "reason":   data.get("reason", "—"),
                "path":     data.get("path", "—"),
                "left_arm": data.get("left_arm_action", "—"),
                "right_arm":data.get("right_arm_action", "—"),
                "free_arm": data.get("free_arm_action", "—"),
                "gait":     data.get("gait_action", "—"),
                "ts":       data.get("timestamp", _now_ms()),
            })
            # reset safety status for next cycle
            state["safety"].update({"status": "—", "reason": "—", "ts": 0})
        except Exception:
            pass

    _push_update()


# ---------------------------------------------------------------------------
# Band listener (runs in asyncio thread)
# ---------------------------------------------------------------------------

async def _band_listener():
    agent_id  = os.environ.get("DashboardID", "")
    api_key   = os.environ.get("DashboardBandAPI", "")
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
            print(f"[Dashboard] Monitoring room {room.id}")
    except Exception as e:
        print(f"[Dashboard] Could not list rooms: {e}")

    await link.subscribe_agent_rooms(agent_id)

    async for event in link:
        if isinstance(event, RoomAddedEvent):
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


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Baymax — Live Pipeline</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }
  h1 { text-align: center; font-size: 1.6rem; margin-bottom: 4px; letter-spacing: 2px; color: #58a6ff; }
  .subtitle { text-align: center; font-size: 0.8rem; color: #8b949e; margin-bottom: 20px; }
  .status-bar { text-align: center; margin-bottom: 16px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge.green { background: #1a4731; color: #3fb950; }
  .badge.grey  { background: #21262d; color: #8b949e; }

  .pipeline { display: flex; flex-direction: column; gap: 12px; max-width: 960px; margin: 0 auto; }
  .row { display: flex; gap: 12px; justify-content: center; }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 10px;
    padding: 14px 16px; flex: 1; min-width: 180px; max-width: 300px;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .card.flash { border-color: #58a6ff; box-shadow: 0 0 12px #58a6ff44; }
  .card-title { font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #8b949e; margin-bottom: 8px; }
  .card-main { font-size: 1rem; font-weight: 600; color: #e6edf3; margin-bottom: 4px; word-break: break-word; }
  .card-sub  { font-size: 0.75rem; color: #8b949e; }
  .card-ts   { font-size: 0.65rem; color: #484f58; margin-top: 6px; }

  .hazard-NONE     { color: #3fb950; }
  .hazard-LOW      { color: #d29922; }
  .hazard-HIGH     { color: #f0883e; }
  .hazard-CRITICAL { color: #f85149; }
  .status-APPROVED { color: #3fb950; }
  .status-VETOED   { color: #f85149; }

  .final-card {
    background: #0d2f5e; border: 1px solid #388bfd; border-radius: 10px;
    padding: 16px 20px; max-width: 960px; margin: 0 auto;
    transition: box-shadow 0.3s;
  }
  .final-card.flash { box-shadow: 0 0 20px #388bfd88; }
  .final-title { font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #388bfd; margin-bottom: 8px; }
  .final-command { font-size: 1.5rem; font-weight: 700; color: #58a6ff; margin-bottom: 6px; }
  .final-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
  .final-item { background: #0d1b2e; border-radius: 6px; padding: 8px 10px; }
  .final-label { font-size: 0.65rem; color: #388bfd; text-transform: uppercase; letter-spacing: 1px; }
  .final-value { font-size: 0.85rem; color: #e6edf3; font-weight: 600; margin-top: 2px; }

  .arrow { text-align: center; color: #30363d; font-size: 1.2rem; line-height: 1; }
  .msg-count { text-align: center; font-size: 0.72rem; color: #484f58; margin-top: 16px; }
</style>
</head>
<body>

<h1>⚡ BAYMAX</h1>
<p class="subtitle">Live Multi-Agent Pipeline — UC Berkeley AI Hackathon 2026</p>

<div class="status-bar">
  <span id="conn-badge" class="badge grey">Connecting…</span>
</div>

<div class="pipeline">

  <!-- Row 1: Vision -->
  <div class="row">
    <div class="card" id="card-vision">
      <div class="card-title">👁 Vision</div>
      <div class="card-main" id="v-hazard">—</div>
      <div class="card-sub" id="v-summary">Waiting for scene…</div>
      <div class="card-sub" id="v-terrain"></div>
      <div class="card-ts" id="v-ts"></div>
    </div>
    <div class="card" id="card-threat">
      <div class="card-title">⚠️ Threat</div>
      <div class="card-main" id="t-level">—</div>
      <div class="card-sub" id="t-desc">—</div>
      <div class="card-ts" id="t-ts"></div>
    </div>
  </div>

  <div class="arrow">↓</div>

  <!-- Row 2: Conductor -->
  <div class="row">
    <div class="card" id="card-conductor" style="max-width:500px;">
      <div class="card-title">🧠 Conductor</div>
      <div class="card-main" id="c-decision">—</div>
      <div class="card-sub" id="c-reason">—</div>
      <div class="card-ts" id="c-ts"></div>
    </div>
  </div>

  <div class="arrow">↓</div>

  <!-- Row 3: Arm + Lower agents -->
  <div class="row">
    <div class="card" id="card-upperleft">
      <div class="card-title">💪 Upper Left</div>
      <div class="card-main" id="ul-arm">—</div>
      <div class="card-sub" id="ul-free">Free arm: —</div>
      <div class="card-ts" id="ul-ts"></div>
    </div>
    <div class="card" id="card-lower">
      <div class="card-title">🦵 Lower</div>
      <div class="card-main" id="lo-gait">—</div>
      <div class="card-sub" id="lo-pace">—</div>
      <div class="card-ts" id="lo-ts"></div>
    </div>
    <div class="card" id="card-upperright">
      <div class="card-title">💪 Upper Right</div>
      <div class="card-main" id="ur-arm">—</div>
      <div class="card-sub" id="ur-free">Free arm: —</div>
      <div class="card-ts" id="ur-ts"></div>
    </div>
  </div>

  <div class="arrow">↓</div>

  <!-- Row 4: Safety + Spine -->
  <div class="row">
    <div class="card" id="card-safety">
      <div class="card-title">🛡 Safety</div>
      <div class="card-main" id="s-status">—</div>
      <div class="card-sub" id="s-reason">—</div>
      <div class="card-ts" id="s-ts"></div>
    </div>
    <div class="card" id="card-spine">
      <div class="card-title">⚡ Spine (Reflex)</div>
      <div class="card-main" id="sp-status">Standby</div>
      <div class="card-ts" id="sp-ts"></div>
    </div>
  </div>

  <div class="arrow">↓</div>

  <!-- Final Command -->
  <div class="final-card" id="card-final">
    <div class="final-title">🤖 Final Command → Robot</div>
    <div class="final-command" id="f-command">Waiting…</div>
    <div class="card-sub" id="f-reason" style="color:#8b949e;">—</div>
    <div class="final-grid">
      <div class="final-item"><div class="final-label">Left Arm</div><div class="final-value" id="f-left">—</div></div>
      <div class="final-item"><div class="final-label">Right Arm</div><div class="final-value" id="f-right">—</div></div>
      <div class="final-item"><div class="final-label">Free Arm</div><div class="final-value" id="f-free">—</div></div>
      <div class="final-item"><div class="final-label">Gait</div><div class="final-value" id="f-gait">—</div></div>
    </div>
    <div class="card-ts" id="f-ts" style="margin-top:10px;"></div>
  </div>

</div>

<div class="msg-count" id="msg-count">messages seen: 0</div>

<script>
function ts(ms) {
  if (!ms) return '';
  return new Date(ms).toLocaleTimeString();
}
function flash(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 800);
}
function hazardClass(h) {
  return 'hazard-' + (h || 'NONE');
}

function update(s) {
  const v = s.vision;
  document.getElementById('v-hazard').textContent = v.hazard || 'NONE';
  document.getElementById('v-hazard').className = 'card-main ' + hazardClass(v.hazard);
  document.getElementById('v-summary').textContent = v.summary || '—';
  document.getElementById('v-terrain').textContent = v.terrain ? 'Terrain: ' + v.terrain : '';
  document.getElementById('v-ts').textContent = v.ts ? ts(v.ts) + ' · ' + v.latency_ms + 'ms' : '';
  if (v.ts) flash('card-vision');

  const t = s.threat;
  document.getElementById('t-level').textContent = t.level || '—';
  document.getElementById('t-level').className = 'card-main ' + hazardClass(t.level);
  document.getElementById('t-desc').textContent = t.description || '—';
  document.getElementById('t-ts').textContent = t.ts ? ts(t.ts) : '';
  if (t.ts) flash('card-threat');

  const c = s.conductor;
  document.getElementById('c-decision').textContent = c.decision || '—';
  document.getElementById('c-reason').textContent = c.reason || '—';
  document.getElementById('c-ts').textContent = c.ts ? ts(c.ts) : '';
  if (c.ts) flash('card-conductor');

  const ul = s.upper_left;
  document.getElementById('ul-arm').textContent = ul.arm_action || '—';
  document.getElementById('ul-free').textContent = 'Free arm: ' + (ul.free_arm || '—');
  document.getElementById('ul-ts').textContent = ul.ts ? ts(ul.ts) : '';
  if (ul.ts) flash('card-upperleft');

  const ur = s.upper_right;
  document.getElementById('ur-arm').textContent = ur.arm_action || '—';
  document.getElementById('ur-free').textContent = 'Free arm: ' + (ur.free_arm || '—');
  document.getElementById('ur-ts').textContent = ur.ts ? ts(ur.ts) : '';
  if (ur.ts) flash('card-upperright');

  const lo = s.lower;
  document.getElementById('lo-gait').textContent = lo.gait_action || '—';
  document.getElementById('lo-pace').textContent = lo.pace_ms ? lo.pace_ms + 'ms pace' : '—';
  document.getElementById('lo-ts').textContent = lo.ts ? ts(lo.ts) : '';
  if (lo.ts) flash('card-lower');

  const sa = s.safety;
  document.getElementById('s-status').textContent = sa.status || '—';
  document.getElementById('s-status').className = 'card-main status-' + (sa.status || '');
  document.getElementById('s-reason').textContent = sa.reason || '—';
  document.getElementById('s-ts').textContent = sa.ts ? ts(sa.ts) : '';
  if (sa.ts) flash('card-safety');

  const sp = s.spine;
  document.getElementById('sp-status').textContent = sp.status || 'Standby';
  document.getElementById('sp-ts').textContent = sp.ts ? ts(sp.ts) : '';
  if (sp.ts) flash('card-spine');

  const f = s.final_command;
  document.getElementById('f-command').textContent = f.command || 'Waiting…';
  document.getElementById('f-reason').textContent = f.reason || '—';
  document.getElementById('f-left').textContent = f.left_arm || '—';
  document.getElementById('f-right').textContent = f.right_arm || '—';
  document.getElementById('f-free').textContent = f.free_arm || '—';
  document.getElementById('f-gait').textContent = f.gait || '—';
  document.getElementById('f-ts').textContent = f.ts ? 'Sent at ' + ts(f.ts) + ' · path: ' + (f.path || '—') : '';
  if (f.ts) flash('card-final');

  document.getElementById('msg-count').textContent = 'messages seen: ' + (s.message_count || 0);

  const badge = document.getElementById('conn-badge');
  if (s.connected) {
    badge.textContent = '● Live';
    badge.className = 'badge green';
  } else {
    badge.textContent = '○ Waiting for Band credentials';
    badge.className = 'badge grey';
  }
}

const es = new EventSource('/events');
es.onmessage = e => {
  try { update(JSON.parse(e.data)); } catch(_) {}
};
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
