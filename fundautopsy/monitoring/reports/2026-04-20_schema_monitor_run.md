# SEC Schema Monitor — Run Report

**Run timestamp:** 2026-04-20 (UTC)
**Test target:** AGTHX (American Funds Growth Fund of America)
**Verdict:** No SEC schema break detected. Three of four "failures" trace to bugs inside the monitor itself, not changes at the SEC. The production parsers (`fundautopsy/data/ncen.py`, `fundautopsy/data/nport.py`) are unaffected.

---

## Headline summary

| Check | Initial result | True root cause | SEC schema actually changed? |
|---|---|---|---|
| EDGAR Submissions API | FAIL (404) | Wrong test CIK constant in monitor (`2798` vs correct `44201` for AGTHX) | No |
| MF Tickers API | PASS | — | No |
| N-CEN XML Schema | FAIL (XML parse error) | Two monitor bugs (see below) | No |
| N-PORT XML Schema | FAIL (XML parse error) | One monitor bug (see below) | No |

After fixing the test CIK to `44201`, EDGAR Submissions and MF Tickers both pass cleanly. The N-CEN and N-PORT XML failures are caused by (a) a primary-document fetch bug and (b) expected-element paths that never matched the live SEC schema in the first place. The production parsers do not share these bugs.

---

## Finding 1 — Wrong test CIK in `schema_monitor.py` (pre-existing bug, not SEC change)

`TEST_CIK = 2798` returns 404 from `data.sec.gov/submissions/CIK0000002798.json`. The MF Tickers feed cleanly resolves AGTHX to **CIK 44201** (confirmed live this run). 2798 was never the correct CIK for Growth Fund of America. This bug had been masking every check that depends on the submissions endpoint.

**Fix already applied during this run** (otherwise no useful validation could happen):

```python
# fundautopsy/monitoring/schema_monitor.py
TEST_CIK = 44201   # was 2798
```

A second small bug — the `SchemaCheckResult` dataclass had `passed: bool` with no default but was instantiated without it — was also fixed (`passed: bool = False`) so the script could even start.

## Finding 2 — Monitor does not handle SEC's XSL-prefixed `primaryDocument` (monitor bug)

The EDGAR submissions API returns `primaryDocument` like `xslFormN-CEN_X01/primary_doc.xml`. Fetching that URL returns the **XSLT-rendered HTML preview**, not the raw XML — strict XML parsing fails on the HTML doctype. The raw XML lives at `primary_doc.xml` (no XSL prefix) in the same accession directory.

This is **not a SEC change**. The production N-CEN and N-PORT parsers already handle exactly this case:

```python
# fundautopsy/data/nport.py:67-74 (mirrored in ncen.py)
# The primary_document field often points to an XSLT-rendered
# HTML version (e.g. xslFormNPORT-P_X01/primary_doc.xml).
# We need the raw XML, which is always at primary_doc.xml
# in the filing's root directory.
doc_candidates = ["primary_doc.xml"]
```

The monitor's `download_filing_xml` call uses `filing.primary_document` verbatim and never falls back. Suggested fix: in `check_ncen_schema` and `check_nport_schema`, mirror the parser's fallback ladder, or pass `primary_document="primary_doc.xml"` explicitly when the API returns an XSL-prefixed value.

**Verified directly:**
- `…/000119312525282335/xslFormN-CEN_X01/primary_doc.xml` → HTML (242 KB), starts with `<!DOCTYPE html …>`
- `…/000119312525282335/primary_doc.xml` → XML (52 KB), starts with `<?xml version="1.0" …>`, root `{http://www.sec.gov/edgar/ncen}edgarSubmission`, schema version `X0505`

## Finding 3 — Monitor's expected N-CEN element paths never matched the real schema (monitor bug)

When fetched against the **raw XML**, four of seven monitor-expected N-CEN paths still come up missing — but every one of them is a typo or wrong-form name in the monitor, not a missing element. Live element names from `X0505` N-CEN, with what the monitor expects:

| Monitor expects | Lives in live XML as | Notes |
|---|---|---|
| `genInfo/seriesId` | `headerData/seriesClass/seriesInfo` and `formData/managementInvestmentQuestionSeriesInfo/mgmtInvSeriesId` | `genInfo` is N-PORT's element name; N-CEN uses `generalInfo` (no series child) |
| `brokerCommissions` | `broker`, `grossCommission`, `aggregateCommission` (discrete elements, no wrapper) | Production parser correctly reads `aggregateCommission` and iterates `grossCommission` |
| `administrator` | `admins/admin/adminName` | Production parser correctly reads `adminName` |
| `securitiesLending` | `securityLending` / `securityLendings` / `isFundSecuritiesLending` / `netIncomeSecuritiesLending` | Singular `security…`, not plural `securities…` |

Three of seven paths the monitor expects (`investmentAdviser`, `custodian`, `transferAgent`) do exist in the live XML and pass. So this is partial alignment — the monitor was hand-rolled with educated guesses rather than against actual filings.

**Recommended fix:** rewrite `NCEN_EXPECTED_PATHS` against the elements the production parser actually consumes, e.g.:

```python
NCEN_EXPECTED_PATHS = [
    ".//generalInfo",
    ".//seriesClass/seriesInfo",
    ".//aggregateCommission",
    ".//grossCommission",
    ".//admin/adminName",
    ".//securityLending",
    ".//investmentAdviser",
    ".//custodian",
    ".//transferAgent",
]
```

## Finding 4 — N-PORT schema is fully intact

When fetched against the raw XML (bypassing Finding 2), all six expected N-PORT element paths resolve under the namespace wildcard:

```
.//invstOrSec  PRESENT
.//name        PRESENT
.//valUSD      PRESENT
.//assetCat    PRESENT
.//totAssets   PRESENT
.//repPdEnd    PRESENT
```

Sample filing: accession `0001193125-26-027715`, filed 2026-01-29, root `{http://www.sec.gov/edgar/nport}edgarSubmission`. **No N-PORT schema change.**

---

## What this means for the production parsers

**Nothing is broken in production.** The live N-CEN (X0505) and N-PORT XML feeds expose all the elements `data/ncen.py` and `data/nport.py` consume, and both parsers already defensively fall back to `primary_doc.xml` when the API returns the XSL-prefixed document path. The Fund Autopsy pipeline should still parse AGTHX (and structurally similar funds) end-to-end against the current SEC feed.

**The monitor itself, however, cannot currently catch a real schema break.** Three of four checks failed for cosmetic reasons during this run; if the SEC actually shipped a breaking N-CEN element rename next quarter, the monitor would fail the same way and the change would be lost in the noise.

---

## Recommended follow-ups (priority order)

1. **Re-align `NCEN_EXPECTED_PATHS` to elements the parser actually reads** (Finding 3). Without this, the monitor cannot distinguish a real schema break from its own out-of-date expectations. See suggested list above.
2. **Make the monitor's XML fetches mirror the parser's primary-document fallback** (Finding 2). Either prefer `primary_doc.xml` directly or fall back to it when the API returns an `xslForm…` path.
3. **Lock in the corrected `TEST_CIK = 44201`** (Finding 1). Already applied in this run — keep it.
4. **Optional:** add a sanity assertion that `xml_bytes` does not begin with `<!DOCTYPE html` before parsing, mirroring the parser's "must be XML, not HTML" guard.

None of these require coordination with the SEC. All are local repairs.

---

## Run mechanics / autonomous-run notes

- Script could not run as-shipped: `SchemaCheckResult.passed` had no default, so even constructing a check raised `TypeError`. Patched to `passed: bool = False` so the run could proceed.
- `httpx` was missing from the sandbox; installed via `pip install httpx defusedxml --break-system-packages`.
- All HTTP fetches used a `Tombstone Research <tombstoneresearch@proton.me>` user-agent in line with SEC's policy.
- No write actions taken against external systems. No SEC notifications, no GitHub commits.
- TASKS.md updated with a single follow-up item flagging that the **monitor needs repair** (NOT a SEC schema break).
- `latest_run.txt` written summarizing this run.
