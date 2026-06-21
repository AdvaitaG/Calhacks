"""
Conductor Agent — Prefrontal Cortex
Reads scene JSON from Vision Agent, decides navigation command,
speaks it aloud to the blind user via macOS TTS.
"""
import json
import os
import subprocess

import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are the prefrontal cortex of Baymax, a humanoid guide robot for visually impaired people.
You receive structured scene data and decide what to tell the blind user walking with the robot.

Output ONLY a valid JSON object:
{
  "command": "stop / go / turn_left / turn_right / slow",
  "spoken_message": "short clear voice instruction for the blind user — max 15 words",
  "urgency": "high / medium / low"
}

Rules:
- spoken_message must be actionable and brief — the person is in motion
- Use "stop" only for immediate threats
- Prioritize safety above all else
- Name objects specifically: "chair", "person", "step" — not "obstacle"
- If path is clear, say something reassuring and directional ("Path is clear, continue straight")
- Output ONLY the JSON object, no other text
"""


def decide(scene: dict) -> dict:
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(scene)}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def speak(message: str) -> None:
    subprocess.run(["say", "-r", "175", message], check=False)


def process_scene(scene: dict) -> dict:
    decision = decide(scene)
    urgency = decision.get("urgency", "?")
    command = decision.get("command", "?").upper()
    msg = decision.get("spoken_message", "")
    print(f"[Conductor] {command} | {msg} | urgency={urgency}")
    speak(msg)
    return decision


if __name__ == "__main__":
    # quick test with a fake scene
    test_scene = {
        "obstacles": ["chair (center path)"],
        "terrain": "flat",
        "crosswalk": False,
        "immediate_threat": True,
        "threat_description": "Chair directly in path 1 meter ahead",
        "scene_summary": "Indoor space with a chair blocking the path ahead.",
    }
    process_scene(test_scene)
