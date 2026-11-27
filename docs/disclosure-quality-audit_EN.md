# Disclosure quality repair

For 000002 and HK02015, add public disclosure/news collection independently of paid search keys, label issuer releases, announcement indexes and secondary sources separately, and flag newer periods than the structured financial table. Preserve original currencies and prohibit cross-currency quarter derivation. Prevent TTM values filling missing quarterly fields and require matching cashflow periods. Prefer same-quote previous close and separate realtime volume ratio from previous-full-day comparisons. Surface collection failures instead of reporting no announcements.

335 focused tests pass. Live public-news collection found the Q3 announcement and financial crosscheck returned 2026-09-30. The issuer site failed local certificate/access checks; verification was not bypassed. Deployment verification is recorded in repository Actions; check disclosure evidence, report-period warnings and mail delivery logs. Restore affected files from 838af322da7d5458c881934212a07fe3c415ca94 to roll back.

When currency labels conflict between periods, the financial cross-check exposes only period metadata, quarantines monetary values and ratios, and forbids their use or derivation. Secondary financial tables must not be presented as issuer disclosures.

If a streaming response explicitly ends with length/max_tokens, reuse the existing single non-stream recovery with a bounded larger budget (up to 16384). Truncated or invalid JSON is never accepted as a successful analysis.
