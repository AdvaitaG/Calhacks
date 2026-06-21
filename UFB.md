# UFB — Ultimate Bots Hacker Guide
### UC Berkeley AI Hackathon 2026 | June 20–21

> Ultimate Bots is the sports league for Physical AI. This weekend is one of the ways they find the strongest teams. Strong results + commitment → opportunities in the actual league.

---

## Prize Pool — $3,000 Best Physical AI Hack

| Place | Prize |
|-------|-------|
| 1st | $1,500 |
| 2nd | $1,000 |
| 3rd | $500 |

**Judging question (memorize this):** *"Would a real robotics team use it?"*

Judges: UFB engineering + invited partners (Nebius, Reactor, LiveKit, NVIDIA where applicable).

---

## Free $150 Nebius Compute

Every competing team gets a $150 Nebius promo code.
**Claim: reach out to UFB on Slack — "Ultimate Bots" group in Hack Berkeley workspace.**

Enough for a meaningful training pass, synthetic data generations, or a small policy fine-tune.

---

## The Pipeline (Where We Play)

```
Data → Train → Eval → Deploy
```

**Baymax is in Deploy** — serving AI decisions to a robot in real time, closing the observation → decision → action loop.

| Stage | What it means |
|-------|---------------|
| **Data** | Collect or synthesize data the robot learns from |
| **Train** | Turn data into a policy |
| **Eval** | Measure honestly whether it works |
| **Deploy** | Serve policy to robot, get observations back, close the loop ← us |

---

## Robots On-Site

**Limited hardware — start in sim, graduate to hardware once pipeline works.**
Talk to UFB engineers on Slack early if you need real hardware.

| Robot | Notes |
|-------|-------|
| LeRobot SO-101 arms | Manipulation tasks |
| Unitree G1 | Full humanoid |
| Booster K1 | Full humanoid |

Sim is **unlimited** — start there.

---

## Workshop: Saturday Morning

**Nebius Physical AI Workbench** — full session Saturday morning.
Stay for the whole thing. Shortest path from idea to working training/deploy run.

---

## Key Resources

| Resource | Link |
|----------|------|
| Nebius Physical AI Workbench | https://github.com/nebius/nebius-physical-ai |
| Workbench blog | https://nebius.com/blog/posts/run-physical-ai-workflows-not-glue-code |
| LiveKit Portal (teleop + remote inference) | https://github.com/livekit/livekit-portal |
| LiveKit hacker docs | https://www.livekit.info/berkeley-ai-hackathon |
| Reactor (world models API, sub-50ms, $100 credits this weekend) | https://docs.reactor.inc/overview |
| Isaac-GR00T (model + SO-100 walkthrough) | https://github.com/NVIDIA/Isaac-GR00T |
| LeRobot (data format, training, teleop) | https://github.com/huggingface/lerobot |

---

## Nebius Physical AI Workbench — 5 Reference Architectures

1. **Sim-to-Real** — train in Isaac Sim, serve on Nebius, stream actions over LiveKit Portal to real hardware ← closest to us
2. **Eval-as-a-Service** — sim-eval harness, manipulation suite, contact-richness scorer
3. **Data Collection** — synthetic data generation pipeline
4. **Policy Fine-tune** — GR00T N1.7 fine-tuning workflow
5. **Hot-swap** — switch multiple policies mid-task over LiveKit Portal with no pause

---

## Submission Requirements (Devpost, Sunday June 21, 11am)

- **Demo video** — ≤ 3 minutes. Show the robot or sim running.
- **Public repo or doc** — code, dataset, or pipeline
- **200-word writeup** — what you built, what's novel, what's next

---

## Ghost Trials (Side Activity)

Open to everyone. Fun break between commits.

1. Open **https://studio.ultimatebots.com** (free account)
2. Record yourself moving — dance, punches, exercises, freestyle
3. Studio retargets motion to a real Unitree G1 in minutes
4. Go to **Lower Sproul Plaza**, launch on the real robot
5. Get a video back

**Why bother:** top performers get invited to perform live on stage at UFB's **June 26 SF event**. Top standout → invitation to join UFB as a **Ghost** (real role, real comp designing skills for the UFB season).

---

## Where to Find UFB

- **Booth** — sponsor row, MLK Jr. Building. Staffed all weekend.
- **Robots** — Lower Sproul Plaza (running outside)
- **Slack** — "Ultimate Bots" group in Hack Berkeley workspace

**Adil leads the UFB booth visit for our team.**

---

## How Baymax Wins This Prize

We're in the **Deploy** stage. Our pitch to judges:

> *"We built the control layer that closes the loop between AI decisions and robot action. Multiple specialized agents coordinate in real time via Band, stream observations via LiveKit, and the robot executes commands with a sub-100ms reflex arc for safety-critical events. This is the architecture a real robotics team would build — not a monolithic script."*

Key talking points at the booth:
- Real-time closed loop: observation → agents → command → robot → repeat
- Hierarchical architecture with synchronous decision-making (no desync)
- Emergency reflex path bypasses decision stack for safety (~90ms)
- Robot visibly improves between runs (neuroplasticity via the observability layer)
- Social impact: assistive robot for blind people
