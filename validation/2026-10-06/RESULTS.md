# Round 1 results (checker v0.1, snapshot c8dc98d)

Independent verifier: blind, own code (curl), catalog re-read 04:10–04:12Z, endpoints probed 04:14–04:16Z.
Files: `independent-labels.json`, `comparison.json`, `offline-v0.2.json`, `repeats.jsonl`.

## Is each claim right? (as measured, METHOD.md section 6)

| Claim | In snapshot | Right in sample | 95% interval | Quotable (lower end ≥ 80%) |
|---|---|---|---|---|
| N1 price differs | 159 | 17/20 | 64–95% | no |
| N2 address differs | 7 | 7/7 | 65–100% | no (too few cases) |
| N3 free | 155 | 0/20 | 0–16% | **no: wrong** |
| N4 network name | 159 | 20/20 | 84–100% | yes |
| N5 no Solana option | 64 | 19/20 | 76–99% | no |
| N6 test-network only | 3 | 3/3 | 44–100% | no (too few cases) |
| E HTTP error | 155 | 17/20 | 64–95% | no |
| D no answer | 22 | 10/20 | 30–70% | **no** |
| U unclear | 52 | 9/10 | 60–98% | no |
| ALIVE | 7,022 | 46/50 | 81–97% | yes |

Problems missed among ALIVE: 2 of 50 (1–13%); both were endpoints that stopped answering after the snapshot.

## Why they disagreed (every case read by hand; third check from Brazil 04:21Z)

| Cause | Cases | Detail |
|---|---|---|
| Checker bug | 24 | Template URLs (`:address`) checked as endpoints (15); 200 bodies not read (3); unknown catalog price treated as priced (2); 402 with no details called "no Solana" (1); comparison against a non-standard catalog network name (3) |
| Endpoint changed or intermittent | 16 | agentutility.ai times out and recovers within minutes (8); 502s that became 402 (3); mekler, readx, ai-rook changed (3); agentbit went down after the snapshot (2) |
| Definition unclear | 2 | pay.sh lists no address, so ALIVE could not be confirmed (Nansen, Arkham) |

## Checker v0.2 on the verifier's own saved replies (identical evidence)

144 of 150 judgeable cases agree; 39 are template URLs, now skipped. The 6 left are definition questions (5),
settled in METHOD.md's change log, and one hand call by the verifier (an `"ok": true` reply with no data).
v0.2 was tuned on these cases, so this is **not** evidence of accuracy. Round 2 tests it on a new sample.

## Stability of one check

The same 189 cases re-checked 10 minutes later from Brazil: 177 kept their verdict (94%); 6 of 20 "no answer"
cases were answering. A single "no answer" is not a finding.
