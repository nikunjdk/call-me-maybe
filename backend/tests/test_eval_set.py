import json
from pathlib import Path

EVAL = Path(__file__).resolve().parents[2] / "policy" / "eval_set.jsonl"


def test_eval_set_shape() -> None:
    rows = [json.loads(line) for line in EVAL.read_text().splitlines() if line.strip()]
    assert len(rows) == 40
    expected_ok = {"ALLOW", "ESCALATE"}
    triggers = {"money", "authorization", "identity", "ambiguity", "none"}
    ids: set[str] = set()
    allow = escalate = 0
    for row in rows:
        assert set(row) >= {"id", "utterance", "expected", "trigger"}
        assert row["id"] not in ids
        ids.add(row["id"])
        assert row["expected"] in expected_ok
        assert row["trigger"] in triggers
        assert row["utterance"].strip()
        if row["expected"] == "ALLOW":
            assert row["trigger"] == "none"
            allow += 1
        else:
            escalate += 1
    assert allow == 13
    assert escalate == 27
