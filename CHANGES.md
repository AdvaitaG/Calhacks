# Changes Since Adil's Last Commit

All changes below were made after Adil's commit `a1ef476` (Fix conductor f-string escaping).

---

## agents/shared/config.py
- Added `"safety"` entry to `AGENT_CONFIGS` so Safety reads credentials the same way as all other agents (`SafetyID`, `SafetyBandAPI` from `.env`)

## agents/safety.py
- Removed duplicated `WS_URL` / `REST_URL` constants — now imports them from `agents/shared/config.py`
- Removed local `_require()` helper — now uses `AGENT_CONFIGS["safety"]` like every other agent
- Result: Safety is fully wired into the shared config pattern

## agents/vision_agent.py
- Added `"timestamp": round(time.time() * 1000)` to every `[SCENE]` JSON payload so downstream agents get real epoch-ms timestamps
- Slowed `FRAME_INTERVAL_SECONDS` from `1.0` → `2.0` to halve Band message volume (Gemini takes 5–9s anyway, so 1s was just queuing stale frames)
- Added auto-restart logic: if the vision loop crashes (Gemini timeout, webcam disconnect, any exception), it logs the error and restarts after 3 seconds without dropping the Band connection

## agents/conductor.py
- Updated FINAL_COMMAND schema in INSTRUCTIONS to copy `timestamp` from the incoming `[SCENE]` JSON instead of hardcoding `0`

## reset_room.py *(new file)*
- Script to create a fresh Band chat room and invite all agents when the message limit is hit
- Connects as Conductor, calls `create_agent_chat`, then `add_agent_chat_participant` for every agent (upper_left, upper_right, lower, threat, spine, safety, vision, robot)
- Fixed response parsing bug: `resp.data.id` is always correct (was previously guarded with a broken `hasattr` fallback that would have crashed)
- Usage: `python reset_room.py` → then `bash scripts/mac/stop_all.sh && bash scripts/mac/start_all.sh`

## scripts/mac/start_all.sh *(new file)*
- Launches all 8 agents as background processes in the correct order (conductor → threat/spine → upper_left/upper_right/lower → safety → vision)
- Logs each agent to `logs/<agent>.log`
- Saves PIDs to `.pids` for clean shutdown

## scripts/mac/stop_all.sh *(new file)*
- Kills all agents started by `start_all.sh` using the saved `.pids` file

## scripts/linux/start_all.sh *(new file)*
- Same as mac version but uses `python3` explicitly (required on WSL/Ubuntu where `python` is not aliased)

## scripts/linux/stop_all.sh *(new file)*
- Same as mac stop script

## .env.example
- Added `SafetyID`, `SafetyBandAPI`, `SafetyHandle` entries (previously missing/commented out)
- Added `RobotID`, `RobotBandAPI`, `RobotHandle` entries for Adil's robot agent
