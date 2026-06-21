# Dependencies from Eshwar — Adil's Return Path (Hour 2)

What I need from Eshwar before/while I build the **command return path**:
`Band FINAL_COMMAND → {vx, vy, vyaw} → robot → B1LocoClient.Move()`.

I can build against **mocks today** (mock FINAL_COMMAND + stubbed SDK), so none of
these hard-block me from *starting*. But each must be locked before **live
integration** works. Ranked by how much it blocks me.

Source of truth note: where the **contract** (`ADIL_READ_THIS.md`) and the
**code** (`agents/conductor.py`, `agents/vision_agent.py`) disagree, I've flagged
it — we need to pick one.

---

## 🔴 Blocking live integration

### 1. Band listener credential for me
I have no Band identity. `.env` has IDs/keys for conductor, upperleft, upperright,
lower, threat, spine, vision — **none for a robot-side listener.** To subscribe to
the room and read `FINAL_COMMAND`, I need either:
- a dedicated `RobotID` + `RobotBandAPI` (preferred — clean sender filtering), or
- confirmation I can listen under an existing identity.

**Need:** an agent_id + API key I can put in `.env`, plus the handle it appears as.

### 2. The exact room / chat to subscribe to
The contract says room `baymax-coordination`, but the code doesn't hardcode that —
`vision_agent.py` discovers chats at runtime via
`link.rest.agent_api_chats.list_agent_chats()` and joins whatever exists.

**Need:** the concrete chat/room id (or the exact discovery call) my listener
should attach to, so I'm reading the same room the Conductor posts into.

### 3. The exact FINAL_COMMAND wire format
Vision posts content as `"[SCENE] " + json.dumps(...)` via
`send_message(content, mentions=[...])`. The Conductor prompt just says
*"post it to the room"* — I don't know the literal string it emits.

**Need — confirm each:**
- Is it prefixed with a tag, e.g. `[FINAL_COMMAND] {json}`, or raw JSON?
- Will the Conductor **@mention me** (so I can filter cheaply), or do I match on
  `sender == ConductorHandle` + `"type":"FINAL_COMMAND"` in the body?
- Sender handle to filter on (default `@eshwar.rajasekar/conductor` — confirm).

### 4. Lock the FINAL_COMMAND schema — contract vs code MISMATCH
These disagree and I parse this object directly:

| Field | `ADIL_READ_THIS.md` (contract) | `conductor.py:52` (actual code) |
|-------|-------------------------------|---------------------------------|
| arm action | single `arm_action` | split: `left_arm_action`, `right_arm_action`, `free_arm_action` |
| gait | `gait_action` | `gait_action` ✅ same |
| command | `command` (6 values) | `command` (same 6) ✅ |
| other | `pace_ms`, `reason`, `path`, `timestamp` | `pace_ms`, `reason`, `path` (no `timestamp`) |

**Need:** which schema is authoritative? I'll code to whatever you confirm. If
it's the code version, I'll update `ADIL_READ_THIS.md` to match. Also confirm
whether `timestamp` is included (I use it to drop stale commands).

---

## 🟠 Needed for the emergency path (the headline safety feature)

### 5. How EMERGENCY_STOP / REFLEX reaches me
`threat.py` emits `{"fire_reflex": true, "reflex_command": "EMERGENCY_STOP"}` and
the Conductor's FINAL_COMMAND carries `"path": "CORTICAL"`. But the contract says
EMERGENCY_STOP "always comes via REFLEX path."

**Need — confirm:**
- Who posts the reflex stop to the room — Spine? Threat? Conductor?
- Same message format as a normal FINAL_COMMAND but with `"path": "REFLEX"`, or a
  different shape?
- So I can correctly apply **"EMERGENCY_STOP / REFLEX always wins"** when two
  commands arrive close together.

> Note: the genuine sub-100ms reflex runs *locally in my robot bridge* off the
> depth frame (per `ADIL_READ_THIS.md:255`). What I need from you is only the
> **cloud-path** reflex message so I can also honor a Threat/Spine-issued stop.

---

## 🟡 Confirmations (won't block, but calibrate my code)

### 6. Band connection pattern
Confirm I should connect the same way Vision does (`BandLink` + `AgentTools`,
`WS_URL`/`REST_URL` from `agents/shared/config.py`), or point me at a shared
listener helper. A 10-line "subscribe + read messages" snippet would save time.

### 7. Command cadence (for my 2-second timeout fallback)
Contract says CORTICAL ~800ms–1s, REFLEX ~90ms. If those still hold I'll set the
"no command in 2s → robot STOPs" fallback (`ADIL_READ_THIS.md:79`) accordingly.
Tell me if the real cadence is different.

---

## What I'm doing in the meantime (not blocked on you)
- Building the listener → `{vx,vy,vyaw}` map, EMERGENCY_STOP-wins priority, and
  2s timeout fallback against a **mock FINAL_COMMAND** I post myself.
- Stubbing `B1LocoClient.Move()` with logging so the whole bridge runs on my
  laptop. Swap to real SDK / K1 sim at the booth.

Once you answer 1–4, I can flip from mock to live in minutes.
