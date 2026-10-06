# How we test whether the checker is right

*Written and committed on 2026-10-06 before any sampled case was examined. The commit time is the proof.
Changes after that date are listed at the bottom with their reason.*

The checker is a measuring instrument. Before any of its counts is quoted, we measure how often it is
wrong, against cases checked independently.

## 1. What is being tested

The frozen snapshot is commit `c8dc98d` (2026-10-06):

- Catalog side: `data/endpoints.json`, collected 2026-10-06T03:50:36Z (7,951 endpoints).
- Checker side: `data/latest.json`, checks run between 03:50Z and 04:05Z (7,787 endpoints checked).

Each checked endpoint has one verdict and zero or more notes. Unit of analysis: one endpoint (method + URL).

## 2. Definitions, fixed in advance

All prices are compared as USD amounts of USDC (mint `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`,
6 decimals). An option priced in any other asset is out of scope for price claims and is reported separately.

"Mainnet option": a payment option in the endpoint's 402 reply whose network is `solana` (x402 v1) or
`solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` (CAIP-2), or any other identifier that is clearly meant as mainnet
(e.g. `solana:mainnet`); the identifier `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` and `solana-devnet` are
test network. An unrecognised identifier is recorded as such.

A claim is **true** for an endpoint when the independent check, made from the reply and the catalog entry as
defined here, reaches the same conclusion.

| Code | Claim made by the checker | True only if |
|---|---|---|
| ALIVE | Answers with a Solana mainnet price | The reply is HTTP 402 with at least one mainnet option, its price and address match the catalog's mainnet option, and nothing in N1–N7 applies |
| N1 PRICE | "Asks X but the catalog says Y" | No mainnet USDC option in the reply has the same amount as any mainnet USDC option in the catalog entry |
| N2 ADDRESS | "Payment address differs from the catalog" | No mainnet option's `payTo` in the reply equals any mainnet option's `payTo` in the catalog entry |
| N3 FREE | "Answered without asking for payment" | A request with no payment gets HTTP 2xx **and** the body is a real answer (not an error, not empty), **and** the catalog price is above $0 |
| N4 NETWORK | "Network name is not standard" | The reply's Solana network identifier is neither `solana` nor `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` |
| N5 NO-SOLANA | "Asks for payment but offers no Solana option" | Reply is HTTP 402 and lists payment options, none on any Solana network |
| N6 TEST-ONLY | "Only accepts test-network money" | Reply is HTTP 402, has Solana options, all of them test network |
| E HTTP | "HTTP NNN" (error) | The reply's status code is NNN (≥ 300, not 402) for a GET, or for a POST other than 400/422 |
| U UNCLEAR | Refused an empty POST (400/422) or rate-limited (429) | Same status for the same request |
| D NO-ANSWER | No reply within 10 seconds | No HTTP status within 10 seconds |

Note on N4: the checker's note adds "some wallets cannot pay it". That consequence is **not** tested here and
must not be quoted as a finding until tested separately.

Note on N3: an HTTP 200 whose body is an error is not "free"; it is recorded as a hidden error (the 5 October
Heurist pattern) and counts against N3.

## 3. Sample, drawn before looking

Random seed: **20261006**. Sampling is stratified by the checker's claim. An endpoint with several notes enters
each stratum it qualifies for; draws are without replacement within a stratum.

| Stratum | Population in snapshot | Drawn |
|---|---|---|
| N2 ADDRESS | all | all |
| N6 TEST-ONLY | all | all |
| N1 PRICE | all | 20 |
| N3 FREE | all | 20 |
| N4 NETWORK | all | 20 |
| N5 NO-SOLANA | all | 20 |
| E HTTP | all | 20 |
| D NO-ANSWER | all | 20 (or all if fewer) |
| U UNCLEAR | all | 10 |
| ALIVE | all | 50 |

The ALIVE draw estimates how many problems the checker **misses**.

## 4. The independent check

- Done by a separate agent that has **not** seen the checker's code, its verdicts, or this sample's strata.
  It receives only: this file's section 2, and a list of (method, URL).
- It writes its own code, using `curl` (a different HTTP client from the checker's Python `urllib`).
- It re-reads the catalog entry itself from the Bazaar and pay.sh public APIs.
- It sends the same request shape as the checker: GET with no body, or POST with body `{}` and
  `Content-Type: application/json`; no payment header; 10-second timeout.
- It saves every raw reply (status, headers, body up to 64 KB) and every catalog entry it used.

Because the independent check runs later than the snapshot, a disagreement can be a real change at the endpoint.
Every disagreement is therefore re-checked a third time and read by hand, and assigned one cause:
checker bug, verifier bug, endpoint changed, catalog changed, definition ambiguous, or unknown.

## 5. Human labels

20 cases drawn at random (same seed + 1) from the sample are given to a person (Leticia or Ernani) as raw
evidence only: request, reply, decoded payment options, catalog entry. No verdict is shown. The person labels
each case against section 2. We report how often person and independent check agree (raw agreement and
Cohen's kappa).

## 6. What is reported

For each claim: right in X of Y sampled cases, with a 95% Wilson interval.

For ALIVE: problems missed in X of 50, with a 95% Wilson interval.

## 7. Rules for quoting a number

- A claim's count may be quoted only if the lower end of its 95% interval is at least **80%**.
- Otherwise the checker is fixed and the claim re-tested on a **new** sample (seed + 2) from a new snapshot.
- Fixing the checker never changes a past result; old and new results are both kept.
- Single-check results are labelled "seen once". A problem is called persistent only when seen in at least 3
  of 4 checks over 24 hours, from two places (GitHub's runners in the US, and a machine in Brazil).

## 8. Known weaknesses, stated before testing

| Weakness | Effect |
|---|---|
| A check is one request at one moment | Transient failures look like real ones; handled by the persistence rule |
| All checks come from one data center | Region or data-center blocking looks like an error |
| POST endpoints get an empty body | Some refuse before asking for payment (counted as UNCLEAR, not as broken) |
| The catalog is read up to 15 minutes before the check | A price or address change in between looks like a mismatch |
| Catalog pagination may skip or repeat items | Affects coverage (which endpoints exist), not the accuracy of a verdict |
| Per-check timestamp is the run's start time, not the request time | Times are accurate to about 15 minutes |
| The checker reads at most 64 KB of each reply | A payment option beyond 64 KB would be missed |

## Changes after 2026-10-06

None yet.
