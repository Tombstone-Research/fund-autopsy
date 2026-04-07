# Fund Autopsy — Production Readiness Audit

**Scope:** Full codebase review (7,943 lines) across 47 Python files focusing on operational reliability, resource management, failure modes, and observability.

**Review Date:** April 2026
**Status:** Multiple critical and high-severity issues identified. App not production-ready without remediation.

---

## Critical Issues (Will Cause Outages)

### 1. HTTP Client Resource Leaks in EDGAR Access
**Files:** `fundautopsy/core/fund.py:24-53`, `fundautopsy/data/nport.py:54-105`, `fundautopsy/data/ncen.py` (similar pattern throughout)

**Severity:** CRITICAL

**Code Pattern:**
```python
def identify_fund(ticker: str) -> FundMetadata:
    client = get_edgar_client()  # Line 24
    try:
        # ... operations that may raise exceptions ...
    finally:
        client.close()  # Line 53 — ONLY reached if no exception
```

**Failure Scenario:** Any exception raised INSIDE the try block (e.g., network timeout, JSON parse error, ValueError) will skip the `client.close()` call. Over 1000 requests, this leaks 1000 TCP connections into TIME_WAIT state, eventually exhausting the system's file descriptor limit (typically 1024/process).

**Why It's Critical:**
- `resolve_ticker()` at line 26 makes HTTP call without local try/finally
- Multiple nested functions create clients without guaranteed cleanup
- No connection pool reuse — each function creates a new client
- Under load (parallel requests), FD exhaustion happens in hours not days

**Specific Leaks:**
1. Line 268 in `web/app.py`: `identify_fund()` → `client.close()` only in finally, but exceptions mid-pipeline skip it
2. Line 54 in `data/nport.py`: Creates client, line 105 close only reached on success path
3. Line 42 in `data/ncen.py`: Same pattern repeated

---

### 2. Missing Timeout on External Service Calls
**Files:** `fundautopsy/data/edgar.py:93`, `fundautopsy/data/fee_tracker.py:96`, `fundautopsy/data/ncsr_parser.py:94`, `fundautopsy/data/sai_parser.py:135`

**Severity:** CRITICAL

**Issue:** Requests to EDGAR have 30-second timeout, BUT:

1. **Line 268 in `web/app.py`** - No timeout on the entire `identify_fund()` call
2. **Line 274-276 in `web/app.py`** - `retrieve_prospectus_fees()` has no timeout wrapper
3. **Line 282 in `web/app.py`** - `compute_costs()` may have unbounded operations
4. **No overall request timeout** - FastAPI request handlers can hang indefinitely waiting for slow EDGAR responses

**Code:**
```python
@app.get("/api/analyze/{ticker}", response_model=FundAnalysis)
def analyze_fund(ticker: str):
    # No timeout set on this entire handler
    # If EDGAR hangs after initial connection, this request holds a thread forever
    try:
        fund = identify_fund(ticker)  # 30s timeout per call, but...
        tree = detect_structure(fund)  # No timeout here
        tree = compute_costs(tree)     # No timeout here
        tree = rollup_costs(tree)      # No timeout here
```

**Failure Scenario:** EDGAR has a brief connectivity issue. A request starts, makes partial progress, hangs on a secondary request. That FastAPI worker thread is blocked forever. After 10 slow requests, all 10 workers are blocked, app stops responding.

---

### 3. Unbounded Cache Growth (Disk Space DoS)
**Files:** `fundautopsy/data/cache.py:45-125`

**Severity:** CRITICAL

**Issue:** Cache has NO eviction policy. Every unique filing downloaded is cached indefinitely.

```python
def get_xml(self, cik: int, accession_number: str, document: str, max_age_days: int = 365) -> Optional[bytes]:
    # max_age_days defaults to 365, but...
    # There is NO limit on TOTAL cache size
    # Cache structure: ~/.fundautopsy/cache/xml/{cik}/{accession_nodashes}_{doc}
```

**Failure Scenario:**
- App is deployed and analyzes 500 funds
- Each fund has N-CEN (500KB), N-PORT (250KB), 485BPOS (2MB) = ~3MB per fund
- After 100 funds: 300MB. After 500 funds: 1.5GB
- Running 24/7, without cache rotation, disk fills up in weeks
- At disk full: all file operations fail, app crashes with disk write errors
- No monitoring, no alerts, silent failure

**Code Path:**
1. `download_filing_xml()` line 314: Downloads and caches
2. `cache.put_xml()` line 123: Writes file with no size check
3. No cleanup mechanism exists

---

### 4. Global State Pollution in Module-Level Singleton
**Files:** `fundautopsy/data/cache.py:136-144`

**Severity:** HIGH

**Code:**
```python
_cache: Optional[FilingCache] = None

def get_cache() -> FilingCache:
    global _cache
    if _cache is None:
        _cache = FilingCache()
    return _cache
```

**Issue:** In concurrent FastAPI requests, if `get_cache()` is called from multiple threads simultaneously:
- Thread A checks `_cache is None` → True
- Thread B checks `_cache is None` → True (before A sets it)
- Both threads call `FilingCache()`, creating TWO cache objects
- One gets lost, cache operations are split across two instances
- Duplicate cache entries, wasted disk space, inconsistent state

**Also:** No way to clear or reset cache between requests/tests without restarting.

---

## High-Severity Issues (Will Cause Failures)

### 5. Leaderboard JSON Grows Unbounded
**Files:** `fundautopsy/data/leaderboard.py:62-85, 88-143`

**Severity:** HIGH

**Failure Scenario:** Every `/api/analyze/{ticker}` call updates the leaderboard JSON file (line 493 in app.py). After analyzing 50,000 unique funds, the leaderboard.json file is 5-10MB and becomes slow to load/parse.

**Code:**
```python
def _load_leaderboard(path: Path = _LEADERBOARD_FILE) -> dict[str, dict]:
    # Loads ENTIRE file into memory every time
    with open(path, "r") as f:
        data = json.load(f)  # No streaming, no pagination
    return {entry["ticker"]: entry for entry in data}  # Full dict comprehension

def update_leaderboard(...):
    entries = _load_leaderboard(path)  # Load all entries
    # ... modify one entry ...
    _save_leaderboard(entries, path)   # Write entire file
```

**Performance Degradation:** Every API call does full JSON parse and rewrite. With 1000 concurrent analyses, this becomes a bottleneck.

**No Size Limit:** There is no maximum entry count. Leaderboard grows indefinitely.

---

### 6. Missing Exception Handling in Nested Calls
**Files:** `fundautopsy/web/app.py:261-288`

**Severity:** HIGH

**Code:**
```python
try:
    fund = identify_fund(ticker)        # Can raise ValueError, httpx exceptions, others
    tree = detect_structure(fund)       # Can raise AttributeError, KeyError
    _prospectus_fees = _get_fees(...)   # Can raise any Exception (line 159 in prospectus.py)
    tree = compute_costs(tree)          # Can raise division by zero, AttributeError
    tree = rollup_costs(tree)           # Can raise KeyError, ValueError
except ValueError as e:                 # Only catches ValueError
    raise HTTPException(404, str(e))
except Exception as e:                  # Catches all others
    traceback.print_exc()               # Logs to stderr, not to logger
    raise HTTPException(500, f"Analysis failed: {e}")
```

**Issues:**
1. **traceback.print_exc()** at line 287 writes to stderr, NOT to the app logger. In production, this data is lost/scattered across syslog, not in centralized logging
2. **All non-ValueError exceptions become 500s** — can't distinguish user error (bad ticker) from server error (EDGAR down)
3. **No distinction between EDGAR down vs. parsing error** — same error code returned to client
4. **Line 279-280:** Inner exception silently caught and logged.warn(), but processing continues. If prospectus fetch fails, the app doesn't surface this to the user.

---

### 7. Race Condition in Rate Limiter
**Files:** `fundautopsy/data/edgar.py:98-116`

**Severity:** HIGH

**Code:**
```python
def _rate_limit() -> None:
    global _last_request_time
    sleep_duration: float = 0.0
    with _rate_limit_lock:
        now: float = time.time()
        elapsed: float = now - _last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            sleep_duration = RATE_LIMIT_DELAY - elapsed
        _last_request_time = now + sleep_duration  # Reserves the time slot
    if sleep_duration > 0:
        time.sleep(sleep_duration)
```

**The Issue:** Lock is released BEFORE sleeping (good). But:
- Thread A: Acquires lock, computes sleep_duration=0.2, releases lock, sleeps 0.2s
- Thread B: Acquires lock immediately, computes elapsed ~0.0001 (A just released), sleeps another 0.2s
- Both threads sleep, but the schedule is NOT honored — SEC sees 2 requests within 0.2s

**Impact on EDGAR Rate Limiting:** If 2-3 threads call `_rate_limit()` simultaneously, the SEC rate limit (10 req/sec) can be exceeded, causing 429 responses and retry storms.

---

### 8. No Health Check Endpoint
**Files:** None — missing entirely

**Severity:** HIGH

**Failure Scenario:** Kubernetes probes for `/healthz` or similar. App has no health endpoint. K8s assumes app is dead after first failed probe, restarts it constantly.

**What's Missing:**
- No `/health` endpoint
- No `/ready` (readiness) endpoint
- No `/live` (liveness) endpoint
- EDGAR health is tracked (thread-local var in `edgar.py:35-41`) but never exposed
- No way to distinguish:
  - App is running but EDGAR is down (should return 503, not 500)
  - Cache is corrupted
  - Disk is full

---

## Medium-Severity Issues (Will Cause Degradation)

### 9. Logging Only to Console, No File Rotation
**Files:** `fundautopsy/monitoring/schema_monitor.py:206` (only basicConfig found)

**Severity:** MEDIUM

**Issue:** No centralized logging configuration. Individual loggers call:
```python
logger = logging.getLogger(__name__)
```

But there's no handler configured at app startup. By default, logs go nowhere. FastAPI + uvicorn capture some logs, but not from the data layer.

**Missing:**
- No rotating file handler
- No log level configuration via environment variable
- No structured logging (JSON format for log aggregation)
- **`traceback.print_exc()`** at line 287 in app.py writes to stderr, bypassing logger entirely

**Production Scenario:** App runs for 7 days, crashes at day 7. No logs to debug why because:
1. Logs went to stdout (lost when container restarted)
2. Exception was in traceback.print_exc(), which is unstructured

---

### 10. Hardcoded Values Should Be Configuration
**Files:** Multiple

**Severity:** MEDIUM

**Examples:**
1. **Line 8 in `web/__main__.py`:** `port=8000` hardcoded
2. **Line 7 in `web/__main__.py`:** `reload=True` hardcoded (dangerous in production)
3. **Line 31 in `config.py`:** `EDGAR_RATE_LIMIT_DELAY: float = 0.12` — should be configurable if SEC changes policy
4. **Line 26 in `data/edgar.py`:** `MAX_RETRIES: int = 3` — no way to adjust without code change
5. **Line 27 in `data/edgar.py`:** `RETRY_BACKOFF_BASE: float = 1.0` — hardcoded
6. **Line 365 in `data/cache.py`:** Default TTL is 365 days, no way to change per filing type
7. **Line 22 in `data/leaderboard.py`:** Leaderboard path hardcoded to `../../../data/leaderboard.json`

**Production Issue:** If SEC EDGAR goes down for maintenance and needs 60-second retries instead of exponential backoff, you must edit code and redeploy.

---

### 11. No Request Deduplication / Caching at API Level
**Files:** `fundautopsy/web/app.py:252-548` (analyze_fund)

**Severity:** MEDIUM

**Scenario:** User A requests `/api/analyze/VTSAX` at 10:00:00. At 10:00:01, User B requests the same. Both spawn full pipelines:
- Both call identify_fund() → EDGAR API call
- Both call detect_structure() → Download N-CEN, N-PORT
- Both call compute_costs() → Estimate calculations

**Expected:** Second request should wait for first to complete, then return cached result.

**Actual:** Two independent full runs, 2x the EDGAR load.

**Code:** No HTTP caching headers, no request deduplication, no memoization.

---

### 12. Insufficient Error Logging in Retry Loop
**Files:** `fundautopsy/data/edgar.py:119-180`

**Severity:** MEDIUM

**Issue:** When retries are exhausted (line 174-180), the error message is generic:
```python
_edgar_health.errors = getattr(_edgar_health, "errors", 0) + 1
logger.error("EDGAR request failed after %d attempts: %s", MAX_RETRIES, url)
```

**Missing Context:**
- HTTP status codes from each attempt
- Wait times applied
- Network error details
- Whether SEC returned 429 (rate limit) vs. 500 (server error) vs. network timeout

**Production Impact:** When EDGAR is down, operators see "EDGAR request failed" but can't tell:
- Is EDGAR actually down? (Check SEC status page)
- Is our rate limiter broken? (Too many 429s)
- Is the network path broken? (TransportError)

---

### 13. No Graceful Shutdown on SIGTERM
**Files:** `fundautopsy/web/__main__.py`

**Severity:** MEDIUM

**Code:**
```python
if __name__ == "__main__":
    print("\n  Fund Autopsy Dashboard — http://localhost:8000\n")
    uvicorn.run("fundautopsy.web.app:app", host="0.0.0.0", port=8000, reload=True)
```

**Issues:**
1. No signal handlers for SIGTERM/SIGINT
2. No cleanup of background resources on shutdown
3. Uvicorn will hard-kill in-flight requests after grace period
4. Cache singleton may not flush pending writes
5. EDGAR clients may not close cleanly

**Production Scenario:** Rolling deployment kills old container. In-flight request is analyzing a large fund. Request is killed mid-analysis. Leaderboard file is left partially written (corrupted JSON).

---

## Low-Severity Issues (Best Practices)

### 14. Missing Input Validation
**Files:** `fundautopsy/web/app.py:255-257, 598-600, 712-714`

**Severity:** LOW

**Code:**
```python
ticker = ticker.strip().upper()
if not ticker.isalpha() or len(ticker) > 6:
    raise HTTPException(400, "Invalid ticker format")
```

**Better Practice:**
```python
import re
TICKER_PATTERN = re.compile(r'^[A-Z]{1,6}$')
if not TICKER_PATTERN.match(ticker):
    raise HTTPException(400, "Invalid ticker: must be 1-6 uppercase letters")
```

**Why:** Current validation allows edge cases (empty string after strip), and error message is generic.

---

### 15. Floating Point Precision in Cost Calculations
**Files:** `fundautopsy/web/app.py:223, 344, 371, 381`

**Severity:** LOW

**Code:**
```python
true_cost_low_bps = round(expense_ratio_bps + total_hidden_low, 2)
```

**Issue:** Adding basis points and percentages with floating point arithmetic can accumulate rounding errors. Over 1000 funds, small errors compound.

**Better Practice:** Use `decimal.Decimal` for financial calculations:
```python
from decimal import Decimal, ROUND_HALF_UP
true_cost_low_bps = Decimal(expense_ratio_bps) + Decimal(total_hidden_low)
true_cost_low_bps = true_cost_low_bps.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

---

### 16. No Metrics / Monitoring Instrumentation
**Files:** None found (only a `monitoring/schema_monitor.py` for schema checks, not metrics)

**Severity:** LOW

**Missing:**
- Request latency histogram (How long does analyze_fund take?)
- Cache hit rate counter (Are we actually saving EDGAR calls?)
- EDGAR error rate (How often do retries happen?)
- Leaderboard update count (Is the API being used?)
- Worker thread utilization (Are we CPU-bound or I/O-bound?)

**Production Impact:** When app is slow, operators have no visibility into whether it's EDGAR being slow, cache misses, or computation overhead.

---

## Summary Table

| Issue | File(s) | Severity | Impact | Fixes Needed |
|-------|---------|----------|--------|--------------|
| HTTP client resource leaks | core/fund.py, data/nport.py, data/ncen.py | CRITICAL | FD exhaustion, outage | Use context managers for all HTTP clients |
| Missing timeout on handlers | web/app.py | CRITICAL | Requests hang forever | Add request-level timeout |
| Unbounded cache growth | data/cache.py | CRITICAL | Disk fills, app crashes | Implement cache eviction policy (LRU or size limit) |
| Cache singleton race condition | data/cache.py | HIGH | Thread-unsafe initialization | Use threading.Lock or use functools.lru_cache |
| Leaderboard JSON unbounded | data/leaderboard.py | HIGH | Performance degradation | Limit entries, use pagination or database |
| Exception handling gaps | web/app.py | HIGH | Lost error context | Use centralized logger, structured error responses |
| Rate limiter race condition | data/edgar.py | HIGH | SEC rate limit violations | Fix lock placement or use asyncio |
| No health check endpoint | web/app.py | HIGH | K8s restarts, no observability | Add /health, /ready, /live endpoints |
| No log rotation | (global) | MEDIUM | Lost debug data | Configure RotatingFileHandler, JSON logging |
| Hardcoded configuration | Multiple | MEDIUM | No operational flexibility | Move to environment variables or config file |
| No request deduplication | web/app.py | MEDIUM | 2x EDGAR load for concurrent requests | Add memoization or cache layer |
| Insufficient retry logging | data/edgar.py | MEDIUM | Hard to debug EDGAR issues | Add detailed per-attempt logging |
| No graceful shutdown | web/__main__.py | MEDIUM | Corrupted state on restart | Add SIGTERM handler |
| Missing input validation | web/app.py | LOW | Edge case handling | Tighten regex, better error messages |
| Float precision | web/app.py | LOW | Rounding errors accumulate | Use Decimal for financial calculations |
| No metrics instrumentation | (global) | LOW | No operational visibility | Add prometheus client or similar |

---

## Recommendations Priority

**Phase 1 (Before Launch — Do First):**
1. Fix HTTP client leaks with context managers (critical for stability)
2. Add request-level timeout to FastAPI handlers
3. Implement cache eviction (LRU with max size)
4. Add /health endpoint with EDGAR status

**Phase 2 (Week 1 Production):**
5. Fix leaderboard JSON growth (limit to 1000 entries or switch to database)
6. Add centralized logging with rotation
7. Move hardcoded values to environment variables
8. Add SIGTERM handler for graceful shutdown

**Phase 3 (Operational Hardening):**
9. Add request deduplication / memoization
10. Add detailed retry logging
11. Add metrics instrumentation
12. Implement database for leaderboard if traffic justifies

---

## Files Requiring Immediate Review

- `/fundautopsy/web/__main__.py` — startup/shutdown logic
- `/fundautopsy/web/app.py` — exception handling, request timeouts
- `/fundautopsy/data/edgar.py` — client lifecycle, rate limiting
- `/fundautopsy/data/cache.py` — eviction policy, singleton thread safety
- `/fundautopsy/data/leaderboard.py` — unbounded growth
- `/fundautopsy/core/fund.py` — client lifecycle

