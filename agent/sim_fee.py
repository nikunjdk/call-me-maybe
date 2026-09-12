"""Fee-line soak: simulate a rep saying $150 change fee; expect escalate tool."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")

API = "https://api.elevenlabs.io/v1"
aid = os.getenv("ELEVENLABS_AGENT_ID")
key = os.getenv("ELEVENLABS_API_KEY")
if not aid or not key:
    sys.exit("missing ELEVENLABS_* env")

body = {
    "simulation_specification": {
        "simulated_user_config": {
            "prompt": {
                "prompt": (
                    "You are a brief airline rep. First reply after the AI speaks: "
                    "there is a $150 change fee. Then say nothing else useful."
                ),
                "llm": "gpt-4o-mini",
                "temperature": 0.0,
            }
        },
    },
    "extra_evaluation_criteria": [
        {
            "id": "calls_escalate",
            "name": "Calls escalate",
            "conversation_goal_prompt": (
                "The agent called the escalate tool after hearing about a fee."
            ),
            "use_knowledge_base": False,
        }
    ],
}

r = httpx.post(
    f"{API}/convai/agents/{aid}/simulate-conversation",
    headers={"xi-api-key": key, "Content-Type": "application/json"},
    json=body,
    timeout=300.0,
)
print("status", r.status_code)
data = r.json()
out = ROOT / "agent" / "config" / "last_sim.json"
out.write_text(json.dumps(data, indent=2)[:100000], encoding="utf-8")

blob = json.dumps(data).lower()
hit = "escalate" in blob and ("tool" in blob or "function" in blob)
print("escalate_signal", hit)
print("wrote", out)
if r.status_code >= 400:
    sys.exit(1)
