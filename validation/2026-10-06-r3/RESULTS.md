# Round 3 results (checker v0.3, snapshot ff2b8ce)

Blind verifier with its own code (curl, redirects followed), catalogs re-read and endpoints probed 06:50–07:06Z;
snapshot checks ran 05:36–06:02Z. Third checks by hand at about 07:15Z. The waiting-list part of round 3 names
unaccepted sellers and is kept private; its sample's SHA-256 is in `waitlist-sample.sha256.txt`.

## Is each claim right? (as measured)

| Claim | In snapshot | Right in sample | 95% interval | Quotable |
|---|---|---|---|---|
| N1 price differs from the listing | 350 | 20/20 | 84–100% | **yes** (also round 2) |
| N4 non-standard network name | 163 | 20/20 | 84–100% | **yes** (rounds 1, 2, 3) |
| N5 listed as Solana, offers no Solana option | 62 | 20/20 | 84–100% | **yes** (also round 2) |
| E HTTP error | 26 | 20/20 | 84–100% | **yes** |
| ALIVE | 6,635 | 47/50 | 84–98% | **yes** |
| Literal agent L3: reaches a correct payment request | 6,985 | 49/50 | 90–100% | **yes** (also round 2) |
| Literal agent L0: cannot build the request | 163 | 19/20 | 76–99% | no (just below) |
| Literal agent L1: no payment request | 204 | 18/20 | 70–97% | no |
| Literal agent L2: payable but wrong | 552 | 19/20 | 76–99% | no (just below) |
| U unclear | 104 | 8/20 | 22–61% | no (see below) |
| N3, D, N2, N6 | 12, 8, 7, 3 | 7/12, 3/8, 7/7, 2/3 | — | no |

## Why they disagreed (all 31 read by hand)

| Cause | Cases | Detail |
|---|---|---|
| Endpoint changed or intermittent | 14 | Timeouts that recover (agentutility, mekler, agentbit, accelerometer: 9); two listings gone from the catalog; unykorn updated its listed price; one endpoint that went from free to 402 |
| **Verifier error** | 12 | It sent POSTs with an empty body; the definition says `{}`. Re-sent by hand with `{}` at 07:15Z: all 12 refuse or return an error body, as the checker recorded. With an empty body they ask for payment |
| Definition gap | 4 | "Help" pages returned as 200 (3); an MPP challenge counted by the verifier as a Solana option (1) |
| Checker bug | 1 | OpenAPI parameters given by `$ref` are not read (same bug as in the waiting list) |

After adjudication U would read 20 of 20, but that relies on our own re-check, so the as-measured figure stands
for the quoting rule.

## What can be said now

- "Of 7,918 Solana listings in Coinbase Bazaar and pay.sh, about 90% reach a correct payment request for an agent
  that follows the listing exactly. When the check says so it is right 90–100% of the time (two blind rounds)."
- "Wrong prices, non-standard network names and listings that offer no Solana option are each measured correctly
  in 20 of 20 sampled cases" (counts: 350, 163 and 62 endpoints on 6 October).
- The failure levels L0–L2 are within reach (76%, 70% and 76% lower bounds) but not quotable yet.
