# ADIL READ THIS — Eshwar ↔ Adil Interface Contract

This is the agreed-on schema between Eshwar's agent layer and Adil's LiveKit/robot layer.
Do not change this without talking to Eshwar first.

---

## The One Thing Eshwar Sends You

When the Conductor agent finishes a decision cycle (Safety approved), it publishes a final command to the Band room. **You listen for this message and forward it to the robot via LiveKit.**

Eshwar's Conductor will post to Band:

```json
{
  "type": "FINAL_COMMAND",
  "command": "GUIDE_LEFT | GUIDE_RIGHT | MOVE_FORWARD | SLOW_DOWN | STOP | EMERGENCY_STOP",
  "arm_action": "GENTLE_LEFT_PULL | GENTLE_RIGHT_PULL | FORWARD_PUSH | HOLD_STEADY | RELEASE",
  "gait_action": "WALK_NORMAL | WALK_SLOW | PAUSE | STEP_HIGH | STEP_DOWN | HALT",
  "pace_ms": 500,
  "reason": "one sentence — why this command was chosen",
  "path": "CORTICAL | REFLEX",
  "timestamp": 1718900000000
}
```

`path` tells you whether this came from the normal decision cycle (`CORTICAL`) or an emergency bypass (`REFLEX`). You can use this for logging or to prioritize REFLEX commands if two arrive close together.

---

## Command Definitions

| `command` | What the robot should do |
|-----------|--------------------------|
| `GUIDE_LEFT` | Gentle left pull on user's arm, maintain walking pace |
| `GUIDE_RIGHT` | Gentle right pull on user's arm, maintain walking pace |
| `MOVE_FORWARD` | Continue straight, normal pace |
| `SLOW_DOWN` | Reduce pace, keep direction |
| `STOP` | Halt movement, hold position |
| `EMERGENCY_STOP` | Immediate full stop — always comes via REFLEX path |

---

## The One Thing You Send Eshwar

After you receive a frame from the robot's camera via LiveKit, pass it to Advaita's Vision Agent. Advaita handles that. **You do NOT send anything directly to Eshwar's agents.**

The only thing you owe Eshwar is:

1. **The final command arrives in Band** — you subscribe to the Band room and listen for `"type": "FINAL_COMMAND"` messages from the `Conductor` agent.
2. **You execute it** — translate the command fields into whatever the UFB robot/sim API expects and fire it via LiveKit.
3. **You handle EMERGENCY_STOP first** — if two commands arrive close together, EMERGENCY_STOP always wins regardless of order.

---

## How You Listen (Band Side)

Subscribe to the Band room `baymax-coordination`. Filter messages where:
- Sender is `Conductor`
- Message contains `"type": "FINAL_COMMAND"`

You don't need to @mention anyone or respond — just consume and execute.

---

## Timing Expectations

- **Normal (CORTICAL) commands:** arrive every ~800ms–1s during active navigation
- **EMERGENCY_STOP (REFLEX):** arrives in ~90ms from hazard detection — treat as highest priority
- **Between commands:** robot holds its last state (don't drift or freewheel)

---

## Fallback Behavior

If no command arrives within **2 seconds** of the last one:
- Robot should **STOP** and hold position
- This handles agent crashes, network lag, or processing delays safely

---

## What You Do NOT Need to Know

- How Eshwar's agents decide anything internally
- What the scene description looks like (that's Vision → Conductor)
- What Safety approved or vetoed
- Anything about the reflex arc internals

You just need: `FINAL_COMMAND` in → robot action out.

---

## Checklist Before Integration

- [ ] Eshwar and Adil have agreed on this file
- [ ] Adil's Band subscription filters for `Conductor` + `FINAL_COMMAND`
- [ ] Adil's LiveKit layer maps each `command` value to a robot API call
- [ ] EMERGENCY_STOP is handled as highest priority
- [ ] 2-second timeout fallback implemented (robot stops if no command)
- [ ] Both have tested with a mock `FINAL_COMMAND` message in the Band room before live integration
