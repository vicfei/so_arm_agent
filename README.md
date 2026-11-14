# RobotAgent

[![CI](https://github.com/vicfei/RobotAgent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vicfei/RobotAgent/actions/workflows/ci.yml)

**Robot Use Agent for SO-ARM101** — no model training: an LLM/VLM (low-frequency
cloud consults) drives deterministic primitives to complete tabletop tasks on the
open-source SO-ARM101.

> Hardware line moved to [RoboHarness](https://github.com/vicfei/RoboHarness)
> (general robotic harness, currently on CreateBlock 5-DOF). This repo keeps the
> SO-ARM101 agent stack: mock closed-loop → 90% real-perception loop.

## Architecture (per docs/06)

```
Task (natural language)
   ▼
Planner: LLM/VLM low-frequency look → primitive sequence + target coords
   ▼
Primitives (deterministic, zero-training): move_to / gripper / push_toward
   ▼
Supervisor: veto power + evidence recording (borrowed from ORA)
   ▼
Executor: TCP bridge → degree-level servo control (mock-first)
   ▼
Verifier: re-shoot a frame → completion check → replan with feedback
```

## The 90% real loop

Perception and planning run on real components — a renderer paints the simulated
desk into real BGR frames, OpenCV does HSV blob detection (measured round-trip
error 0.00 mm), and an LLM planner reads rendered frames to emit primitives
(DeepSeek-Vision, ~13 s per consult). **The only mock part is motor rotation** —
swap in the real TCP executor when the arm is back online; everything else stays
unchanged.

```bash
python3 scripts/run_real_perception_demo.py              # scripted, no network
DEEPSEEK_API_KEY=... python3 scripts/run_real_perception_demo.py --llm
python3 scripts/run_suite.py                             # 5-task success table
```

## Docs

- [docs/06-robot-use-agent-roadmap.md](docs/06-robot-use-agent-roadmap.md) — design baseline (2026-10-20)
- [docs/07-landscape-2026-10.md](docs/07-landscape-2026-10.md) — ecosystem scan (ORA / OpenRUA / HarnessPAI / GenSwarm)

## Status

Mock loop PASS (veto demo + multi-round push convergence, evidence JSONL).
Real-arm executor slot reserved; hardware bring-up tracked in RoboHarness.
