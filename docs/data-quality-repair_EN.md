# Quote quality repair

HK realtime fetching first tries a single-symbol Eastmoney endpoint with decimal fields, two bounded attempts and a provider timestamp, retaining the existing fallbacks. Daily volume is converted from lots to shares only when turnover and OHLC validate the unit. Invalid volume metrics display N/A without a percent suffix. Unavailable market breadth is omitted from model input. Sina fallback attribution is corrected.

379 focused project tests pass. The public endpoint returned valid HK fields through curl; Python requests failed in the local network environment. GitHub Actions and email delivery still require deployment verification. Restore the original files to roll back.

Valid HK single-symbol quotes retain their timestamp and range even without optional volume metrics. Missing realtime open/high/low stay missing; last price and previous close must not fabricate session OHLC or zero amplitude.

The daily workflow defaults to a 600-second per-stock budget when unset, allowing bounded public-source fallbacks. Explicit settings remain authoritative. A failed stock now fails the workflow; reports and logs still upload via always().
