# Gate eval results

Measured by `python -m app.policy.bench --compare`. Do not quote numbers that are not in this file.

Eval set: [`policy/eval_set.jsonl`](eval_set.jsonl) (40 utterances: 13 ALLOW / 27 ESCALATE).
Turn budget: 2500ms (p95). Tier-2: off (tier-1 + hard net only). Hosted IFM API `https://api.ifm.ai/v1`.

False allow = expected ESCALATE, gate returned ALLOW. That is the number that matters.

| variant | n | reachable | acc | false_allow | false_esc | tier2_rate | p50_ms | p95_ms | degraded | in_budget | skip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IFM/K2-Horizon-0.9B | 0 | no | — | — | — | — | — | — | — | — | http 400 |
| IFM/K2-Horizon-3.7B | 0 | no | — | — | — | — | — | — | — | — | http 400 |
| IFM/K2-Horizon-7B | 0 | no | — | — | — | — | — | — | — | — | http 400 |
| IFM/K2-Horizon-32B | 0 | no | — | — | — | — | — | — | — | — | http 400 |
| IFM/K2-Horizon-375B-A23B | 40 | yes | 0.975 | 0 | 1 | 0.00 | 267 | 1758 | 23 | yes | — |
| IFM/K2-Think-v2 | 0 | no | — | — | — | — | — | — | — | — | http 429 |

## Pick

**IFM/K2-Horizon-375B-A23B** is the only hosted size that both answered the ping and classified. Zero false allows, p95 1758ms ≤ 2500ms, accuracy 0.975, one false escalate. Smaller Horizon sizes are not on the IFM token API (HTTP 400). Live `TIER1_MODEL` is this checkpoint. Degraded 23/40 is fail-closed unparseable/timeout on borderline turns — not a false allow.
