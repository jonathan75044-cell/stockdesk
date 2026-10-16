# Fundamental-data and ticker audit

Checked 2026-10-16 UTC using the deployed service's GET-only Finnhub, SEC and Schwab adapters. No production source files or stored scan results were changed by the diagnostic commands. SEC responses were fetched sequentially without retaining companyfacts.

## Corrections included

- **LRCX:** Finnhub's latest 10-K (2026-06-28, accession 0000707549-26-000037) has no balance-sheet rows. Exact SEC facts in that accession supply equity 12,470,921,000; liabilities 11,058,822,000; current assets 15,610,705,000; current liabilities 5,937,249,000 USD. Enable the existing strict SEC fallback for CIK 0000707549. Live parsing succeeded. [SEC facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000707549.json)
- **PANW:** Finnhub's 2026-07-31 10-K (0001327567-26-000023) also has no balance-sheet rows. Exact SEC facts supply equity 27,492,000,000; liabilities 20,968,000,000; current assets 8,643,000,000; current liabilities 9,923,000,000 USD. Enable fallback for CIK 0001327567. Live parsing succeeded; the current ratio is approximately 0.871, so recovering data does not imply qualification. [SEC facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001327567.json)
- **TGT:** The 2026-01-31 10-K (0000027419-26-000016) reports LiabilitiesCurrent 21,230,000,000 and LiabilitiesNoncurrent 22,095,000,000 USD. Their sum is 43,325,000,000. Use these explicit non-overlapping components when the total is absent; do not infer missing noncontrolling interest. The current ratio is approximately 0.942 and liabilities/equity approximately 2.680. [SEC facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000027419.json)
- **BRK-B:** SEC identifies Berkshire Class B as BRK-B; Schwab returned a quote only for BRK/B in the comparison request. Normalize BRK-B and BRK/B to dashboard symbol BRK.B, deduplicate the scan universe, and translate to BRK/B for Schwab. Apply the same identity to reviews and alert allowlists. [SEC ticker directory](https://www.sec.gov/files/company_tickers.json)
- **NUFG:** No SEC ticker match or Schwab quote. MUFG is Mitsubishi UFJ Financial Group (CIK 0000067088), and Schwab returned its ADR quote. The user explicitly confirmed replacing NUFG with MUFG. Normalize this confirmed typo in the configured universe and deduplicate existing MUFG entries. [SEC submissions](https://data.sec.gov/submissions/CIK0000067088.json)

## Remaining exclusions

| Symbols | Finding | Treatment |
|---|---|---|
| JPM, WFC | Bank revenue is reported as RevenuesNetOfInterestExpense. WFC also reports fee revenue under the general customer-revenue tag, which is not total bank revenue. Their cash-flow reports do not supply the ordinary corporate capex/current-ratio evidence required by this screen. | Sector-specific financial rules are needed; do not force industrial-company mappings or substitute securities purchases for capex. |
| PGR | Insurance balance sheet lacks AssetsCurrent in the returned annual report. | Do not substitute total assets for current assets. |
| DE | Exact latest SEC accession 0001104659-25-122321 contains Assets and Liabilities but no AssetsCurrent or LiabilitiesCurrent facts in the checked USD taxonomy. | Keep the current-ratio exclusion; no unsupported sum of assets. |
| BKNG | The scan reports negative equity of -5,578,000,000. | This is a ratio eligibility failure, not a missing-tag problem. |
| TSM, ASML, ARM, SMFG | Finnhub returned no annual periods. SEC identifies their latest annual filings as 20-F, while the current fallback/automatic valuation supports 10-K. SMFG is also a financial issuer. | A separate validated foreign-issuer/ADR and, where applicable, sector model is required. |
| SPCX | SEC identifies CIK 0001181412 as Space Exploration Technologies. No 10-K, 20-F or 40-F was present in the recent submissions inspected; Finnhub supplied no annual periods. | Do not substitute an unrelated issuer or claim two annual periods exist. |

Primary SEC submissions: [DE](https://data.sec.gov/submissions/CIK0000315189.json), [TSM](https://data.sec.gov/submissions/CIK0001046179.json), [ASML](https://data.sec.gov/submissions/CIK0000937966.json), [ARM](https://data.sec.gov/submissions/CIK0001973239.json), [SMFG](https://data.sec.gov/submissions/CIK0001022837.json), [SPCX](https://data.sec.gov/submissions/CIK0001181412.json).

## Scope and verification

These corrections repair quality-data retrieval and ticker identity. They do not relax screening thresholds or guarantee an intrinsic value or Undervalued %: automatic valuation independently requires matched cash flows, financing evidence, shares and a supported model. Financial-sector and foreign-issuer valuation exclusions remain.

Live checks confirmed the LRCX/PANW fallback, TGT component sum and Schwab ticker responses. Regression tests cover component completeness, signs, conflicting values, custom-tag rejection, fallback provenance/failure, canonical symbols, alert allowlists and configured-universe normalization. A fresh scan after deployment is still required to verify the complete dashboard.
