# Solana Endpoint Record

Every paid Solana endpoint we can find, checked every hour without paying.

- **What a check is.** The request an agent sends before paying. A working x402 endpoint answers
  `402 Payment Required` with its price and payment address. We record the answer, the price, where
  the money goes, and how long it took. **Checks never pay.**
- **Where endpoints come from.** The Coinbase Bazaar discovery API and the pay.sh catalog, refreshed daily.
- **How often.** Hourly for endpoints with 10 or more payers in the last 30 days and everything on
  pay.sh; daily for the rest. Free endpoints, endpoints that need path parameters, and methods that
  change data (DELETE, PATCH, PUT) are skipped. POST endpoints get an empty JSON body.
- **Paid checks.** Occasionally we buy one call and read the answer, to see whether it was real or an
  error dressed as a success. Each one is listed with its transaction in `data/paid_checks.json`.

## Verdicts

| Verdict | Meaning |
|---|---|
| alive | Answered with a Solana mainnet price |
| warning | Answered, but something is off: test-network money only, non-standard network name, price or address differs from the catalog, or served without asking for payment |
| unclear | Refused our empty test request, or asked us to slow down |
| error | Any other HTTP error |
| down | No answer within 10 seconds |

## Run it yourself

Python 3.9+, standard library only.

```
python3 record/collect.py        # refresh data/endpoints.json from the catalogs
python3 record/knock.py hourly   # or: daily
python3 record/page_data.py      # build data/page.json for index.html
```

If your endpoint is listed and you would rather we check it less often, open an issue.
