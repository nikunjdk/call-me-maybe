"""Sync /agent config + prompt + escalate tool to ElevenLabs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
load_dotenv(ROOT / "backend" / ".env")
load_dotenv(ROOT / "backend" / ".env.local", override=True)

API = "https://api.elevenlabs.io/v1"


def main() -> None:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY missing")
    headers = {"xi-api-key": key, "Content-Type": "application/json"}

    cfg = json.loads((AGENT_DIR / "config" / "agent.json").read_text(encoding="utf-8"))
    agent_id = os.getenv("ELEVENLABS_AGENT_ID") or cfg["agent_id"]
    prompt = (AGENT_DIR / cfg["prompt_file"]).read_text(encoding="utf-8")
    tool_cfg = json.loads(
        (AGENT_DIR / "config" / "tools" / "escalate.json").read_text(encoding="utf-8")
    )
    base = (
        os.getenv("AGENT_WEBHOOK_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or os.getenv("BACKEND_PUBLIC_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")
    tool_cfg["api_schema"]["url"] = tool_cfg["api_schema"]["url"].replace(
        "{{AGENT_WEBHOOK_BASE_URL}}", base
    )

    placeholders = {
        "session_id": "demo-session",
        "opening_script": "Cancel the booking on the approved plan.",
        "goal": "cancel this flight",
        "passenger_name": "Alex Chen",
        "pnr": "ABC123",
        "airline": "United",
        "flight_number": "UA 482",
        "flight_date": "September 18",
        "route": "SFO-EWR",
        "ticket_class": "Economy",
    }

    with httpx.Client(timeout=60.0, headers=headers) as client:
        tool_id = cfg.get("escalate_tool_id")
        if tool_id:
            tr = client.patch(
                f"{API}/convai/tools/{tool_id}", json={"tool_config": tool_cfg}
            )
            if tr.status_code >= 400:
                tool_id = None
        if not tool_id:
            tr = client.post(f"{API}/convai/tools", json={"tool_config": tool_cfg})
            tr.raise_for_status()
            tool_id = tr.json()["id"]

        patch_body = {
            "conversation_config": {
                "tts": {
                    "voice_id": cfg["voice_id"],
                    "model_id": cfg["tts_model_id"],
                },
                "agent": {
                    "first_message": cfg["first_message"],
                    "prompt": {"prompt": prompt, "tool_ids": [tool_id]},
                    "dynamic_variables": {
                        "dynamic_variable_placeholders": placeholders
                    },
                },
                "conversation": {
                    "turn_timeout": cfg.get("turn_taking", {}).get("turn_timeout", 7),
                },
            }
        }
        ur = client.patch(f"{API}/convai/agents/{agent_id}", json=patch_body)
        ur.raise_for_status()

    cfg["escalate_tool_id"] = tool_id
    cfg["webhook_base_url"] = base
    cfg["transcript_webhook_path"] = "/agent/elevenlabs/event"
    (AGENT_DIR / "config" / "agent.json").write_text(
        json.dumps(cfg, indent=2) + "\n", encoding="utf-8"
    )
    print(f"ok agent={agent_id} tool={tool_id} webhook={base}")
    print(
        f"Configure ElevenLabs post-call / conversation webhook → "
        f"{base}/agent/elevenlabs/event"
    )


if __name__ == "__main__":
    main()
