# Round 4 results (checker v0.4, snapshot d96e085)

Literal-agent levels only (METHOD.md, "Round 4"). Snapshot checks ran 19:00–19:15Z on GitHub; the blind verifier
re-read the catalogs and probed at about 19:30Z with its own code (curl, redirects followed, POST body exactly `{}`
unless the listing gives one). Third checks by hand at 19:36Z. The waiting-list part names unaccepted sellers and is
kept private; its sample's SHA-256 is in `waitlist-sample.sha256.txt`.

## Is each level right? (as measured, strict; lenient identical)

| Level | In snapshot | Agree in sample | 95% interval | Quotable |
|---|---|---|---|---|
| L0 cannot build the request from the listing | 155 | 40/40 | 91–100% | **yes** |
| L1 no payment request | 307 | 21/40 | 37–67% | no |
| L2 payable but differs from the listing | 342 | 40/40 | 91–100% | **yes** |
| L3 reaches a correct payment request | 7,162 | 50/50 | 93–100% | **yes** (third round in a row) |

MPP challenges (change 22): both instruments saw the same 3 in the catalog sample.

## Why L1 disagreed (all 19 read by hand)

| Cause | Cases | Detail |
|---|---|---|
| Endpoint intermittent | 9 | All were "L1 (seen once)": no answer during the daily run (one host failed on 70 endpoints at once), a 402 twenty minutes later. Re-checked by hand at 19:36Z: 402. Under section 9 a seen-once L1 is not a persistent failure |
| Definition gap | 10 | One seller's listing gives a description as the example value ("EVM wallet address (0x-prefixed, 40 hex characters)"). The checker sends it literally and gets HTTP 400 (L1); the verifier treated it as "described only" (L0). Both say the agent fails; they differ on which level |
| Checker bug | 0 | |

Among the 28 sampled L1s that were not "seen once", the only disagreements are the 10 description cases.

## Proposed for round 5 (not yet in METHOD.md; needs to be fixed before drawing)

1. Section 9: a path value that is a description, not a usable value, counts as "described only" (L0), with a fixed
   rule for recognising one.
2. The L1 stratum samples persistent L1s; seen-once L1s are reported apart, as section 9 already says.

## What can be said now

- "Of the Solana listings in Coinbase Bazaar and pay.sh, about 90% reach a correct payment request for an agent
  that follows the listing exactly; the check agreed with an independent verifier in 50 of 50, 49 of 50 and 47 of
  50 cases across three blind rounds."
- "155 listings cannot be followed at all: the request can't be built from what the listing gives (40 of 40 agreed,
  91–100%)."
- "342 answer with a payment request that differs from the listing: price, network name or token (40 of 40, 91–100%)."
- Not yet: how many give no payment request at all (L1).
