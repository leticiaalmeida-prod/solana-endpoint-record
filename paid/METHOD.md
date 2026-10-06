# Paid tests: method (fixed 2026-10-06, before any purchase)

*Committed before the first paid call. The commit time is the proof. Changes are listed at the bottom with their
reason. Results name sellers and are kept private until Leticia decides to publish them.*

## 1. Bundles: does a published multi-seller recipe finish?

agentic.market lists four "bundles": recipes that chain several paid services into one job, each with a stated cost
per run and a stated success rate written by the bundle's author ("4/5", "5/5"). We run three of them as published.
IPO Analysis is left out: its paid steps are optional enrichments around free SEC reading, so a run has no fixed
paid shape.

**How a run is made.** `bundles.py` follows each recipe's steps in order with fixed inputs listed in the code (25
questions for Market Research, 25 role and location pairs for Talent Market Scanner, 25 separate Morning Briefings).
Where the recipe asks an AI agent to choose, a fixed rule replaces the choice:

| Recipe step that needs a choice | Fixed rule |
|---|---|
| Market Research: "if company is public" | A ticker is given for 14 of the 25 questions |
| Morning Briefing: "pick the single most important story" | The first headline in toon.haus Market News |
| Talent Market Scanner: "top 2–3 public companies" for stock quotes | Not run (optional in the recipe; needs a name-to-ticker choice) |
| Exa Contents (optional fallback in two recipes) | Not run |

The final write-up (the "brief") is produced by the buyer's own AI, not bought, and is not graded.

**Network.** Every required step of every bundle accepts only Base (free first look, 6 Oct), so the runs pay from a Base
wallet through the PayBox CLI (`use-service`, gateway mode).

**Before every purchase** the step is requested once without payment to read its price. The purchase is refused if the
price is over **$0.10**, the seller is not on the approved list (blockrun.ai, parallelmpp.dev, finance.toon.haus,
api.seerium.xyz, stablejobs.dev), or the batch would pass the budget Leticia approved for it.

## 2. Delivery rules (each paid step)

| # | Rule | Fails when |
|---|---|---|
| D1 | The money moved as asked | No USDC transfer from our Base wallet to the 402's `payTo` for the asked amount, read from Base, not from PayBox |
| D2 | The seller answered | No answer within the CLI's timeout, or an HTTP error after paying |
| D3 | Something came out | Empty body, `{}`, `[]` or `null` |
| D4 | Not an error in disguise | A success whose body carries `error`, `errors`, `ok: false`, `success: false`, a status of error or failed, or an upstream 402 |
| D5 | The promised shape | The service's own description names output fields (e.g. results, headlines, jobs) and they are missing or empty |

A step is **delivered** when D1–D5 all hold. Verdicts otherwise: not delivered (D2–D5), paid not settled (D1 fails,
answer served), settled not served (D1 holds, D2 fails).

## 3. Per run

- **Finished**: every *required* step of the recipe delivered. A required step the marketplace does not list (Morning
  Briefing's "Orbis Crypto Sentiment") is reported as missing; the run is scored both ways, with it counted as failed
  (the recipe as published) and without it (the steps that exist).
- **Money wasted**: dollars paid on a run that did not finish.
- **Real cost**: dollars paid per run, against the recipe's stated cost per run.

Reported per bundle: finished X of N with a 95% Wilson interval, next to the recipe's own claim.

## 4. Checking the grader

A second agent, blind to our grades, grades a random 30 saved step responses (seed 20261018) from the saved bodies,
with sections 2 and 3 only. Nothing is bought again. Agreement is reported with its interval; under 80% at the lower
end, the rules are fixed and re-graded before any figure is quoted.

## 5. Budget and approval

Pilot: one run of each bundle (about $0.30). Then the rest in batches, each with Leticia's go and a budget. Expected
total about $7.50 for 25 runs of three bundles.

## Changes

| # | Change | Why |
|---|---|---|
| P1 | New step verdict: **could not pay**, when the seller rejects the wallet's payment and nothing is charged (confirmed on Base). It counts as not delivered for the run, and is reported apart from seller failures | Pilot, 6 Oct 22:10Z: BlockRun's payment check (Coinbase's) rejected all three PayBox payments ("paymentPayload is invalid"); Base shows no charge for them |
| P2 | Bug fix: the Morning Briefing top story is read from toon.haus's answer body (`news[0].headline`); the pilot read the wallet's wrapper and skipped the deep-dive steps | Pilot, 6 Oct |
