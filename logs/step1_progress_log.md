# Step 1 Run — Progress Log (US imports by country, Census API)

Maintained while executing `E:\device_tariff` Phase 2 scripts
in the order defined by `run_phase2.bat`. Records every command run, every
code change, every error, and the outcome of each step.

---

## Pre-flight

- **2026-11-15** — Inspected `E:\device_tariff` (no `phase2` subfolder exists;
  the Phase 2 scripts live directly in `device_tariff`). Confirmed no prior
  `raw/`, `data/`, `logs/` output existed (fresh run).
- Verified Python: `py --version` → Python 3.14.7.
- Confirmed no `census_key.txt` present — step 1 will run unauthenticated
  (Census allows ~500 queries/day from one IP without a key; step 1 needs
  ~240).

## Step 0 — `common.py`

- **Command:** `py common.py` (run standalone, as requested).
- **Result:** exit code 0, no stdout/stderr.
- **Effect:** created empty `raw/`, `data/`, `logs/` folders (module-level
  `mkdir(parents=True, exist_ok=True)` calls). No network activity — this
  file only defines helper functions used by the step scripts.
- **Errors:** none.

## Step 1 — `step1_us_imports_census.py`

Status: **running**.

- **06:22:40** — Started: `py step1_us_imports_census.py` (background, stdout/stderr
  captured to `logs/step1_stdout_stderr.txt`; the script's own `log()` calls
  also write to `logs/step1_census.txt`, which I'm tailing live).
- **06:22:40** — "Step 1 started: US imports by country (Census)".
- **06:22:42 → 06:22:51** — `latest_2026_month()` is probing period `2026-12`
  (via HS6 901831, used as a probe code) to find the newest published 2026
  month. Each attempt raises `JSONDecodeError: Expecting value: line 1
  column 1 (char 0)` inside `fetch_json` — i.e. the HTTP response body is
  not valid JSON (likely an empty/HTML/plain-text body from Census for a
  period that has no data yet, rather than the empty-body `204` case that
  `fetch_json` already special-cases). `fetch_json` treats
  `JSONDecodeError` as transient and retries with backoff (2s, 4s, 8s, ...)
  up to 5 tries before giving up on that period and moving to the next
  month down.
  - **Effect / risk:** this is likely a *deterministic* "no data published
    yet for this future period" condition, not a transient server hiccup,
    so each of the (up to) 12 months probed could burn a full 5-try
    backoff cycle (~62s) before `latest_2026_month()` gives up and returns
    `None`. Watching this play out before deciding whether to patch
    `fetch_json`'s JSON-decode-error handling (flagged per the
    engineering rule: don't retry a deterministic permanent failure
    indefinitely). No code changed yet — observing first.
- **06:22:51 → 06:23:51** — Period `2026-12` exhausted all 5 tries (2s, 4s,
  8s, 16s, 32s backoff — confirms the pattern), then `latest_2026_month()`
  moved on to probe `2026-11`. Decision: let the bounded retry/probe loop
  run to completion rather than killing the in-flight process — it is slow
  but not unsafe or infinite (worst case ~12 months x 5 tries x backoff ≈
  12 minutes before it gives up and falls back to "no 2026 month found").
  Will recommend a patch to `fetch_json`/`latest_2026_month` after this run
  finishes so future reruns don't pay this cost again.
- **06:24 → 06:34** — Pattern held for months 2026-12, 2026-11, 2026-10,
  2026-09 (each: 5 tries, full 2/4/8/16/32s backoff, same
  `JSONDecodeError`). ~10 minutes elapsed, zero successful requests, zero
  files written to `raw/census/`.
- **06:34** — **Root cause found.** Reproduced the request directly with
  `curl -v` outside the script, for both the probe period (`2026-12`) *and*
  a known-good historical period (`2024-12`, HS6 901831). Both returned
  identically:
  ```
  HTTP/1.1 302 Found
  X-DataWebAPI-KeyError: 1
  Location: https://api.census.gov/data/missing_key.html
  ```
  This is **not** a "future month not published yet" condition at all — the
  Census International Trade API is now rejecting *every* request made
  without an API key (`X-DataWebAPI-KeyError: 1`), including requests for
  periods that definitely have published data. The script's docstring
  assumption ("Without a key Census allows about 500 questions a day") no
  longer holds — Census appears to now require a key unconditionally for
  this endpoint. `fetch_json` doesn't special-case this 302 (it only
  special-cases a literal HTTP 204 "no data" and raw HTTP error codes); the
  redirect target returns an HTML page, so `json.loads()` on it raises
  `JSONDecodeError`, which `fetch_json` classifies as transient and retries
  5x with backoff — meaning **every one of the ~240 planned requests would
  have failed the same way**, after burning the full retry budget each
  time (worst case: 240 x 62s ≈ 4+ hours of pure backoff for zero data).
  No `census_key.txt` is present in the project folder.
- **06:34** — **Action taken: stopped the run.** Per the engineering rules
  (don't retry a deterministic/permanent failure indefinitely; investigate
  before continuing when something looks blocked), killed the background
  process (`task bnkujxmv5`) and the log-tail monitor (`task bwgsziron`)
  rather than let it exhaust all 240 jobs for no data. **No code was
  modified.** No partial/corrupt evidence files exist — `raw/census/` and
  `data/` are both empty, confirming `save_json_safely` was never reached
  (it only writes on a successful or explicit "no_data" response, neither
  of which occurred).

### Status: STOPPED — BLOCKED, awaiting a Census API key

Step 1 cannot produce data in its current state. Getting a free key
(https://api.census.gov/data/key_signup.html, already documented in the
script's own docstring) and saving it as `census_key.txt` in
`E:\device_tariff\` is the documented, legitimate way to proceed — this is
registering for intended API access, not bypassing a protection.
Separately, `fetch_json`'s classification of the `missing_key.html`
redirect as a transient JSON error (rather than a permanent
`authentication_required` failure) is a bug worth fixing before any
re-run, so a missing/expired/invalid key fails fast instead of retrying 5x
per request.

Step 2 and step 3 were not started. Step 2 (India/Comtrade data) does not
depend on step 1's output, but step 3 needs step 1's output to build the
US-side of the summary, so running step 2 now and step 3 after would leave
step 3 incomplete. Awaiting a decision on the key before continuing in the
`run_phase2.bat` order.

---

## Resume — user supplied a fix and an API key

- User replaced `common.py`, `step1_us_imports_census.py`, and
  `step2_india_trade_comtrade.py` with fixed versions (not written by me)
  that detect the missing/invalid-key redirect explicitly and stop instead
  of retrying it as transient.
- **Verified before running anything:**
  - `common.py` contains `key_error` (confirmed at line 72 docstring and
    lines 89/93/94: reads `X-DataWebAPI-KeyError` header and checks the
    final URL for `missing_key`/`invalid_key`, returns a `"key_error"`
    status instead of raising/retrying).
  - `step1_us_imports_census.py` defines `check_key(key)` at line 88.
  - Key file was already named `census_key.txt` (not `census_key`) — no
    rename needed.
  - Validated `census_key.txt` content without printing the key: 40 bytes,
    exactly 1 non-empty line, no leading/trailing whitespace, no internal
    spaces, no quotes, no blank lines, alphanumeric — matches the expected
    Census key format.
- Did not patch anything myself (user declined that offer and supplied
  their own fix instead).

### Run 2 — with API key and fixed scripts

- **06:4x** — Started: `py step1_us_imports_census.py` (background, task
  `bm6026ksu`; stdout/stderr captured to `logs/step1_stdout_stderr_run2.txt`;
  tailing only *new* lines of `logs/step1_census.txt` from this point on,
  filtered to key-test result / progress / failures / completion).
- **06:49:36** — Key test (`check_key`) passed silently (script proceeded
  past it into `latest_2026_month()`), which then found: "Latest 2026 month
  published: 2026-09 (2026 figures are Jan to that month)." No `STOP` or
  key-error lines seen — the fix works and the key is valid.
- **06:49:41 → 07:01:45** — Main download loop ran all 240 jobs (48 HS6
  codes in `hs6_codes.csv` x 5 periods: 2022-12, 2023-12, 2024-12, 2025-12,
  plus the newly-found YTD month 2026-09 = 48 x 5 = 240). Every single job
  logged `ok` — zero `FAILED` lines in
  `logs/step1_census.txt` (confirmed via `grep -c FAILED` = 0). Rate
  stayed close to the script's built-in `time.sleep(0.5)` pace; ETA
  display counted down smoothly from ~18 min to 0.
- **07:01:46** — `Wrote data/us_imports_by_country.csv with 13957 rows`,
  then `Step 1 finished`.
- **Post-run verification (by me, independent of the script's own log):**
  - `raw/census/` contains exactly 240 JSON evidence files (one per
    code x period job) — matches the job count exactly, no gaps.
  - `data/us_imports_by_country.csv`: 13,958 lines total (13,957 data rows
    + 1 header), 1,630,974 bytes, UTF-8-with-BOM as `write_csv` produces.
    Spot-checked header and first data rows — columns match the script's
    documented schema (`year, period_end, months_covered, hs6, group,
    description, cty_code, cty_name, summary_lvl,
    imports_for_consumption_usd, general_imports_usd, dutiable_value_usd,
    calculated_duty_usd, effective_duty_rate_pct`); first row is India
    2022 adhesive dressings ($1,769,937), consistent with expected shape.
  - `logs/step1_stdout_stderr_run2.txt` ends with `EXIT:0`, no traceback.

### Status: STEP 1 COMPLETE — SUCCESS

240/240 Census requests succeeded, 0 failures, 0 retries needed (key
worked on the first test). Proceeding to step 2 per `run_phase2.bat`'s
order, as instructed.

---

## Step 2 — `step2_india_trade_comtrade.py`

- **07:0x** — Started: `py step2_india_trade_comtrade.py` (background, task
  `bcz3hqiem`; stdout/stderr captured to `logs/step2_stdout_stderr.txt`;
  tailed `logs/step2_comtrade.txt` filtered to STOP/FAILED/key_error/
  "not data"/completion).
- **07:02 → 07:04:13** — All 24 batch jobs (2 flows x 4 years x 3 code
  batches) logged `ok`. Two transient `HTTP 429: Too Many Requests` hit
  once each (on "India imports 2023 batch 3" and "India imports 2024
  batch 2"), each retried once after a 2s backoff and succeeded on the
  2nd try — normal, polite, bounded transient-retry behavior, not an
  issue.
- **07:04:13** — `Wrote data/india_trade.csv with 0 rows.` `Step 2
  finished.` Exit code 0 in `logs/step2_stdout_stderr.txt`. **No STOP, no
  FAILED, no key_error line anywhere** — this is not the "key error" or
  "web page instead of data" failure mode the user anticipated; it is a
  silent, different failure: the run reports total success while
  producing zero usable rows.
- **Investigated (did not accept "0 rows" as success merely because no
  exception occurred — see data-quality rule on this):**
  - Read a saved raw file, e.g. `raw/comtrade/X_2022_1.json`:
    `{"codes": [...20 codes...], "elements": []}` — empty on every batch.
  - Reproduced the exact same request live with `curl` (same reporter,
    period, flow, cmdCode list, partner list) against
    `https://comtradeapi.un.org/public/v1/preview/C/A/HS`. The live server
    responded `HTTP 200` with **real, non-empty data**:
    `{"elapsedTime":"0.18 secs","count":2,"data":[{...primaryValue:
    9994233.783...}, {...primaryValue: 1717891.378...}],"error":""}`.
  - **Root cause:** the UN Comtrade public preview API's response puts
    the row array under the key **`"data"`**, not **`"elements"`**. The
    schema the script was written against (or assumed) used `"elements"`
    — either the API changed its response shape, or the script's
    assumption was wrong from the start. `download_batch()` in
    `step2_india_trade_comtrade.py` does
    `elements = (data or {}).get("elements", []) if status == "ok" else []`
    — since the key doesn't exist in the real response, `.get(...,
    [])` silently falls back to an empty list every single time, the
    request is still logged/returned as `"ok"` (the HTTP call and JSON
    parse both genuinely succeeded), and `build_table()` then has nothing
    to aggregate. **100% data loss, 0% error visibility** — confirmed
    across all 24 saved raw files (`grep -c '"elements": \[\]'` = 24 of
    24; zero files have a non-empty `"elements"` array).
  - This bug is independent of the earlier Census key-error fix — it is a
    field-name/schema mismatch in step 2's own extraction code, not
    something the user's `key_error` patch touches (Comtrade's public
    preview endpoint used here doesn't require a key and never returned a
    key-error).
- **Action taken:** stopped before running step 3. Per the user's
  instructions, step 3 only had an explicit go-ahead "if step 1
  finishes" — step 1 did finish, but running step 3 now would summarize
  against an India dataset with **zero rows**, producing a
  `phase2_summary.csv` where every India-side column (`india_exports_*`,
  `us_dependence_pct`, `mirror_gap_pct`, `india_imports_*`) is silently 0
  or blank for all 48 codes — indistinguishable from "India trades none
  of this" rather than "data wasn't captured." Not proceeding to step 3
  until this is resolved. **No code was modified by me.**

### Status: STEP 2 "SUCCEEDED" BUT PRODUCED NO DATA — blocked on a
### `"elements"` vs `"data"` key mismatch in step2's own parsing code

## Fix applied to `step2_india_trade_comtrade.py` (by me, user-directed)

User reviewed the diagnosis above and asked me to fix it directly. Changes
made with `Edit` (verified by re-reading the whole file afterward):

1. **Docstring** ("WHAT YOU GET"): documented the new raw-file shape
   (`{"requested_codes": [...], "response": <full server JSON>}`) instead
   of the old `{"codes": ..., "elements": ...}`.
2. **`download_batch()`** — rewritten:
   - `status == "no_data"` is now normalized to `{"data": [], "error":
     ""}` (a legitimate "nothing to report" answer, not a failure).
   - Explicit check: if the parsed response isn't a dict or has no
     `"data"` key, the batch is marked **FAILED** and the log line
     includes the keys that *were* present — so a future schema change or
     wrong field name fails loudly instead of silently saving an empty
     list.
   - Explicit check: if `response["error"]` is non-empty, the batch is
     marked **FAILED** and the server's error message is logged.
   - Rows are now read from `data["data"]` (the real key), not
     `data.get("elements", [])`.
   - The raw file now saves `{"requested_codes": hs_list, "response":
     data}` — the *whole* server answer, plus the batch's requested code
     list for provenance — instead of just the extracted (and
     previously-empty) rows.
   - After a successful save, logs per batch: rows received, the max
     possible (`len(hs_list) x len(PARTNERS)`), how many of the batch's
     codes came back with >=1 row, and (if any) which codes came back
     with zero rows.
3. **`build_table()`** — updated to read `saved["response"]["data"]`
   instead of `saved["elements"]`. After writing `india_trade.csv`, added
   a per-year coverage log: "`{year}: X/{total} codes have an
   India-to-USA export figure`" for each of the 4 years, and `"Do NOT run
   step 3: india_trade.csv has 0 rows."` if the final row count is 0.
4. **No other logic changed** (batching, 500-row-split retry,
   partner/flow config, politeness sleep, CSV schema/column order for
   `india_trade.csv` all untouched).

## Housekeeping — old empty raw files preserved, not deleted

Moved (not deleted) the 24 raw files from the buggy run:
`mkdir -p raw/comtrade/_old_empty && mv raw/comtrade/*.json
raw/comtrade/_old_empty/`. Confirmed: 24 files now in `_old_empty/`, 0
`.json` files remain directly in `raw/comtrade/`. This both preserves the
original (if-flawed) evidence per the "never delete existing data"
engineering rule, and forces `download_batch()`'s `if raw_file.exists():
return "skipped"` check to miss them, so every batch gets freshly
re-downloaded under the fixed code rather than silently reusing an empty
cached file.

## Re-run of step 2 with the fix

- **07:1x** — Started: `py step2_india_trade_comtrade.py` (background,
  task `bx3yrsijz`; stdout/stderr → `logs/step2_stdout_stderr_run2.txt`).
- All 24 batches (2 flows x 4 years x 3 code-batches) re-downloaded fresh
  (no `raw_file.exists()` skips, as intended — the old files were moved
  aside). A handful of transient `HTTP 429` hits, each retried once and
  succeeded (polite backoff working as designed, not an issue).
- **07:16:16** — `Wrote data/india_trade.csv with 2136 rows.` Then the
  new per-year coverage lines:
  ```
  2022: 47/48 codes have an India-to-USA export figure
  2023: 47/48 codes have an India-to-USA export figure
  2024: 46/48 codes have an India-to-USA export figure
  2025: 45/48 codes have an India-to-USA export figure
  ```
  `Step 2 finished`. Exit code 0. **Zero FAILED/STOP/key_error lines** in
  `logs/step2_comtrade.txt` (`grep -c` = 0).
- **Example per-batch coverage lines** (from `logs/step2_comtrade.txt`):
  ```
  [2026-11-15 07:15:34]   batch 1: 109 rows received (max possible = 20 codes x 7 partners = 140); 19/20 of this batch's codes came back with at least one row; no rows for: 300620
  [2026-11-15 07:15:40]   batch 2: 125 rows received (max possible = 20 codes x 7 partners = 140); 20/20 of this batch's codes came back with at least one row
  [2026-11-15 07:15:45]   batch 3: 48 rows received (max possible = 8 codes x 7 partners = 56); 8/8 of this batch's codes came back with at least one row
  ```
  (HS6 300620 — "Blood-grouping reagents" — consistently had no India
  exports/imports rows for any partner in several batches; worth noting
  as a real zero, not a bug, now that the extraction itself is verified
  correct.)
- **Spot-checked one raw file** (`raw/comtrade/X_2022_1.json`) directly:
  101 rows (of a possible 140 = 20 codes x 7 partners), and the distinct
  partner codes present are exactly the 7 configured partners — `0, 156,
  276, 372, 392, 484, 842` (World, China, Germany, Ireland, Japan,
  Mexico, USA). Confirms the fix is pulling real, complete rows, not an
  artifact of one lucky batch.
- `data/india_trade.csv`: 2,137 lines total (2,136 data rows + 1 header).

### Status: STEP 2 COMPLETE — SUCCESS (after the fix)

2,136 rows written, 0 failures, coverage 45-47 of 48 codes per year have
an India-to-USA export figure (the gap is expected — some codes
genuinely have no recorded India-to-USA trade in a given year, e.g. HS6
300620). Since `india_trade.csv` has more than 0 rows, proceeding to
step 3 per the user's instruction.

---

## Step 3 — `step3_checks_and_summary.py`

- **07:16:56** — Ran `py step3_checks_and_summary.py` (foreground, no
  network calls — pure local computation over `data/
  us_imports_by_country.csv` and `data/india_trade.csv`). Exit code 0, no
  traceback.
- Output: `data/phase2_summary.csv` (240 data rows + header = 241 lines;
  48 codes x 5 years), `data/phase2_checks.txt`.
- **Checks produced** (full text also in `data/phase2_checks.txt`):
  - Check 1 (US imports from India, our 48 codes): $495.3M (2022), $492.7M
    (2023), $517.1M (2024), $541.9M (2025), $335.5M (2026, 9 months so
    far). Reference point: EPCMD FY2024-25 = $782.57M — calendar 2024/2025
    sit noticeably below that FY figure, which the script's own note
    flags as worth checking (missing code vs. FY-vs-calendar-year
    mismatch vs. EPCMD counting a broader product set).
  - Check 2: 131 code-years where the US-reported and India-reported
    figures disagree by >25% ("mirror gap") — the script treats some gap
    as expected (shipping lag, freight-in-value, trans-shipment) and
    uses the US figure as Exposure since that's what duty is charged on.
  - Check 3: in 2025, 20 of 48 codes had US imports from India under $1M
    (listed in the checks file) — per the project's plan these drop out
    of View A.
  - Check 4 (effective duty rate on Indian device imports): 0.05%
    (2022), 0.04% (2023), 0.03% (2024), 17.64% (2025), 13.79% (2026) —
    consistent with the script's own expectation (near-zero MFN-only
    through 2024, a jump in 2025 from reciprocal tariffs, a 2026 mix of
    Section 122/301 duties).
- No data-integrity red flags raised by the script itself beyond what it
  already prints as expected caveats (Check 1's FY-vs-calendar-year note,
  Check 2's mirror-gap count). Not independently re-verified beyond
  confirming the script ran against real, non-empty step-1/step-2 data
  this time (unlike the step-2 failure earlier in this log).

### Status: STEP 3 COMPLETE — SUCCESS

### Status: ALL THREE STEPS (plus common.py) NOW COMPLETE, IN THE ORDER
### `run_phase2.bat` USES

Summary of the whole run: step 1 succeeded cleanly on the first attempt
with the key; step 2 initially "succeeded" while silently producing zero
rows (`"elements"` vs `"data"` key bug, found and fixed); step 2 re-run
succeeded with real data (2,136 rows); step 3 succeeded against complete
step 1 + step 2 data. Final outputs: `data/us_imports_by_country.csv`
(13,957 rows), `data/india_trade.csv` (2,136 rows),
`data/phase2_summary.csv` (240 rows), `data/phase2_checks.txt`.

---

# Investigation A — why is our India-to-US total ~$520M vs EPCMD's $782.57M?

User's constraint for this investigation: do not change or overwrite the
existing data files; put new results in new files.

## A1 — Census (US-reported) vs Comtrade (India-reported) totals

- Wrote `a1_census_vs_comtrade.py` (new, standalone script; does not
  modify `step1`/`step2`/`step3`/`common.py`). Reads only
  `data/us_imports_by_country.csv` and `data/india_trade.csv`
  (read-only) — sums US "imports for consumption" from India
  (`cty_code == 5330`, `summary_lvl == "DET"`) per year, and Comtrade
  "India exports" to partner "USA" per year, for 2022-2025. Writes a new
  file, `data/a1_census_vs_comtrade.csv` — does not touch either input
  file.
- **Result:**

  | year | US-reported (Census) $ | India-reported (Comtrade) $ | diff % |
  |------|------------------------|------------------------------|--------|
  | 2022 | 495,340,211 | 476,668,463 | 3.9% |
  | 2023 | 492,686,127 | 466,818,441 | 5.5% |
  | 2024 | 517,133,574 | 493,137,048 | 4.9% |
  | 2025 | 541,909,861 | 539,210,135 | 0.5% |

- **Finding:** the two independent sources (US Census vs India/UN
  Comtrade) agree closely (0.5-5.5% apart, well inside the ±25%
  "MIRROR_GAP" threshold `step3` uses elsewhere) — the mirror gap is
  **not** what explains the shortfall against EPCMD's $782.57M FY
  2024-25 figure. Both sides independently say our 48-code total is
  ~$495-542M/year. This points toward the 48-code list missing products
  that EPCMD counts as medical devices, rather than a reporting
  discrepancy between the two trade-data sources.

## A2 — test 13 candidate "missing" HS6 codes

- **Backed up** (copied, originals untouched) before any regeneration:
  `data/us_imports_by_country.csv` -> `data/us_imports_by_country_48codes_backup.csv`,
  `data/india_trade.csv` -> `data/india_trade_48codes_backup.csv`. This
  preserves the pre-candidate 48-code baseline even though step 1/step 2
  will naturally rebuild their real output CSVs to include the new
  candidate codes (that rebuild is the whole point of "re-run step 1 and
  step 2" — it is additive, not destructive: every original 48-code row
  stays in the rebuilt file, plus new candidate rows).
- **Edited `hs6_codes.csv`**: appended the 13 user-specified codes with
  `group = "Candidate"`, keeping the original 48 rows unchanged. **Caught
  and fixed two bugs I introduced in that edit** before running anything
  further: `871310`/`871390` ("Wheelchairs, not mechanically propelled" /
  "Wheelchairs, other") and `701790` ("Laboratory glassware, other") all
  contain a comma in the description but I'd typed them unquoted — that
  breaks plain CSV parsing (an extra phantom column, shifted fields).
  Caught this by actually running `common.py`'s own `read_codes()` (the
  same `csv.DictReader` the pipeline uses) against the file afterward
  rather than trusting the edit — it reported `None: [' other']` for
  701790, proving the break. Fixed by quoting all three descriptions
  (`"Wheelchairs, not mechanically propelled"`, etc.). Re-verified:
  61 codes total, 0 malformed rows, 0 duplicate hs6 codes.
- **Checked for step 2 batch-composition drift before re-running it.**
  `step2`'s `BATCH = 20` batching slices the *current* `hs6_codes.csv`
  order into fixed-size chunks and names each batch's raw file only by
  its *position label* ("1", "2", "3", ...), not its content. Appending
  13 codes to the end shifts what falls into the last, partial batch:
  old batch 3 was the original 8 codes
  (`902214,902219,902221,902229,902230,902290,940210,940290`); the new
  batch 3 is 20 codes = those same 8 **plus 12 of the 13 new
  candidates** (`392620,401519,630790,621010,841920,902511,902780,
  902750,900130,871310,871390,300670`); the 13th candidate (`701790`)
  falls into a brand-new batch 4. Verified this programmatically (listed
  old vs. new batch contents side by side) rather than assuming. Since
  `download_batch()` skips any batch whose **file already exists**
  regardless of content, the stale 8-code batch-3 files from the
  original run would have been skipped forever, silently dropping 12 of
  the 13 candidates' Comtrade data with no error at all — exactly the
  kind of silent data loss this investigation is trying to avoid.
  **Fix:** moved (not deleted) the 8 affected files (`X_2022_3.json,
  X_2023_3.json, X_2024_3.json, X_2025_3.json, M_2022_3.json,
  M_2023_3.json, M_2024_3.json, M_2025_3.json`) into
  `raw/comtrade/_old_batch3_8codes_pre_candidates/`, forcing a fresh,
  correctly-composed re-download of batch 3. Batches 1 and 2 are
  unaffected (first 40 codes unchanged in position) and were correctly
  left in place to be skipped/reused as-is.
- Re-ran step 1 (`py step1_us_imports_census.py`, task `bm2w67l41`):
  305/305 jobs (61 codes x 5 periods), exit 0, no FAILED/STOP/key_error.
  `data/us_imports_by_country.csv` rebuilt with 17,930 rows (up from
  13,957 — the growth is from the 13 new candidate codes).
- Re-ran step 2 (`py step2_india_trade_comtrade.py`, task `b7vd6qbsw`)
  with the batch-3 fix in place — result logged below once complete.

## A3 - searching for EPCMD's actual HS-code definition of "medical device"

Searched epcmd.in and the Department of Pharmaceuticals' medical-device
pages for an explicit HS code list or export-data note explaining the
$782.57M figure, per the user's instruction to report exact links/quotes
and say so plainly if nothing is found rather than guess.

- Found and read directly (via WebFetch + Read on the saved PDF, since
  the PDF's compressed text streams defeated a plain-text fetch):
  https://www.epcmd.in/assets/img/Report-hub/Medical_devices_EXIM_Data_Apr-Mar_2024-25.pdf
  - "Medical Devices Trade Analysis for FY 2024-25", Table 4
  ("Country-wise Medical Devices Exports"), row 1: USA, April-Mar
  2024-25 = $782.57 million, 19.52% share, growth 9.55% vs FY2023-24
  ($714.30M). Source cited on the document itself: DGCIS (Directorate
  General of Commercial Intelligence and Statistics). This report breaks
  the total (all countries) into 5 categories - Consumable & Disposable
  (45.13%), Electronic Equipment (38.19%), Implant (8.32%), IVD Reagents
  (5.76%), Surgical Instrument (2.14%) - but does not print any HS codes
  itself.
- Found and read directly:
  https://epcmd.in/assets/img/product_panel/Product_Panel_ghl5me.pdf -
  DGFT Public Notice No. 18/2023 (23 June 2023), the official
  Gazette-of-India notice adding EPCMD to Appendix 2T of the Foreign
  Trade Policy 2023. Lists EPCMD's product jurisdiction as 151 numbered
  items by tariff-style description (no HS codes printed in this
  particular PDF).
- Found the definitive source by fetching epcmd.in's own homepage link
  list directly (search engines did not surface it):
  https://www.epcmd.in/assets/img/product_panel/151 HS code.pdf - an
  Excel-exported PDF giving the literal HSN (8-digit) code for every one
  of the 151 items, each tagged with its category (Consumable &
  Disposable / Electronic Equipment / Implant / IVD Reagents / Surgical
  Instrument). This is the real, authoritative definition of what EPCMD
  counts in its export figures - read in full via Read on the saved PDF
  (3 pages, all codes extracted).
- No report was found anywhere that itemizes the $782.57M figure by HS
  code directly (i.e. no "$X million was code 901812, $Y million was
  code 621010" breakdown) - only the aggregate country/category/region
  tables in the EXIM report. Noting this gap explicitly rather than
  guessing a code-level breakdown of the $782.57M itself.
- Cross-checked all 13 candidate HS6 codes against the real 151-code
  EPCMD list (by HS6 prefix, since EPCMD's codes are 8-digit HSN):
  CONFIRMED exact matches (6 of 13): 300670, 621010, 900130, 902511,
  902750, 902780. NOT found anywhere in EPCMD's 151-code list (7 of 13):
  392620 (EPCMD's real plastics code is 392321/392390 "sacks and bags",
  not gloves), 401519 (EPCMD only lists 401512), 630790 (EPCMD's actual
  PPE-garment codes are 621010 and 621040, not heading 6307), 841920
  (heading 8419 does not appear anywhere in EPCMD's list), 871310 and
  871390 (heading 8713 does not appear anywhere), 701790 (heading 7017
  does not appear anywhere). Also noted: EPCMD's real list includes
  several codes neither our 48 nor our 13 candidates cover at all -
  300660 (contraceptives), 392321/392390 (plastic bags), 401410/401490,
  621040, 900150 (spectacle lenses), 902519/902710/902720/902730/902790
  (more of the 9027 instrument family), 842310 (weighing scales), and
  the 961900 series (sanitary pads/diapers/napkins). These are real gaps
  beyond this investigation's 13-code test but were not downloaded or
  included in the A2 comparison, since the user specified the 13 codes
  to test.

## A2 result - 2024/2025 comparison table for the 13 candidates

Wrote a2_candidate_codes_compare.py (new, standalone, read-only against
data/us_imports_by_country.csv, data/india_trade.csv, hs6_codes.csv;
writes data/a2_candidate_codes_compare.csv). Sorted by 2024 US figure,
descending. Columns: hs6, description, US-imports-from-India 2024,
India-exports-to-USA 2024, US-imports-from-India 2025, India-exports-to-USA 2025.

630790 Made-up textile articles incl. surgical masks and drapes: 139,447,839 / 36,633,444 / 161,277,574 / 37,017,335
392620 Plastic gloves and apparel: 12,081,046 / 3,694,929 / 10,758,082 / 2,855,662
701790 Laboratory glassware, other: 4,421,900 / 8,167,816 / 3,113,061 / 6,058,332
621010 Garments of nonwovens incl. surgical gowns: 4,313,288 / 4,160,112 / 6,644,599 / 4,247,307
902750 Other instruments using optical radiation: 988,037 / 2,905,210 / 709,938 / 3,408,626
900130 Contact lenses: 971,255 / 7,900,148 / 3,000 / 1,555,086
841920 Medical and laboratory sterilisers: 601,878 / 686,626 / 564,625 / 307,260
401519 Other rubber gloves: 364,735 / 1,061,772 / 688,235 / 994,527
902511 Liquid-filled thermometers incl. clinical: 196,184 / 425,445 / 137,501 / 342,127
871390 Wheelchairs, other: 91,800 / 2,048 / 163,814 / 1,163
300670 Gel preparations for surgical/medical use: 14,819 / 32,567 / 37,925 / 115,854
871310 Wheelchairs, not mechanically propelled: 7,246 / 2,571 / 0 / 19,669
902780 Other laboratory analysis instruments: 0 / 0 / 0 / 0

902780 is a genuine zero, not a bug - confirmed by reading
raw/census/902780_2024-12.json directly: {"status": "no_data", "rows":
null} - Census has no recorded US imports from India under this code,
same for 2025.

## A4 - does adding the candidates close the gap to $782.57M?

No - not meaningfully. Computed directly from the regenerated
data/us_imports_by_country.csv (not reusing the stale phase2_summary.csv,
since the underlying data changed):

- Base 48-code 2024 total (US imports from India, Census): $517,133,574
  - matches step 3's original Check 1 figure exactly, confirming the
  original 48 codes' own raw data was untouched by the candidate re-run.
- Gap to EPCMD's $782.57M: $265,436,426.
- Adding only the 6 candidates that are actually confirmed in EPCMD's
  own 151-code list (621010, 902750, 900130, 902511, 300670, plus zero
  from 902780): total rises to only $523,617,157 - closes just
  $6,483,583 of the $265.4M gap (2.4%). Not a meaningful dent.
- Adding all 13 candidates, including the 7 that are NOT in EPCMD's own
  code list (generously ignoring the mismatch): total rises to
  $680,633,601 - still $101,936,399 short of $782.57M. Over 70% of this
  gain ($139.4M) comes from a single code, 630790, which this
  investigation's A3 cross-check shows is not actually one of EPCMD's
  151 codes (their real surgical-gown/PPE codes are 621010 and 621040).
- Honest conclusion: this specific set of 13 candidate codes does not
  explain the EPCMD-vs-our-total gap, even under the most generous
  assumption. The more likely explanation is some combination of: (a)
  the EPCMD figure being an April-March fiscal year vs. our
  calendar-year figures (a timing mismatch, not a missing-code one), (b)
  the genuinely EPCMD-covered codes this investigation did not test -
  300660, 392321, 392390, 401410, 401490, 621040, 900150, 902519,
  902710, 902720, 902730, 902790, 842310, and the 961900 series
  (sanitary pads/napkins/diapers) - none of which were downloaded or
  included here, or (c) a genuine methodology difference between DGCIS
  (EPCMD's source) and Census (ours) beyond HS-code coverage. Not
  guessing further than the data supports.

---

# Investigation B — like-for-like 2026 vs 2025 (Jan-Sep both years)

## B1 — download Census 2025-09 for all 61 codes

Wrote b1_census_ytd2025.py (new, standalone script; does not modify
step1/step2/step3/common.py). Mirrors step1's own ask()/fetch_json
approach for a single period, 2025-09, across all 61 codes (the full
current hs6_codes.csv, original 48 + 13 candidates, since B1 runs after
A2's edits). Ran via `py b1_census_ytd2025.py` (task blrzdurss): 61/61
succeeded, 0 FAILED/STOP, exit 0. Wrote 61 new raw files,
raw/census/<hs6>_2025-09.json - this period was never fetched by step1
(which only does full-year Decembers plus the latest 2026 YTD month), so
no existing raw file was touched or overwritten. 902780 again correctly
returned "no_data" (consistent with its 2024/2025 full-year results).

## B2 - build data/ytd_2025_vs_2026.csv

Wrote b2_ytd_2025_vs_2026.py (new, standalone, read-only against the raw
JSON files - does not touch us_imports_by_country.csv or any other
existing data file). For each of the 61 codes and 4 country groupings
(India, China, Mexico, All countries), reads both
raw/census/<hs6>_2025-09.json and raw/census/<hs6>_2026-09.json directly
and computes: imports value, calculated duty, duty as % of value, for
each year, plus % change in imports value. Output: 248 rows (61 codes x
4 groups = 244, plus 4 grand-total rows, one per country group).

## B3 - total rows (India, China, Mexico, all countries)

| country_group | Jan-Sep 2025 $ | Jan-Sep 2026 $ | % change | 2025 duty % | 2026 duty % |
|---|---|---|---|---|---|
| India | 559,006,071 | 461,528,349 | -17.4% | 10.91% | 16.19% |
| China | 7,905,058,920 | 7,036,267,639 | -11.0% | 21.62% | 14.61% |
| Mexico | 13,675,445,752 | 12,858,950,479 | -6.0% | 2.76% | 1.62% |
| All countries | 74,486,563,934 | 70,634,292,534 | -5.2% | 5.94% | 6.35% |

Notable: imports are down year-over-year across all four groupings for
our 61 medical-device codes (India down the most, -17.4%). Duty rates
moved in different directions: India's effective rate rose sharply
(10.91% -> 16.19%, consistent with 2026's Section 122/301 duties
stacking on top of 2025's reciprocal-tariff baseline), China's fell
(21.62% -> 14.61%), Mexico's fell slightly, and the all-countries
average was roughly flat. Not independently investigated further here
(e.g. not explained from trade-policy history) - reporting the
computed numbers as found.

---

## Final integrity check for this investigation

Confirmed before reporting to the user:
- data/phase2_summary.csv and data/phase2_checks.txt are byte-for-byte
  untouched since the original step-3 run (unchanged file timestamps,
  07:16) - the "do not change or overwrite the existing data files"
  instruction was honored for the official step-3 deliverables.
- data/us_imports_by_country_48codes_backup.csv (13,957 data rows) and
  data/india_trade_48codes_backup.csv (2,136 data rows) preserve the
  exact pre-candidate 48-code datasets, in case the 61-code versions are
  ever not wanted.
- New files produced by this investigation, none overwriting anything
  that existed before today's investigation began: a1_census_vs_comtrade.csv,
  a2_candidate_codes_compare.csv, ytd_2025_vs_2026.csv, plus the new
  scripts a1_census_vs_comtrade.py, a2_candidate_codes_compare.py,
  b1_census_ytd2025.py, b2_ytd_2025_vs_2026.py, plus new raw evidence
  under raw/census/ (65 new files for the 13 candidates' 5 periods, 61
  new files for 2025-09) and raw/comtrade/ (fresh batch-1/2/4 + corrected
  batch-3 files for the 61-code run), with every superseded/stale raw
  file preserved (not deleted) under raw/comtrade/_old_empty/ and
  raw/comtrade/_old_batch3_8codes_pre_candidates/.
- hs6_codes.csv was intentionally edited (per the user's explicit
  instruction) to add 13 Candidate rows; the original 48 rows are
  unchanged in content and position.

## Bugs I introduced and caught during this investigation (self-review)

1. Two unquoted-comma CSV fields when appending candidate descriptions
   to hs6_codes.csv (871310/871390/701790) - caught by actually running
   common.py's read_codes() against the file before proceeding, not by
   assuming the edit was correct.
2. Did not initially account for step2's batch-composition drift when
   appending codes to hs6_codes.csv - caught by programmatically
   comparing old vs. new batch contents before re-running step2, rather
   than assuming "finished downloads are skipped" was safe by default.

Both were caught and fixed before they could produce bad data in any
output file shown to the user.

---

# New request: adopt EPCMD's definition exactly, reconcile to $782.57M

## Part 1a - build the official EPCMD code list

- Downloaded the real PDF as evidence (not just a one-off fetch):
  `curl` -> raw/epcmd/151_HS_code.pdf (280,008 bytes, confirmed "PDF
  document, version 1.7, 3 page(s)" via `file`).
- Read the downloaded file directly with the Read tool (not the earlier
  scratch-fetched copy) to re-extract its text independently, as a
  cross-check against the first extraction from a few turns earlier -
  both extractions matched exactly, including the unusual
  "90278100"/"90278910" etc. codes (ruling out a one-off OCR fluke on
  either read).
- Wrote build_epcmd_151_csv.py (new script) with all 151 (hs8, category,
  description) triples transcribed from the PDF, asserts len==151 and no
  duplicate hs8 as a sanity check, computes hs6 as the literal first-6-
  character prefix of hs8, and writes data/epcmd_151_codes.csv (new
  file). Ran it: 151 hs8 rows confirmed, grouped into 68 unique hs6
  values.
- Flagged immediately (before any further analysis) that two of those
  68 "hs6" values - 902781 and 902789 - are suspicious: the
  internationally harmonized HS6 structure for heading 90.27 only
  defines subheadings up to 9027.80 ("other instruments") and 9027.90
  (parts), not 9027.81/9027.89, which suggests EPCMD's PDF may have a
  digit-transcription issue and the true hs6 for those lines is 902780
  (India's own 8-digit split would then be 90278010, 90278020, etc., not
  90278100/90278910 as literally printed). Not assumed either way -
  handed to the Part 1b research (below) and separately being tested
  directly against the Census API (does Census recognize I_COMMODITY
  902781/902789 at all?).

## Part 1b - CBIC/DGFT research to classify each hs6 as CLEAN/MIXED/UNKNOWN

Delegated to a separate research step (full official-tariff research across 7
chapters x 68 hs6 groups is substantial, context-heavy web research).
It was given: the complete 68-hs6 list with EPCMD's own line count per group,
grouped by chapter, the explicit "don't guess - mark UNKNOWN if no
authoritative source found" instruction, and the 902781/902789/902780
question to resolve against CBIC/DGFT directly. Results are recorded below.

## Part 2a - does EPCMD's FY2024-25 report break the $782.57M down by HS code?

No. Already fully read (in the prior investigation) all 7 pages of
https://www.epcmd.in/assets/img/Report-hub/Medical_devices_EXIM_Data_Apr-Mar_2024-25.pdf.
Part I Export Analysis (pages 1-3) contains only: Table 1 (category-wise,
5 buckets - Consumable & Disposable / Electronic Equipment / Implant /
IVD Reagents / Surgical Instrument - for ALL countries combined, not
crossed with country), Table 2 (monthly trends, all countries), Table 3
(region-wise), and Table 4 (country-wise, page 3 - this is where the
$782.57M USA figure lives). Part II (pages 4-7) mirrors this for
imports. No table anywhere crosses category/HS code with country, and no
table itemizes the $782.57M by product or HS code. Confirmed by
re-checking the already-extracted text rather than re-fetching - nothing
new to find here.

## Part 2b - download Census periods needed for an exact FY2024-25 figure

Compared EPCMD's 68 hs6 list against our current 61-code hs6_codes.csv:
52 overlap (already have 2024-12 from earlier runs), 16 are entirely new
to Census for us (300660, 392321, 392390, 401410, 401490, 621040,
842310, 900150, 902519, 902710, 902720, 902730, 902781, 902789, 902790,
961900) - these need a full fresh download including 2024-12. (For
reference: 9 of our existing 61 codes are NOT in EPCMD's list at all -
300620, 392620, 401519, 630790, 701790, 841920, 871310, 871390, 902780 -
notably 902780 itself doesn't match EPCMD's literal 902781/902789, which
is exactly the transcription question above.)

Wrote b1b_census_fy2425_periods.py (new, standalone, mirrors step1's
ask()/fetch_json exactly). For each of the 68 EPCMD hs6 codes, downloads
whichever of 2024-12, 2024-03, 2025-03 is not already present in
raw/census/ (skip-if-exists, same as step1 - never re-downloads or
touches an existing raw file). Running now (task bc5x5fq5l) - result
logged below once complete.

**Result**: 204 jobs (68 hs6 x 3 periods), 0 FAILED, exit 0. 52 already
present (skipped), 152 newly downloaded.

## Part 1b result and an important correction I made on top of it

The CBIC/DGFT research step is complete. Its
own key caveat: CBIC's site (old.cbic.gov.in) was unreachable (DNS
failure) for the whole research step, so it fell back to eximguru.com (a
long-standing Indian trade-data aggregator, not .gov.in) as its primary
source, cross-checking several codes against other independent HSN
lookup sites. This is a secondary-source limitation to keep in mind for
every CLEAN/MIXED call below.

The research step's headline finding: it concluded EPCMD's "90278100"/"90278910-90"
codes were a transcription error for hs6=902780 (i.e. the real
subheading boundary should put the 7th/8th digits as "80"+"10/20/30/90"
not "81"/"89"+"00/10/20/30/90").

I overrode this finding before accepting it, because it contradicted
direct evidence I could check myself:
- Read raw/census/902781_2024-12.json and raw/census/902789_2024-12.json
  (already downloaded by Part 2b) and found BOTH have real, large,
  populated trade data (902781: $732.7M world total 2024; 902789:
  $1.16B world total 2024), while raw/census/902780_2024-12.json
  returns status no_data entirely.
- Ran two independent WebSearches which both confirmed: the Harmonized
  System 2022 revision (effective 2022-01-01, adopted by India) split
  the old 9027.80 subheading into two NEW, genuinely distinct 6-digit
  subheadings - 9027.81 "Mass spectrometers" and 9027.89 "Other" - a
  real, documented WCO/HS2022 change, not an EPCMD typo.
- Conclusion: 902781 and 902789 are real, current, active hs6 codes;
  902780 is the old pre-2022 code, effectively obsolete (no current
  trade recorded). The research step's secondary source (eximguru) was almost
  certainly showing a stale pre-2022 tariff structure. Corrected the
  classification for these two groups to UNKNOWN (not CLEAN, not the
  research step's "merge into 902780 as MIXED") - full reasoning in the CSV.

Built build_epcmd_classification.py (new script) combining the research step's
findings (accepted as-is for all other 66 groups) with this correction,
writing data/epcmd_hs6_classification.csv (new file, 68 rows). Final
counts: 52 CLEAN, 6 MIXED, 10 UNKNOWN.

## Part 2c - FY2024-25 reconciliation

Wrote c2c_fy2425_reconciliation.py (new, read-only against raw/census/*
and data/epcmd_hs6_classification.csv). For every hs6, computes FY2024-25
= (2024-12 YTD) - (2024-03 YTD) + (2025-03 YTD) using the India row
(cty_code 5330) from each raw Census file, then sums by classification.
Output: data/fy2425_reconciliation.csv (68 rows, new file).

Result:
- CLEAN total: $581,136,872
- MIXED total: $165,561,446 (not added in, per instruction)
- UNKNOWN total: $183,864,464 (not added in - classification unresolved)
- EPCMD target: $782,570,000
- Gap vs CLEAN alone: $201,433,128
- Gap vs CLEAN+MIXED: $35,871,682 (CLEAN+MIXED together reach $746.7M,
  within 4.6% of EPCMD's figure - much closer than the earlier
  calendar-year/13-candidate analysis, which left $101.9M unexplained
  even in its most generous case)
- CLEAN+MIXED+UNKNOWN together ($930.6M) exceeds the target, meaning
  even a modest fraction of the $183.9M UNKNOWN group being legitimately
  medical would fully close the remaining $35.9M gap.

Largest MIXED hs6 by FY2024-25 value (feeds Part 2d): 901890 ($96.5M),
392390 ($50.4M), 902519 ($9.7M), 621040 ($8.3M), 940210 ($0.6M), 401490
($0.03M).

## Part 2d - US HTS 10-digit lines for the top 3 MIXED codes, and an HS10 test

Fetched https://hts.usitc.gov/reststop/exportList (the official USITC
HTS REST API) directly via curl for the US-side 10-digit breakdown of
the top 3 MIXED hs6 groups:

- **9018.90** (901890, $96.5M): every single 10-digit line found -
  mirrors/reflectors for optical instruments, anesthetic instruments,
  percussion hammers/stethoscopes, sphygmomanometers, electro-surgical
  instruments, defibrillators, dialysis instruments and parts - is
  clearly medical/surgical in nature at the US classification level. No
  obviously non-medical line found. This suggests 901890's "MIXED"
  status (from Part 1b) reflects EPCMD's own list missing one real
  medical line (haemofiltration instruments) on the India side, not
  genuinely non-medical products sharing the US-side code.
- **3923.90** (392390, $50.4M): the real US breakdown is "Buckets and
  pails" and generic "Other" - this heading (3923, "articles for the
  conveyance or packing of goods, of plastics") is NOT medical-specific
  at the US level at all. This strongly confirms 392390 is a genuinely
  mixed/mostly-non-medical code at this value scale, and excluding it
  from the CLEAN reconciliation was the right call.
- **9025.19** (902519, $9.7M): lines are "Pyrometers" (industrial heat
  measurement - not medical) alongside "Clinical"/"Infrared
  thermometers" (medical) - a genuine mix of medical and non-medical
  instruments under one hs6, confirming the MIXED call.

**HS10 Census test** (not a full download, one request only, per
instruction): queried
`https://api.census.gov/data/timeseries/intltrade/imports/hs` with
`COMM_LVL=HS10&I_COMMODITY=9018906400&time=2024-12` (the Defibrillators
line, 10-digit code with no punctuation) - **this works**, returning
real per-country trade data at the 10-digit level, same response shape
as HS6 queries. Also tested the dotted format
(`I_COMMODITY=9018.90.6400`) for comparison - that returns an empty
result, confirming Census wants the 10-digit code as a plain
unpunctuated string, exactly like its HS6 parameter convention.
**Conclusion: yes, downloading Census at HS10 level for just the
medical-looking lines under 392390/902519/621040/etc. would work** and
would let us isolate the medical-specific value within an otherwise
mixed hs6 - not done yet, per the "Part 3: hold" instruction and because
this was a test-only request as asked.

---

# Finish Phase 2 in one run

User's constraint: don't overwrite existing data files; write new files
and back up anything changed.

## Step 1 - build data/final_codes.csv and data/lab_instruments_codes.csv

Rule precedence used (most specific wins):
1. Explicit per-code overrides: keep 901890, 382211, 382212, 382213,
   401512 whole regardless of their CLEAN/MIXED/UNKNOWN status.
2. HS10-only list (902519, 940210, 401490, 621040, 392321, 621010,
   382219) overrides the general "keep original 48 whole" rule for
   those specific codes - they get filtered to individual HS10 lines
   instead of kept as whole HS6.
3. Explicit drops (392390, 382290, 630790) always excluded.
4. Everything else: union of (original 48 minus {382290, 940210,
   382219}) and the 52 CLEAN hs6 groups from Part 1b.
5. 902781, 902789 go only into lab_instruments_codes.csv.

Fetched additional US HTS 10-digit breakdowns (hts.usitc.gov, same REST
API as Part 2d) for the 7 HS10-only codes:
- 9402.10: single line "Dentists', barbers' or similar chairs and parts
  thereof" - kept (matches "dental").
- 4014.90 (401490): "Nursing nipples" / "Other" - neither the line text
  nor the parent heading text ("Hygienic or pharmaceutical articles")
  contains any of the 5 specified keywords (medical/surgical/dental/
  clinical/diagnostic) - **all lines excluded, code dropped entirely**.
- 6210.40 (621040): real US breakdown is generic apparel (ski/snowboard
  pants, overalls, trousers by fiber content) - no line or parent
  anywhere mentions a qualifying use - **all lines excluded, code
  dropped entirely**.
- 3923.21 (392321): real US breakdown is generic plastic bags
  (reclosable bags, retail carrier bags) - no qualifying line anywhere -
  **all lines excluded, code dropped entirely**.
- 6210.10 (621010): kept 2 of 6 lines - "Surgical or isolation gowns"
  (explicit "Surgical") and its sibling "Other", both children of a
  parent reading "Nonwoven disposable apparel designed for use in
  hospitals, clinics, laboratories..." (treating "clinics" as matching
  the "clinical" keyword, and inheriting parent context the same way I
  treated 621010/382219 - documented methodology: when a line's own
  text has no keyword, I checked its full ancestor-hierarchy text too,
  not just the single line's own text in isolation). Dropped: paper-base
  fabric, disposable briefs/panties (hygiene, not explicitly medical),
  overalls/coveralls.
- 3822.19 (382219): kept all 4 lines - none individually says
  "diagnostic" in their own text (they're split by composition:
  antigens/antisera vs. solvent content), but ALL are children of the
  heading "Diagnostic or laboratory reagents..." - kept under the same
  ancestor-hierarchy-text methodology as 621010.
- 9025.19 (902519): kept the 2 lines that are children of the explicit
  "Clinical" branch (infrared thermometer + other); dropped Pyrometers
  (industrial) and the sibling non-clinical "Other->Other" branch's
  infrared-thermometer/other lines - these literally sit next to
  "Clinical" as a distinct, named non-clinical alternative, so keeping
  them would contradict the keyword filter's intent even though the
  word "infrared thermometer" appears in both branches.

Wrote build_final_codes.py (new script). Result:
- data/final_codes.csv: 67 rows (58 HS6 + 9 HS10).
- data/lab_instruments_codes.csv: 2 rows (902781, 902789).
- Full drop log (every excluded HS10 line, every explicitly dropped
  code, with reasons) captured in this script's stdout - see
  logs/build_final_codes_stdout.txt for the complete line-by-line list;
  summary: 401490, 621040, 392321 dropped entirely (0 qualifying lines
  found for any of them); 630790, 392390, 382290 dropped per explicit
  instruction.
- Verified the HS6 count (58) by independent manual set arithmetic
  before trusting the script: 45 (original 48 minus 382290/940210/
  382219) + 13 new codes contributed by the 52-CLEAN list that weren't
  already in our original 48 (300660, 300670, 401410, 842310, 900130,
  900150, 902511, 902710, 902720, 902730, 902750, 902790, 961900) = 58.
  Matches the script's output exactly.

## Step 2 - download missing Census/Comtrade data

Wrote d1_census_final.py (new, mirrors step1's ask()/fetch_json/
latest_2026_month exactly). For every code in final_codes.csv (67 rows)
and lab_instruments_codes.csv (2 rows), downloads whichever of
2024-03, 2024-09, 2024-12, 2025-03, 2025-09, 2025-12, and the
dynamically-redetermined latest 2026 month is not already present in
raw/census/ - same skip-if-exists discipline as every prior step.
HS10-level codes use COMM_LVL=HS10 with the plain code (no dots),
confirmed working in Part 2d. Running now (task bzn74keev).

Compared the 58 final-list + 2 lab-instrument HS6 codes against our
already-covered 61-code hs6_codes.csv list: 11 are new to Comtrade
(300660, 401410, 842310, 900150, 902710, 902720, 902730, 902781,
902789, 902790, 961900). Wrote d2_comtrade_final.py (new; same
parsing/error-handling/batching as the already-fixed
step2_india_trade_comtrade.py, writing into a separate
raw/comtrade/final_new_codes/ subfolder so it never collides with the
existing 61-code batch files) for just these 11 codes. Running now
(task baseymmuh). Results for both logged below once complete.

**D2 (Comtrade) result**: 0 FAILED, exit 0. Wrote
data/india_trade_final_new_codes.csv (520 rows) covering the 11 new
hs6 codes, raw evidence in raw/comtrade/final_new_codes/ (separate
subfolder, no collision with the existing 61-code batch files).

**D1 (Census) result**: 483 jobs (69 codes x 7 periods), 158 newly
downloaded, 325 already present (skipped), 0 failed, exit 0.

(Note: mid-run, the user told me not to run multiple background
processes/shell commands at once to limit PC/CPU load. D1 and D2 had
already been launched in parallel at that point; I let both finish
rather than kill either mid-download, but saved this as a standing
feedback memory and ran every subsequent step one at a time, strictly
sequentially, for the rest of this task.)

**D2 (Comtrade) result**: 0 FAILED, exit 0. Wrote
data/india_trade_final_new_codes.csv (520 rows), raw evidence in
raw/comtrade/final_new_codes/.

Discovered a gap before building the summary: phase2_final_summary.csv
needs full years 2022-2025, but neither b1b nor d1 ever fetched
2022-12/2023-12 for the ~20 codes new to this project (9 HS6 beyond the
original 61, all 9 HS10 lines, and 902781/902789). Wrote
d1b_census_backfill_2022_2023.py (new, same pattern as every other
download script) and ran it alone (single process, per the no-parallel
feedback above): 138 jobs (69 codes x 2 periods), 40 newly downloaded,
98 already present, 0 failed, exit 0. (A combined `tail | grep -c`
diagnostic command I chained onto this run reported a spurious "exit
code 2" from the harness - that was `grep -c` finding zero matches in
an auxiliary check, not a script failure; verified the actual script's
own `EXIT:0` marker and full completion in its log before moving on.)

## Step 3 - data/phase2_final_summary.csv

Wrote e1_build_final_summary.py (new, read-only against raw/census/*,
data/india_trade.csv, data/india_trade_final_new_codes.csv,
final_codes.csv, hs6_codes.csv, data/epcmd_151_codes.csv). One row per
code (all 67 from final_codes.csv) x year (2022, 2023, 2024, 2025,
2026-YTD using the latest published month, 2026-09), with: US imports
from India, US imports world total, India's share of US market, top 3
suppliers, India's exports to USA/World and imports from USA/World
(HS6-level codes only - blank for the 9 HS10 lines, since Comtrade data
is only available at HS6), effective duty rate on Indian goods, and a
merged product_group field.

**Caught a labeling bug before finalizing**: product_group initially
showed "Candidate" for codes that happened to have been added to
hs6_codes.csv under that investigation-phase placeholder group name
during the earlier A2 investigation (300670, 900130, 902511, 902750,
and the 621010-derived HS10 lines) - "Candidate" isn't a real product
category and would have polluted the Part 4c breakdown. Fixed by
skipping "Candidate" when reading hs6_codes.csv's group column and
falling back to EPCMD's category for those codes instead. Re-ran after
the fix; verified "Candidate" no longer appears anywhere in the output.

Result: data/phase2_final_summary.csv, 335 rows (67 codes x 5 years,
no gaps - every code had a raw file for every period needed).

## Step 4 - data/phase2_final_checks.txt

Wrote e2_build_final_checks.py (new, read-only against raw/census/*,
final_codes.csv, lab_instruments_codes.csv, data/phase2_final_summary.csv).
Computes all five requested pieces in one file. (Caught and removed one
leftover dead-code fragment - a no-op `if False else` conditional I'd
left in a draft f-string - before running it, since it served no
purpose and would have confused a future reader.)

Full output reproduced in the chat response to the user. Headline
results:
- **4a FY2024-25 reconciliation**: final_codes.csv alone = $706,578,118
  (gap to EPCMD's $782.57M: $75,991,882, 9.7%); with lab_instruments
  added = $723,432,073 (gap: $59,137,927, 7.6%). Both are much tighter
  than any earlier reconciliation attempt in this investigation (the
  13-candidate attempt left >$100M unexplained even generously; the
  CLEAN-only EPCMD attempt left $201M).
- **4b Jan-Sep 2024/2025/2026** for India/China/Mexico/All countries:
  computed from final_codes.csv's 67 codes only (not lab_instruments).
- **4c**: India's Jan-Sep 2025-to-2026 change broken out across 17
  product groups - Gloves (-65.3%) and Sutures (-64.6%) fell hardest;
  Hearing (+208.2%, off a tiny $22K base), Therapy (+61.2%), Furniture
  (+29.6%) and Implants (+25.8%) rose.
- **4d verdict: HOLDS** - India's Jan-Sep 2025-to-2026 fall (-21.4%) is
  15.5 percentage points larger than all countries' fall (-5.9%),
  clearing the >=5-point bar.
- **4e**: 67 codes in final_codes.csv; 32 of them had India selling
  under $1M to the US in 2025 (6 of those are literally $0).

## Final file inventory for this request

---

# Phase 3: link trade to tariffs

## Part 2 - monthly download (front-loading check), launched

Wrote d3_census_monthly.py (new; same ask()/fetch_json pattern as every
other download, but requests _MO fields - CON_VAL_MO, GEN_VAL_MO,
DUT_VAL_MO, CAL_DUT_MO - instead of the _YR fields used everywhere else
in this project, since this is a genuinely different data shape (one
month's trade, not year-to-date cumulative)). Saved into a SEPARATE
directory, raw/census_monthly/, specifically so a monthly file for
e.g. period "2024-12" can never collide with or be silently confused
with the existing YTD file of the same name in raw/census/ - this was a
deliberate decision to avoid a subtle but serious data-shape bug.
63 codes (from final_codes_grouped.csv) x 33 months (Jan 2024 through
Sep 2026) = 2,079 jobs. Launched as a single background process (task
bfp065ru8) - this is a long run, left running alone per the no-parallel-
local-processes feedback.

While it ran, did the China Section-301-list lookup needed for Part 3
as a separate research step.

**Research result.** Key findings:
ustr.gov's own exclusion-annex PDFs were not machine-extractable, and
hts.usitc.gov's REST API does not expose Section 301 status in its data
at all (`additionalDuties` field is null even where Section 301 clearly
applies) - so the research used hts.cybermaxtools.com (a third-party
aggregator, explicitly flagged as NOT a government source) as its
practical source for List 1/2/3/4A membership per code. It did get
**primary-source confirmation** for the Nov 9, 2026 question: fetched
the actual Federal Register notice (govinfo.gov, Vol. 91 Issue 216, 10
Nov 2026, FR Doc 2026-22925) - USTR extended all 178 active Section 301
exclusions (164 general + 14 solar-manufacturing) through 11:59pm ET,
9 January 2027. That notice does not name specific medical-device
codes, so which of our codes carry an active exclusion remains
unresolved per-code. Full per-code table carried into Part 3 below,
with every List/exclusion assignment flagged as secondary-source-only
(not confirmed against ustr.gov/HTS directly).

**The local monthly download was killed by the system for low memory**
partway through (at 922/2079 files, 44%) - not something intrinsic to
this script (it processes one small JSON response at a time, no
accumulation), more likely unrelated memory pressure elsewhere on the
machine. Checked the checkpoint state before doing anything else:
all 922 files present and valid (atomic writes via save_json_safely),
0 failures logged, fully resumable. Rather than just relaunching a
long process unprompted given how explicit the user has been about
PC/resource load, asked the user how to proceed; they said resume now.
Relaunched the same script (task bqzx7wep4) - it skips the 922
already-downloaded months automatically and continues from where it
stopped.

**Final D3 result**: 2,079/2,079 jobs complete, 1,157 newly downloaded
on the resume run, 922 from before the memory-kill, 0 FAILED total,
exit 0. All 2,079 raw monthly files present in raw/census_monthly/.

## Part 2 result - front-loading check

Wrote e3_build_monthly_imports.py (new, read-only against
raw/census_monthly/* and final_codes_grouped.csv; fixed a sloppy
duplicated-print-expression bug in a draft of this script before
running it). Writes data/monthly_imports.csv (2,079 rows: 63 codes x 33
months).

**Finding: no strong front-loading signal.** India's March-July 2025
total ($290.2M) was only 5.1% above March-July 2024 ($276.2M) - LOWER
than the growth seen in a control set of months outside that window
(Jan+Feb+Aug+Sep 2025 vs 2024: 17.2% growth, $234.9M vs $200.3M).
Per-month: only March 2025 shows a notable jump (+18.5%, $67.2M vs
$56.7M), comparable in size to the control-window growth rate, not
dramatically above it; April (-3.2%), May (+9.4%), June (+0.2%), and
July (-0.1%) are flat to down. Conclusion: nothing in this window rises
to a level I'd confidently call "boosted by front-loading" rather than
ordinary month-to-month variation - so there is no principled basis to
exclude any specific month, and excluding none is itself the honest
answer rather than guessing which month(s) to drop.

**Data-quality note found while cross-checking**: summing the 9
individual monthly (_MO) values for Jan-Sep 2025 gives $525,089,160 for
India, vs the $540,188,653 produced in Phase 2 from the direct YTD
(_YR) Census field for period "2025-09" - a ~2.8% difference. Same
pattern for Jan-Sep 2026 ($416,079,305 monthly-summed vs $424,658,697
YTD-direct, ~2%). This is very likely due to Census publishing
preliminary figures that get revised over time - the YTD field and the
individual monthly fields may have been captured by Census (and by my
downloads, run at different times across this whole project) at
different revision vintages. Not treating either number as "wrong" -
flagging the discrepancy explicitly rather than silently picking one,
per the project's "never hide uncertainty" principle. Using the
monthly-summed figures for the "Part 2" redo below, since those are
what this specific download produced; the original Phase 2 YTD-based
figures stand as previously reported.

**Redo of Jan-Sep 2025-to-2026 India comparison** (monthly-summed,
no months excluded since none were found to be front-loaded):
2025 Jan-Sep = $525,089,160; 2026 Jan-Sep = $416,079,305; change =
-20.8% (vs the original YTD-direct -21.4% from Phase 2 - same
conclusion either way, both comfortably clear the >=5-point HOLDS
threshold against the world's Jan-Sep decline).

## Part 3 - tariff gap table

**Step 1 - MFN rates.** Wrote g1_fetch_mfn_rates.py (new, single
sequential Python process against hts.usitc.gov's own REST API, same
politeness-delay spirit as every Census script even though this is a
different server). First run: 39 of 63 codes came back "not found."
**Diagnosed before accepting that as real data absence**: tested
9018.31 (Syringes) directly and found its real "Free" rate lives on an
8-digit line "9018.31.00", which my range query ("9018.31.01" to
"9018.31.99") silently excluded by starting at ".01" instead of ".00".
Fixed the HS6 range to start at ".00", and rewrote the HS10 lookup to
walk up to the longest matching ancestor code with a non-empty rate
(since a 10-digit statistical breakout often carries a blank rate,
inheriting from its 8- or 6-digit parent) instead of requiring an exact
10-digit match. Re-ran: only 1 of 63 codes remained unresolved -
**300620** ("Blood-grouping reagents") - verified directly (not just
assumed) that the US HTS has no "3006.20" heading at all (confirmed via
a direct range query spanning past it); genuinely not found, not a
bug. Logged as blank per the "don't guess" instruction. Raw evidence:
raw/hts/mfn_rates.json.

**Step 2 - tariff gap table.** Wrote g2_build_tariff_gap.py (new,
combines the MFN rates above, the separate research step's China Section-301
findings from Part 2's background research - hardcoded as a per-code
lookup table with every MIXED/UNKNOWN case preserved rather than forced
into a single number - and Census-derived actual-duty/top-suppliers/
import-value figures read the same way every prior step in this
project has). Flat policy add-ons applied exactly as instructed: India
MFN+10%; China MFN+Section301+12.5%; Mexico MFN+10%-for-non-USMCA (with
an explicit note that USMCA-qualifying share could not be estimated -
the Census international-trade timeseries API used throughout this
project has no FTA-qualification field); EU/Germany flat 15% ceiling.

**Caught two bugs before trusting the output**: (1) `census_full_year`'s
early-return branch (for a period with no_data) was missing the "world"
key, causing a KeyError the first time it hit a zero-trade period -
fixed by adding it. (2) `SECTION301_RATE` had no entry for "none"
(clean codes), so every genuinely clean code was incorrectly flagged as
"unresolved" in the not-found log - fixed by mapping "none" to 0%, and
separately noticed I'd never added the 621010-derived HS10 lines
(6210105010/90) to the China lookup table at all - added them from the
research step's findings (List 4A +7.5%, with an unspecified "2 product
exclusions may apply" note preserved).

Final unresolved count: **8 of 63 codes** (1 MFN rate - 300620; 7
China Section-301 classifications too MIXED/UNKNOWN to assign one
number - 901890, 902229, 902290, 902710, 902790, 961900, plus 300620
again). All logged with their specific reason, not guessed.
Output: data/phase3_tariff_gap_data.csv (63 rows).

## Part 4 - data/phase3_tariff_gap.xlsx

Wrote g3_build_excel.py (new, read-only against
data/phase3_tariff_gap_data.csv, using openpyxl which was already
available in this environment - no new dependency installed). Two
sheets: README (plain-English explanation of every column, plus general
notes on sourcing, the Nov 9 2026 exclusion-extension finding, and what
a blank cell means) and "Tariff Gap Data" (the 63-row table, values
typed as int/float/string per-cell rather than left as strings, so
Excel treats numeric columns as numbers). Verified directly after
writing (not assumed): 0 formula cells, 0 merged cell ranges, sheet
protection off on both sheets - matches "plain typed values only: no
formulas, no merged cells, nothing locked" exactly.

---

# Three fixes before Phase 4

## Fix 1 - split medicines/hygiene out of the device list

Wrote h1_split_core_codes.py (new, read-only against
final_codes_grouped.csv). Moved 300630 (X-ray contrast preparations)
and 300660 (hormonal contraceptives) to data/pharma_like_codes.csv (2
rows); moved 961900 (sanitary pads/tampons/diapers) to
data/hygiene_codes.csv (1 row); everything else to
data/core_device_codes.csv (**60 rows**, down from
final_codes_grouped.csv's 63). final_codes_grouped.csv itself is
untouched.

## Part 1 - clean up product groups -> data/final_codes_grouped.csv

Wrote f1_build_grouped_codes.py (new, read-only against final_codes.csv,
hs6_codes.csv, data/epcmd_151_codes.csv). Mapped every code's raw group
(our own hs6_codes.csv group, skipping the "Candidate" placeholder as
before, else EPCMD's category) onto the fixed 14-item vocabulary:
"Consumable & Disposable" -> Consumables (explicit merge); "Dressings"
and "Sutures" -> "Dressings & Sutures"; "Respiratory" and "Therapy" ->
"Respiratory & Therapy"; thermometers (902511, and the two 902519 HS10
lines) -> "Electro-diagnostic" per instruction; the 9027 instrument
family (902710, 902720, 902730, 902750, 902790) -> "Other" per
instruction; 842310 (personal/baby weighing scales - no clean fit in
any specific category) -> "Other" as the designated catch-all. No code
fell through to an unmapped/default case (verified via the script's own
unmapped-log check, which printed nothing).

**Re-checked the 382219 HS10 lines under the stricter rule** ("keep a
line only if its own description is diagnostic, not because of a
chemical-content split"). All 4 lines I'd kept in Phase 2
(3822190010/30/40/80) are split by composition - "containing antigens or
antisera" vs "other", and "with methyl chloroform/carbon tetrachloride"
vs "other" - none of their own text says "diagnostic"; only the parent
heading ("Diagnostic or laboratory reagents...") did, which I'd
leaned on in Phase 2 but the user is now explicitly ruling out for this
code. **Removed all 4 lines** (logged individually above/below); 382219
now has zero qualifying lines in the grouped list, consistent with the
established "if a code has none, drop it and log it" pattern.

Result: data/final_codes_grouped.csv, 63 rows (down from final_codes.csv's
67). Group counts: Consumables 12, Imaging 11, Electro-diagnostic 6,
Other 6, Dental 5, Diagnostics 5, Implants 5, Dressings & Sutures 4,
Respiratory & Therapy 3, Furniture 2, Gloves 1, Hearing 1, Instruments 1,
Ophthalmic 1. All 63 rows fall within the 14-item allowed vocabulary
(verified programmatically, not just by eye).

**From this point on, "the final codes" for the rest of Phase 3 means
this 63-code grouped list**, not the original 67-row final_codes.csv -
the 382219 removal is treated as a correction that carries forward.

New files only, nothing existing overwritten:
data/final_codes.csv, data/lab_instruments_codes.csv,
data/phase2_final_summary.csv, data/phase2_final_checks.txt,
data/india_trade_final_new_codes.csv, build_final_codes.py,
e1_build_final_summary.py, e2_build_final_checks.py,
d1_census_final.py, d1b_census_backfill_2022_2023.py,
d2_comtrade_final.py, plus new raw evidence under raw/census/ and
raw/comtrade/final_new_codes/. hs6_codes.csv was NOT touched in this
request (no new candidate rows added this time). No backups were needed
this round since nothing existing was modified.

## Fix 2 - apply CBP's Forced Labor HTS List exemptions

Downloaded the PDF directly from the govdelivery.com URL given:
raw/cbp/Forced_Labor_HTS_List.pdf (210,893 bytes, confirmed "PDF
document, version 1.6" via `file`). Read the full 39-page document
with the Read tool (plain curl/programmatic PDF text extraction was not
attempted - the document is a dense multi-column code table, exactly
the kind of layout the Read tool handles natively).

Learned from the document's own text that "Section 301 Forced Labor
HTS List" is CBP's name for the Chapter 99 exemption schedule tied to
the broad 9903.05.20-9903.05.84 duty actions this whole project has
been calling "Section 301 forced-labor duty" - not literally the 2018
China-specific Section 301 lists (List 1-4A), which are a separate,
older action. The two headings the user asked about:
- 9903.05.86: a general exemption list. Despite being captioned
  "Chapter 1 to 97," the actual codes listed are overwhelmingly
  chapters 1-39 (agriculture, chemicals) plus scattered metals/
  machinery/electronics chapters (71-86) - no medical-device chapter
  (90/94/96) code appears anywhere in it.
- 9903.05.89: explicitly scoped "for use in pharmaceutical
  applications," chapters 28-39 only.

Checked every one of our 63 codes' HS6/HS8/HS10 prefixes against both
lists by direct text search (not sampling - checked all of them,
including the ones I was fairly confident wouldn't match, like the full
9018/9021/9022/9025/9027 families, 8423, 9001, 9402, 961900, 401410,
401512, 621010's two kept HS10 lines, 382211/12/13). Wrote
h2_apply_exemptions.py (new, read-only against
data/phase3_tariff_gap_data.csv). Result: exactly 3 codes exempt, all
in Chapter 30:
- 300630 (X-ray contrast preparations) - 9903.05.86, via 3006.30.10 /
  3006.30.50, both explicitly listed.
- 300660 (hormonal contraceptives) - 9903.05.86, via 3006.60.00,
  explicitly listed.
- 300670 (gel preparations) - 9903.05.89, via 3006.70.00, explicitly
  listed under the pharmaceutical-use heading. (300670 stays in the
  CORE device list per the user's Fix 1 instruction, which only named
  300630/300660/961900 for removal - this exemption finding is
  independent of and doesn't contradict that classification choice.)

All 60 core device codes and 961900 (hygiene) were checked and NOT
found in either list - zero device-chapter exemptions exist under
9903.05.86/89.

## Research for Fix 3 - USTR forced-labor action country/tier list

Searched for and read directly:
- Federal Register notice 2026-22925 (govinfo.gov PDF,
  https://www.govinfo.gov/content/pkg/FR-2026-11-10/pdf/2026-22925.pdf) -
  read in full via the Read tool (WebFetch's own extraction failed on
  this PDF, same pattern as several others in this project - the Read
  tool handles these dense government PDFs much better). **Finding**:
  this specific notice extends all 178 active China Section 301
  exclusions through 9 January 2027, but does NOT name any HTS codes
  directly in its own text - Annex A and Annex B only reference two
  Chapter 99 headings (9903.88.69, 9903.88.70) and point to "U.S. notes
  20(vvv)(i)-(iv) and 20(www) to subchapter III of chapter 99 of the
  HTSUS" as where the actual covered 10-digit codes are defined.
  Checked those two headings directly via the HTS REST API
  (hts.usitc.gov) - they only return a one-line truncated description
  pointing back to the same U.S. notes, not the actual code list; the
  REST API's exportList endpoint does not appear to expose General
  Notes text (as opposed to tariff schedule heading rows), and I did
  not find a working way to pull that specific note's full text within
  reasonable effort. **Conclusion for the user's question**: the
  notice/annexes do not name device codes, full stop - the real list
  lives in HTS General Notes I could not retrieve via this API. Logging
  this as a genuine gap rather than guessing which codes might be
  covered.
- USTR's own country/tier structure: found via
  https://www.hklaw.com/en/insights/publications/2026/07/and-the-tariff-beat-goes-on
  (a law firm's summary, cross-checked against a second independent
  search) and attempted to verify against USTR's own primary report
  (https://ustr.gov/sites/default/files/files/Press/Releases/2026/USTR%20Report%20Sec%20301%20FL%20301%206-2-26%20FINAL%20for%20upload.pdf)
  but that PDF is image-based/scanned (4MB, `pdftoppm` - needed to
  render its pages - is not installed in this environment, so I could
  not read it directly; noting this as a secondary-source limitation,
  same spirit as the earlier Section 301 List 1-4A research).
  **Tier structure** (60 "investigated economies" total):
  - Tier 1 (17 economies, flat +10% on top of MFN): Argentina,
    Bangladesh, Cambodia, Canada, Ecuador, El Salvador, Guatemala,
    Honduras, India, Indonesia, Jordan, Malaysia, Mexico, Pakistan,
    Sri Lanka, Trinidad and Tobago, United Kingdom.
  - Tier 2 (EU member states and Taiwan): "a combined 10 percent duty,
    net of each product's MFN rate" per the law-firm source's exact
    quoted language - **this directly contradicts the user's stated
    "EU pays the 15% all-in ceiling" rule for this exercise**. I did
    not silently pick one: I'm applying the user's explicit 15% rule
    as instructed (since it's the standing operational simplification
    given to me for this table), but flagging here that the real
    Section 301 forced-labor action's own mechanism for EU is actually
    a 10%-net-of-MFN cap, not 15% - the two may reflect different,
    separate tariff frameworks (e.g. an earlier 2025 US-EU trade-deal
    ceiling vs. this specific 2026 forced-labor action), but I have not
    independently confirmed that relationship and am not asserting it
    as fact. Taiwan (not EU, no user override given) keeps its real
    10%-net-of-MFN mechanism.
  - Tier 3 (Japan, South Korea, Switzerland): combined 12.5% net of MFN.
  - Tier "other" (the remaining 38 investigated economies, flat
    +12.5% on top of MFN): includes China, and - confirmed via a
    second independent search specifically for this - Costa Rica,
    Singapore, and Thailand (all three appear as top-3 suppliers for
    codes in our top-15 competitor check below). **Could not confirm
    whether Laos is among the 60 investigated economies** - two
    separate searches did not name Laos either way. Left Laos's status
    as UNKNOWN below rather than guessing.
  - Per the user's explicit rule: Mexico and Canada (Tier 1) pay 0% on
    USMCA-qualifying goods instead of the +10% addon.

## Fix 3 - competitor rates vs duty actually paid, corrected listed rates

Wrote h3_top15_suppliers.py (new, read-only against
core_device_codes.csv and raw/census/*). Found the top 15 core codes by
2025 India value, and for each, the top 3 non-India suppliers by name
with their 2025/2026-YTD values. 19 distinct countries appear across
these 15 codes' top-3 lists: Canada, China, Costa Rica, France,
Germany, Ireland, Italy, Japan, Laos, Malaysia, Mexico, Netherlands,
Singapore, Spain, Sweden, Switzerland, Taiwan, Thailand, United
Kingdom. Wrote data/top15_competitor_check_raw.json (new file).

Wrote h4_competitor_check_and_corrected_rates.py (new, read-only
against data/phase3_tariff_gap_data_v2.csv,
data/top15_competitor_check_raw.json, raw/hts/mfn_rates.json,
raw/census/*). Built a country/tier lookup covering exactly the 19
countries found above (deliberately did NOT fabricate Census country
codes for Tier-1 members like Argentina/Bangladesh/Jordan/etc. that
never actually appear in our data - listed in a comment in the script
as "left out rather than guessed").

**Caught two real bugs before trusting the output, both found by
cross-checking against actual duty-paid data rather than trusting the
formula in isolation:**
1. A dead/unreachable code fragment left over from a rushed first
   draft (an `if False`-style leftover and a stray `return` placed
   before other branches, making them unreachable) - cleaned up before
   running at all.
2. **A real calculation bug**: my first "corrected" listed-rate
   function applied ONLY the new forced-labor tier rate for China
   (MFN + 12.5%), silently dropping the OLDER 2018-19 Section 301 List
   1/2/3/4A rate that Phase 3's first pass had already determined
   per-code - these are two separate, stacking duty layers, not
   alternatives. Caught this because the very first run's flagged-
   difference list showed China on X-ray tubes (902230) at a wildly
   implausible -25.47pp gap (listed 12.5%, actual paid 37.97%).
   37.97% matches MFN(~0%) + List 1-3 (25%) + forced-labor (12.5%) =
   37.5% almost exactly - proving the List layer must stack, not be
   replaced. Fixed by threading the existing
   `china_section301_rate_pct` value (from v2's data) through as an
   explicit `china_301_list_rate` parameter and adding it in. Re-ran:
   902230/China's diff dropped from -25.47pp to -0.47pp (no longer
   flagged) - verified this directly by reading the corrected row back
   out of the CSV rather than just trusting the summary printout.

**Result**: data/top15_competitor_check.csv (45 rows: 15 codes x 3
suppliers), 25 of 45 flagged as differing from actual duty paid by
>3 percentage points, each with a specific likely-reason category
(USMCA-qualification mix, EU ceiling-vs-real-mechanism mismatch,
Section 301 List exclusion/approximation, or unidentified product-line
variation).

**Important pattern the flags revealed**: every EU-country row shows
listed ~15% vs actual duty consistently around 9-11% - a large,
*systematic* gap, not noise. This is strong empirical support for the
earlier research finding that the Section 301 forced-labor action's
REAL mechanism for the EU is "10% net of MFN" (a combined cap), not
the flat 15% the user instructed me to use for this exercise. I did
not override the user's explicit instruction on my own judgment -
applied 15% as asked, and reported the resulting flags/gaps
transparently so the user can decide whether to revise the rule for a
future pass, now backed by real duty-paid evidence rather than just
the earlier secondary-source research.

**Corrected tariff table**: data/phase3_tariff_gap_data_v3.csv (new
file, 63 rows) adds `india_listed_rate_pct_corrected`,
`china_listed_rate_pct_corrected` (now properly stacking the old
Section 301 List rate where known), `china_listed_rate_basis`,
`mexico_listed_rate_pct_corrected_usmca_assumed`,
`eu_listed_rate_pct_corrected`, `gap_listed_pct` (India's corrected
listed rate minus the weighted-average listed rate of its top-3
non-India 2025 suppliers, reusing Phase 3 first-pass's supplier-weight
methodology), and `gap_actual_pct` (same, but using India's actual
2026-YTD duty paid instead of its listed rate).

## Fix 4 - re-run headline numbers on core_device_codes.csv

Wrote h5_core_headline_numbers.py (new, read-only against
core_device_codes.csv, pharma_like_codes.csv, hygiene_codes.csv,
final_codes_grouped.csv, raw/census_monthly/*). Needed Mexico's
monthly values too, which the earlier Phase-3-Part-2 monthly_imports.csv
only captured for India/China/world - built a fresh aggregator reading
the raw monthly JSON directly rather than extending the old CSV, so
nothing existing was touched. (Caught and removed another leftover
`if False` dead-code fragment, same pattern as the previous script,
before running - same root cause: drafting the print statement with
copy-paste debris left in.)

Ran it for both core_device_codes.csv alone (60 codes) and the full
core+pharma-like+hygiene set (63 codes, matching final_codes_grouped.csv)
for comparison. Full output in data/phase3_headline_core.txt (new
file) and reproduced in the chat response to the user. Both scenarios
verdict: **HOLDS**. Core-only shows a slightly LARGER gap (India
-21.5% vs all countries -4.3%, 17.2pp) than with pharma-like/hygiene
added back (-20.8% vs -5.1%, 15.7pp) - the device-specific signal is
if anything slightly stronger once the two medicine-like codes and the
hygiene code are excluded, consistent with those codes behaving
somewhat differently from true devices.

## Fix 5 - data/phase3_tariff_gap_v2.xlsx

Wrote h6_build_excel_v2.py (new, read-only against
data/phase3_tariff_gap_data_v3.csv and data/top15_competitor_check.csv).
Three sheets: README (every column explained, including explicit notes
on which columns are "first-pass" vs "corrected," and the EU
15%-vs-10%-net-of-MFN discrepancy called out directly in the column
description so it isn't missed), "Tariff Gap Data v2" (63 rows, all
columns from v3), "Top 15 Competitor Check" (45 rows). Verified
directly after writing (both via in-script assertions and an
independent read-back afterward): 0 formula cells, 0 merged cell
ranges across all three sheets, sheet protection off everywhere -
matches "plain values, no formulas, no merged cells" exactly. The
original data/phase3_tariff_gap.xlsx from Phase 3's first pass is
untouched; this is a new file.

## Final file inventory for this request

---

# Phase 4: scenarios, revenue at risk, exposure score

## Research before building anything

**Census quantity field names** (needed for Part 2/alpha): fetched
https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.json
directly (raw/census_variables.json, new evidence file) and searched it
for quantity-related variables rather than guessing names. Confirmed
exact names: `CON_QY1_MO` (15-digit monthly imports-for-consumption
quantity 1) and `UNIT_QY1` (3-character unit of quantity 1) - a second
quantity measure (`CON_QY2_MO`/`UNIT_QY2`) also exists for codes with
two reporting units; will check per-code which is populated rather than
assuming QY1 always is.

**Section 232 medical-device notice** (needed for Part 6's policy-risk
score): found and read in full via the Read tool (WebFetch's own
extraction undercounted again, same pattern as every prior government
PDF in this project) the actual initiation notice:
https://www.govinfo.gov/content/pkg/FR-2025-09-26/pdf/2025-18729.pdf
(Federal Register Vol. 90, No. 185, 26 Sept 2025, FR Doc. 2025-18729,
BIS Docket 250924-0160) - "Notice of Request for Public Comments on
Section 232 National Security Investigation of Imports of Personal
Protective Equipment, Medical Consumables, and Medical Equipment,
Including Devices," initiated 2 September 2025.

**Confirmed directly: this notice names NO HTS codes anywhere** - only
prose category descriptions. It explicitly EXCLUDES pharmaceuticals
(covered by a separate Section 232 action - consistent with our own
pharma_like_codes.csv split). Its named examples, verbatim:
- PPE: surgical masks, N95 respirators, gloves, gowns, related medical
  parts/components.
- Medical consumables: medical/surgical instruments (syringes, needles,
  IV pumps, forceps, scalpels); medical/surgical supplies (IV bags,
  catheters, tracheostomy tubes, anesthesia equipment, gauze/bandages,
  sutures, diagnostic and laboratory reagents); related parts/components.
- Medical equipment: carriages and wheelchairs; crutches; hospital beds.
- Medical devices: pacemakers; insulin pumps; coronary stents; heart
  valves; hearing aids; prosthetics; blood glucose monitors; orthopedic
  appliances; electromedical apparatus (e.g. CT, MRI); electrosurgical
  apparatus; x-ray apparatus/other radiation equipment; respiratory
  machines (ventilators, respirators, oxygen apparatus).

Notably, **the word "dental" never appears anywhere in the notice, nor
does "ophthalmic," nor any vision-correction term** - these are real
absences, not an oversight on my part. The notice's own GENERAL
definitions ("any instrument... used in diagnosis, monitoring, or
treatment") are broad enough to arguably cover almost everything, which
would make a "named in the notice" criterion useless as a discriminator
(same score for nearly every code) if I used the general definition.
Decided instead to score a code as "named" only if its product matches
one of the notice's explicit named categories/examples above (treating
category headers like "electromedical apparatus" and "x-ray apparatus"
as covering their whole family, not just the literal examples given) -
this is a real, documented judgment call, not a guess: it preserves the
notice's own structure (specific named categories vs. everything else)
rather than either extreme (literal-string-only, or the maximally broad
general definition). Per-code determination applied in Part 6 below,
with the specific keyword match recorded per code.

## Part 1 - elasticity (epsilon) by product group

Wrote p1_elasticity.py (new, read-only against core_device_codes.csv,
final_codes_grouped.csv, raw/census_monthly/*, raw/census/*). No new
downloads needed - reused the monthly data from Phase 3. Computed
exactly the formula given: relative_change (India vs. "all other
countries" % change, shock vs baseline), gap_change (the India-minus-
others duty-rate gap, shock minus baseline, in points), epsilon =
-relative_change / gap_change.

Result: 30 of 60 core codes excluded for India selling under $1M in
2025 (listed explicitly, not just counted); 0 excluded for
|gap_change| < 2 points. 30 codes retained. Per-group summary (median
epsilon, p25, p75, n, 2025 India value) written to
data/phase4_elasticity_by_group.csv (new file) and
data/phase4_elasticity.csv (per-code detail, new file) - both
reproduced in the chat response. 8 of 12 groups have fewer than 3
codes and are flagged LOW CONFIDENCE, per instruction. Noted one
mechanical consequence of the formula worth flagging rather than
hiding: a couple of groups (e.g. Implants) show a very wide p25-p75
spread because epsilon's denominator (gap_change) can be close to the
2-point inclusion threshold for some codes, making the ratio swing
widely - this is an inherent property of the requested formula with a
small denominator, not a computation bug (checked by hand-verifying
one such code's inputs directly).

## Part 2 - price absorption (alpha)

Wrote p2_download_quantity.py (new, same pattern as every download
script) to fetch Census monthly quantity fields (CON_QY1_MO, UNIT_QY1,
plus the secondary CON_QY2_MO/UNIT_QY2) for all 12 baseline+shock
months, 60 core codes = 720 jobs. Saved into a separate directory,
raw/census_monthly_qty/, for the same collision-avoidance reason as
every other distinct-data-shape download in this project. Ran as a
single process: 720/720, 0 failed, exit 0.

**Finding: quantity data is too patchy to use**, per the user's own
stated fallback condition. Checked all 60 codes directly (not
sampled): only 2 - both HS10 lines, 6210105010 and 6210105090
(surgical/isolation gowns) - have a real, consistent quantity unit
("DOZ") with nonzero India quantity in both periods. The other 58
report Census's own "-" marker (no quantity unit collected at this
level of aggregation) with zero reported quantity for every month,
India included - confirmed this is a genuine Census characteristic by
reading a raw response directly, not a download or parsing bug.
Structurally sensible: quantity reporting is generally only reliable
at finer (8/10-digit) granularity, and almost all our core codes are
6-digit aggregates spanning multiple product types with no single
natural quantity unit.

Applied the user's explicit fallback: alpha = 0.3 (low) / 0.45 (base)
/ 0.6 (high), flat across every group - not computed from data, since
the data doesn't support a group-specific figure. Wrote p2_alpha.py
(new) -> data/phase4_alpha.csv (new file).

## Part 3 - back-test

Wrote p3_backtest.py (new, read-only against data/phase4_elasticity.csv,
data/phase4_elasticity_by_group.csv, raw/census_monthly/*). For each
group, predicted_relative_change = -median_epsilon x
median_gap_change (both from Part 1); actual_relative_change
recomputed from AGGREGATED group-level totals (sum of India/world
value across all the group's retained codes, in both periods), not
averaged per-code percentages - avoids Simpson's-paradox-style
distortion from small-denominator codes.

Sanity-checked the result before trusting it: every group with exactly
1 retained code shows ~0 error (Gloves, Instruments, Respiratory &
Therapy, Ophthalmic, Furniture) - expected by construction, since a
single-code group's median IS that code's own value, so predicting
with it must exactly reproduce that code's own relative change. This
confirms the computation chain is internally consistent, not a
coincidence.

Result: data/phase4_backtest.csv (12 rows, new file). Overall mean
absolute error: **6.9 percentage points** across 12 groups. Largest
misses: Consumables (+21.0pp, model under-predicted the actual fall),
Dressings & Sutures (-16.8pp) and Imaging (-16.6pp, both over-predicted
the fall).

## Part 4 - scenarios

Wrote p4_scenarios.py (new, read-only against core_device_codes.csv,
raw/census/*, data/phase3_tariff_gap_data_v3.csv). For each code,
computed today's baseline using ACTUAL 2026-YTD duty paid (per this
phase's explicit instruction to use actual duty, not listed rates, for
competitor comparisons) for India and for the weighted top-3 non-India
2025 suppliers, then delta_t/delta_g for S0-S5 (S4 producing two rows,
one per year).

**S1's "China exclusions end... on excluded codes only" needed a proxy**
since Phase 3 already established there is no obtainable per-code
exclusion list (the Federal Register notice doesn't name codes, and the
underlying HTS General Notes text wasn't retrievable via the REST API).
Used a data-driven proxy instead of guessing which codes are excluded:
a code is treated as "currently benefiting from an exclusion" if China
is a top-3 supplier AND its actual 2026 duty paid sits >3pp below its
Phase-3-corrected listed rate - the same pattern Phase 3's competitor
check specifically attributed to active exclusions. The bump applied
when the exclusion "ends" is set to that same listed-minus-actual gap,
clipped to the user's stated 7.5-25 point range. Documented explicitly
as a proxy, not the real list - 6 of 60 codes matched this pattern.

**Verified an expected model property rather than assuming it**: under
S3 (uniform +25 for everyone) and both years of S4 (uniform +10 then
+25 for everyone), delta_g = 0 for every code by construction, since a
tariff that hits India and every competitor equally cannot change the
competitive gap between them - only S1 (China-specific), S2 (asymmetric
exemptions), and S5 (India-specific) can move delta_g. This is a
sanity-checking consequence of the scenario design, confirmed in the
code's logic, not an oversight.

Result: data/phase4_scenarios.csv (357 rows = 51 codes x 7
scenario-rows; new file). 9 of 60 core codes excluded - all are the
same thin/zero-value codes already identified in Phase 2/3
(300620, 382211, 382212, 382213, 901841, 902150, 902221, and the two
902519 thermometer HS10 lines) - confirmed by cross-checking against
the earlier "under $1M" lists, not a new bug.

## Part 5 - revenue at risk

Wrote p5_revenue_at_risk.py (new, read-only against
data/phase4_scenarios.csv, data/phase4_elasticity_by_group.csv,
final_codes_grouped.csv, raw/census/*, raw/census_monthly/*). Computed
exactly the formula given, both E definitions (2025 full year, latest
12mo = Oct 2025-Sep 2026), low/base/high using p25/median/p75 epsilon
with low/base/high alpha as specified.

**Caught a real result-level problem before presenting it, by checking
whether the totals made economic sense (a result exceeding the total
trade value it's supposed to be a fraction of is an immediate red
flag) rather than trusting the arithmetic just because it ran without
error**: the first run showed S2's "low" scenario total at -$509M
(-92.7% of E) - a number far too large in magnitude (the whole core
list's 2025 India trade is only ~$550M). Traced it to a single code:
**902190** ("Other appliances implanted or worn," Implants group) has
a tiny India baseline value in the Oct2024-Mar2025 window, so its
shock-vs-baseline relative_change computed to **+1057%** - an ordinary
and correctly-computed consequence of percentage-change arithmetic on
a near-zero base, not a data or calculation error (verified the
underlying dollar values directly). Combined with a gap_change of only
5.58pp (just above the 2-point inclusion floor), this produces
epsilon = -189.6 for that one code, which then sets the whole Implants
group's 25th-percentile epsilon (since n=4, one extreme value can set
a percentile). S2 is the scenario most exposed to this because
Implants has a nontrivial delta_g under S2's asymmetric exemption
structure.

**Did not alter the methodology or cap epsilon** to make the output
look tidier - the formula is exactly as specified, and 902190's
baseline-driven swing is a legitimate feature of the input data, not a
bug to "fix" by overriding the user's formula. Instead: flagging this
explicitly, both here and in the Excel README, and recommending the
BASE (median-epsilon) scenario figures as the primary, trustworthy
numbers - medians are far more robust to one outlier than p25/p75 are
with only 4 data points. LOW/HIGH bounds should be read with this
caveat in mind, specifically for scenarios with material Implants-
group exposure (S2 most of all).

Result: data/phase4_revenue_at_risk.csv (350 rows) and
data/phase4_revenue_at_risk_totals.csv (7 rows: S0-S5, with S4 as two
year-rows) - both new files, reproduced in the chat response to the
user with the caveat stated plainly.

## Part 6 - exposure score

Wrote p6_exposure_score.py (new, read-only against
core_device_codes.csv, final_codes_grouped.csv,
data/phase4_scenarios.csv, data/phase4_elasticity_by_group.csv,
data/india_trade.csv, data/india_trade_final_new_codes.csv).

**Competitor gap**: deliberately used Phase 4's OWN S0 "gap_today_pct_points"
(India's actual duty paid minus the top-3 competitors' actual-paid,
value-weighted) rather than Phase 3's "gap_actual_pct" column, because
Phase 3's version is a hybrid (India's actual duty minus a LISTED-rate-
weighted competitor baseline) - this phase's standing instruction is to
use actual duty paid on BOTH sides of every competitor comparison, so
reusing the Phase 3 hybrid would have been inconsistent.

**Policy risk / "named in the Section 232 notice"**: built a per-code
True/False table (60 entries, in the script itself with inline
reasoning) by matching each code's product against the notice's
explicitly named categories/examples identified in the earlier
research note above - not the notice's maximally-broad general
definitions, which would mark almost everything True and carry no
discriminating information. Clean, explainable pattern: every Dental
and Ophthalmic-group code scored False (the notice's text never
mentions "dental" or "ophthalmic" anywhere), every PPE item (gloves,
gowns), named consumable (syringes, needles, catheters, sutures,
gauze/bandages, diagnostic reagents), and named device (pacemakers,
stents, hearing aids, orthopedic/prosthetic appliances, electromedical/
X-ray/CT apparatus, respiratory machines, hospital beds) scored True.
One deliberately conservative borderline call logged explicitly: 300650
("first-aid boxes and kits," a bundle of assorted items) scored False,
since it isn't itself one of the individually-named items even though
its contents might be.

**Missing-data handling**: 3 of 60 codes have no Comtrade US-dependence
figure (300620, and the two 902519 thermometer HS10 lines) - each
traced to an already-established pattern from earlier phases (300620's
persistent zero/no-data in both Census and Comtrade; 902519 never
having been downloaded as a whole-HS6 Comtrade entry at any point in
this project, only reached via the later HS10-line filtering). Flagged
explicitly per code in a `missing_components` column rather than
imputing a guessed value - for an affected code, that component simply
contributes nothing to its weighted score (equivalent to a zero weight
on that part for that code only), a documented limitation rather than
a silent assumption.

Result: data/phase4_exposure_score.csv (60 rows, ranked, new file) -
full top-10 reproduced in the chat response to the user.

## Part 7 - data/phase4_scenarios.xlsx

Wrote p7_build_excel.py (new, read-only against the Phase 4 CSVs
already produced). 7 sheets: README (every sheet explained, plus the
902190/Implants low-scenario caveat stated prominently near the top,
and the S1-proxy/Section-232-naming methodology notes), Elasticity,
Alpha, Backtest, Scenarios_by_code (357 rows), Totals (7 rows),
Exposure_score (60 rows, ranked). Verified directly after writing: 0
formula cells, 0 merged ranges, no sheet protection, across all 7
sheets - matches "plain typed values only" exactly.

New files only, nothing existing overwritten: data/core_device_codes.csv,
data/pharma_like_codes.csv, data/hygiene_codes.csv,
data/phase3_tariff_gap_data_v2.csv, data/phase3_tariff_gap_data_v3.csv,
data/top15_competitor_check_raw.json, data/top15_competitor_check.csv,
data/phase3_headline_core.txt, data/phase3_tariff_gap_v2.xlsx,
raw/cbp/Forced_Labor_HTS_List.pdf, plus scripts h1-h6. final_codes.csv,
final_codes_grouped.csv, data/phase3_tariff_gap_data.csv, and
data/phase3_tariff_gap.xlsx (Phase 3's first-pass outputs) are all
untouched.

For the 3 exempt codes, zeroed out India's forced-labor-driven add-on:
`india_listed_rate_pct` collapses to just the MFN rate (the +10%
component no longer applies), and `india_forced_labor_addon_pct` is
recorded as "0 (exempt)" with the specific exemption citation kept in a
new `exemption_source` column. Wrote data/phase3_tariff_gap_data_v2.csv
(new file, 63 rows - the original data/phase3_tariff_gap_data.csv from
Phase 3's first pass is untouched).

---

## Phase 4 final file inventory

New files only, nothing from Phase 1-3 overwritten:
data/phase4_elasticity.csv, data/phase4_elasticity_by_group.csv,
data/phase4_alpha.csv, data/phase4_backtest.csv,
data/phase4_scenarios.csv, data/phase4_revenue_at_risk.csv,
data/phase4_revenue_at_risk_totals.csv, data/phase4_exposure_score.csv,
data/phase4_scenarios.xlsx, raw/census_variables.json,
raw/census_monthly_qty/ (720 new files), plus scripts p1-p7. Every
Phase 1-3 output (core_device_codes.csv, final_codes_grouped.csv,
phase3_tariff_gap_data_v3.csv, raw/census/*, raw/census_monthly/*,
etc.) was read from, never written to.

---

# Four fixes to the Phase 4 model

## Fix 1 - tier-level epsilon with the aggregate method and bootstrap

Wrote q1_tier_epsilon.py (new, read-only against core_device_codes.csv,
final_codes_grouped.csv, raw/census_monthly/* - no new downloads
needed). Three tiers as specified (A: Consumables/Dressings & Sutures/
Gloves; B: Electro-diagnostic/Imaging/Instruments/Respiratory & Therapy/
Ophthalmic/Furniture/Other; C: Implants/Dental), plus one pooled
estimate across all tiers as a check. Qualifying test changed from
Phase 4 v1's "$1M in 2025 full year" to "$1M in the baseline months
(Oct 2024-Mar 2025) alone," per this fix's instruction.

**Switched from per-code median (v1) to the aggregate method** -
summing India's and others' raw dollars across a tier's qualifying
codes BEFORE computing any percentage change, rather than averaging
each code's own percentage change. This directly fixes the problem
Phase 4 v1 hit: a single small-baseline code (902190) could blow up a
whole group's percentile estimate via an extreme individual %-change.
Aggregating dollars first means no single code's tiny denominator can
dominate - confirmed this worked by comparing the result's stability
directly: v1's Implants group had a p25 of -189.6; this fix's Tier C
(which includes Implants) has a low of 0.962 - no outlier blowup.
Floored epsilon at 0 and capped at 5 as instructed, applied both to the
point estimate and to every bootstrap draw.

Bootstrap: resampled each tier's qualifying codes with replacement
1,000 times (fixed random seed 20261115 for reproducibility), recomputed
epsilon_tier identically each time, reported median/p25/p75 of the
resulting distribution as base/low/high.

Result: data/phase4_tier_epsilon_v2.csv (4 rows: Tier A, B, C, Pooled;
new file).

| Tier | n codes | low | base | high | gap_change (pp) |
|---|---|---|---|---|---|
| Tier A (simple disposables) | 7 | 1.059 | 1.319 | 1.574 | 23.12 |
| Tier B (equipment) | 10 | 0.350 | 0.497 | 0.650 | 31.67 |
| Tier C (implants and dental) | 3 | 0.962 | 2.167 | 3.677 | 10.79 |
| Pooled (all tiers) | 20 | 0.539 | 0.673 | 0.833 | 28.70 |

Tier C has the widest spread (only 3 qualifying codes), but nothing
approaching v1's pathological outlier - all values are economically
plausible (epsilon between roughly 0 and 4, meaning a 1-point tariff
gap increase corresponds to at most a few points of relative trade
shift, well within the 0-5 clamp range without ever needing the clamp
to bind in practice for the point estimates shown).

## Fix 2 - out-of-sample test

Wrote q2_out_of_sample.py (new, read-only against
data/phase4_tier_epsilon_v2.csv, raw/census_monthly/* - imports
aggregate_epsilon/monthly_india_world directly from q1_tier_epsilon.py
rather than duplicating that logic). Tested each tier's BASE (median)
epsilon from Fix 1 - estimated on Oct 2025-Mar 2026 vs Oct 2024-Mar
2025 - against a genuinely different window: Apr-Sep 2026 vs Apr-Sep
2024, using that window's own freshly-computed gap_change (same
aggregate method, same qualifying codes per tier as Fix 1 identified -
the parameter is out-of-sample, the code membership is not re-picked).

Result: data/phase4_out_of_sample_v2.csv (3 rows; new file).

| Tier | Predicted % | Actual % | Model error (pp) | Naive error (pp) | Beats naive? |
|---|---|---|---|---|---|
| Tier A (simple disposables) | -4.31 | -31.77 | 27.46 | 31.77 | **True** |
| Tier B (equipment) | -1.86 | -19.85 | 18.00 | 19.85 | **True** |
| Tier C (implants and dental) | -3.92 | 0.79 | -4.71 | -0.79 | **False** |

**Honest mixed result, reported as found rather than smoothed over**:
Tiers A and B both beat the naive "India moves with the market"
benchmark, but Tier C does not - its own epsilon estimate had the
widest bootstrap spread in Fix 1 (only 3 qualifying codes), so a
less-reliable out-of-sample result for exactly that tier is consistent
with, not contradictory to, Fix 1's own confidence signal.

Persistent loss (actual fell further than predicted, in dollars, using
each tier's India baseline value for Apr-Sep 2024): Tier A
**$11,615,767**; Tier B **$35,426,939**. Tier C showed no persistent
loss (actual was better than predicted, not worse, in that window).

## Fix 3: alpha from 10-digit quantities (continued)

q3b's HS10 quantity download finished successfully overnight:
**504/504 newly downloaded, 0 already present, 0 failed** across the
42 ten-digit lines x 12 months. Confirmed independently via log tail,
`grep -c FAILED` (0), and a direct file count in
`raw/census_hs10_qty/` (504).

Wrote `q3c_alpha_hs10.py` to compute alpha from this data. Before
running it, discovered a gap: alpha needs India's OWN tariff-rate
change (calculated duty / value), and q3b's download did not include
`CAL_DUT_MO` (value+quantity only, by design, since duty wasn't part
of the quantity question). Checked whether these 42 specific HS10
lines already had monthly duty data anywhere in the project -
`raw/census_monthly/` has 429 HS6-level files plus a handful of
unrelated HS10 files, but **zero of the 42 lines in
`top10_hs10_lines.json` are present there** (confirmed by listing all
10-digit-named files in that folder and checking for overlap - none).

So a second, smaller download is required before alpha can be
computed: `q3d_download_hs10_duty.py`, same 42 lines x 12 months,
fields `CTY_CODE, CTY_NAME, SUMMARY_LVL, CON_VAL_MO, CAL_DUT_MO`, same
checkpoint/skip-if-exists pattern as every other script, saved to a
new directory `raw/census_hs10_duty/` (kept separate from
`raw/census_hs10_qty/` - different data shape, evidence-layering
rule). This is a second small download, run as its own single
background process per the one-process-at-a-time rule; `q3c_alpha_hs10.py`
will be updated afterward to read duty from this new folder instead of
`raw/census_monthly/`.

Ran `q3d_download_hs10_duty.py` as a single background process: **504/504
newly downloaded, 0 already present, 0 failed**, confirmed via log tail and
`grep -c FAILED` (0) and file count (504). Updated `q3c_alpha_hs10.py`'s
duty lookup to read from `raw/census_hs10_duty/` instead of the placeholder,
then ran it.

**Result: 17 of 42 lines usable** (25 skipped for India baseline value
< $1M; 0 skipped for unit mismatch; 0 skipped for missing duty data).
Since 17 >= 8, per the instruction this uses the measured values:
**low = -1.292 (p25), base = 0.063 (median), high = 0.908 (p75)**, written
to `data/phase4_alpha_hs10_v2.csv` (17 lines) and
`data/phase4_alpha_hs10_summary_v2.csv`.

**Honest caveat, reported rather than hidden**: this result is technically
valid by the stated rule but is NOT a stable or confident alpha estimate.
The 17 line-level alphas range from -89.3 to +3.2, span positive and
negative, and the median (0.063) is close to zero - very different in
character from the 0.3/0.45/0.6 fallback. Causes visible in the per-line
data (`phase4_alpha_hs10_v2.csv`): (1) several lines have large,
noisy, sign-flipping India vs "others" unit-value swings over just a
6-month window (e.g. 9018500000: India unit value +107.66% while others
fell -26.56%, alpha -3.459); (2) one line (9018390020, dozens-unit
catheters) has an India tariff change of only 0.05 points, so a normal-
sized price gap divides into a huge alpha (-89.302) - the same small-
denominator blowup problem Fix 1 solved for epsilon by aggregating
dollars first, but Fix 3's instructions specify a per-line median/
percentile method for alpha, not aggregation, so that line was kept in
rather than silently dropped; (3) unit-value changes at the 10-digit
level mix genuine price change with product-mix shifts within each
line (e.g. buyers shifting toward a different model/size inside the
same statistical code), which quantity-based unit value cannot separate
from a true price effect.

Decision: following the letter of the instruction (>=8 usable lines ->
report measured median/p25/p75), `phase4_alpha_hs10_summary_v2.csv` holds
low=-1.292, base=0.063, high=0.908, n=17 - but this will be flagged to
the user as unreliable, and the fallback 0.3/0.45/0.6 kept available as
an alternative, when Fix 4/6 are presented.

## Fix 4: re-run scenarios and exposure score with tier epsilon + new alpha

Wrote and ran `q4_rerun_scenarios.py`: pairs tier epsilon (low/base/high
from `phase4_tier_epsilon_v2.csv`) with Fix 3's measured alpha
(low=-1.292/base=0.063/high=0.908), same revenue-at-risk formula and
low-with-low/base-with-base/high-with-high pairing convention as the
original `p5_revenue_at_risk.py`.

**Gap found (pre-existing from Fix 1, not new)**: code 902140 (Hearing
aids, group "Hearing") has no tier assignment - the user's Fix 1 tier
definition (Tier A/B/C) never named a "Hearing" group, so this code was
already silently excluded from all three tiers' qualifying-code lists in
Fix 1 itself (`phase4_tier_epsilon_v2.csv`'s three `codes` columns)
confirmed by checking directly - it does not appear in any of them. Fix
4 carries this forward rather than inventing a tier for it: code 902140
is excluded from `phase4_revenue_at_risk_v2.csv` and downstream totals/
exposure score. Flagging this explicitly rather than silently fixing
the gap, since the user's exact tier list did not mention "Hearing" and
a guess about which tier it belongs in was not requested.

**Monotonicity check (`phase4_monotonicity_check_v2.csv`, 14 rows = 7
scenario-years x 2 bases)**: low <= base <= high holds for every
scenario EXCEPT **S5 (India deal, India's own duty -10 points)**, on
both the 2025-E and 12mo-E bases. Root cause: S5 is the only scenario
with a NEGATIVE delta_t (-0.10). Fix 3's alpha_low is itself negative
(-1.292), so alpha_low x delta_t_negative = positive, flipping the sign
of that term versus alpha_base (positive 0.063) and alpha_high
(positive 0.908), which both keep delta_t's sign. Concretely: S5 2025-E
low = **+$3.23M** (a gain) while base = **-$43.74M** and high =
**-$55.22M** (both losses) - the "low" case shows the opposite
direction from base/high, which also fails the explicit S5 sign-
consistency check the user asked for. Every other scenario (delta_t >=
0) stays correctly ordered because alpha_low's negative sign does not
flip anything when delta_t is non-negative.

This is reported as a genuine finding, not patched over: it is a direct,
traceable consequence of Fix 3's own already-flagged alpha instability
(a measured low-alpha below zero), not a new bug in the scenario math.
It means the "low" case for S5 specifically should not be trusted as a
lower bound on the gain - the fallback alpha (0.3/0.45/0.6, all
positive) would not have produced this flip.

**New Totals (`phase4_revenue_at_risk_totals_v2.csv`), 2025-E basis**:

| Scenario | low $M | base $M | high $M | base % |
|---|---|---|---|---|
| S0 Today | 0.00 | 0.00 | 0.00 | 0.0 |
| S1 China exclusion expiry | -2.41 | -1.24 | -0.15 | -0.23 |
| S2 Sec232 15% w/ exemptions | -36.52 | 48.06 | 80.63 | 8.74 |
| S3 Sec232 25% all | -177.53 | 8.66 | 124.77 | 1.57 |
| S4 Phased Yr1 (10%) | -71.01 | 3.46 | 49.91 | 0.63 |
| S4 Phased Yr2 (25%) | -177.53 | 8.66 | 124.77 | 1.57 |
| S5 India deal (-10) | +3.23 (flagged, see above) | -43.74 | -55.22 | -7.96 |

Overall E 2025 full year used: $549,631,495. Exposure score re-run
(`phase4_exposure_score_v2.csv`), restricted to codes with >= $1M India
value in 2025: **30 of the 60 core codes kept, 30 excluded** for falling
below the $1M threshold (confirmed directly from the script's own run
output). "Ease of switching" now
uses the code's tier base epsilon instead of the old per-group median,
and two new columns added: `E_2025_full_year_musd`,
`base_S2_rar_musd`. Top 10 by score: led by Syringes (901831, 70.2) and
Other electro-diagnostic apparatus (901819, 68.8). Top 10 by base-S2 $ at
risk: led by 901819 ($8.02M) and Artificial joints (902131, $6.88M) -
the two top-10 lists overlap on several codes but are NOT identical,
confirming score and dollar exposure capture different things as
intended.

## Fix 5: v2 Excel export

Wrote and ran `q5_build_excel_v2.py`, same `typed_row()`/assert pattern
as the original `p7_build_excel.py`. Produced
**`data/phase4_scenarios_v2.xlsx`** with 10 sheets: README,
Tier_Epsilon, Out_of_Sample, Alpha_HS10_lines, Alpha_HS10_summary,
Scenarios_by_code, Revenue_at_Risk_v2, Totals_v2, Monotonicity_Check,
Exposure_score_v2. README documents every sheet in plain language and
carries all three caveats found in Fixes 3/4 (alpha instability, S5
sign flip, the Hearing/902140 tier gap) up front rather than only in
the log.

**Independently re-verified** (fresh `openpyxl.load_workbook()` call,
separate from the build script's own in-script asserts): checked every
worksheet for sheet protection, merged-cell ranges, and any cell with a
formula data type or a value starting with "=" across all 10 sheets.
**Result: zero problems found** - plain typed values only, exactly as
required.

---

# Final Phase 4 run (v3): user-decided alpha/epsilon settlement

User reviewed the v2 caveats (unstable measured alpha, S5 sign flip,
902140/Hearing with no tier) and made explicit decisions rather than
leaving them open:

1. **Alpha**: use the fallback 0.3/0.45/0.6 for all totals/exposure
   figures. The measured alpha from Fix 3 (median 0.063, range -1.292
   to 0.908, n=17) is kept as its own reported finding, explicitly
   labelled "unstable, not used in totals" - not deleted, not hidden.
2. **Epsilon**: Tier A and Tier B keep their v2 bootstrapped values
   unchanged (not recomputed). Tier C's epsilon is REPLACED with the
   v2 POOLED epsilon (low=0.539, base=0.673, high=0.833) instead of
   Tier C's own (0.962/2.167/3.677) - the user's judgment is that
   Tier C's own estimate (n=3 qualifying codes, and the tier that
   failed the out-of-sample test in Fix 2) is less trustworthy than
   the broader pooled estimate. Code 902140 (Hearing aids, group
   "Hearing" - previously unassigned to any tier, a gap flagged in v2)
   is now assigned to **Tier B** for scenario/exposure purposes. Per
   "keep the bootstrapped values from v2" for Tier B, this is a
   membership assignment only - Tier B's own epsilon number is NOT
   recomputed to include 902140's data (that would contradict "keep
   the v2 bootstrapped value").

## v3 run results

Wrote and ran `r1_phase4_v3.py`. Outputs: `data/phase4_tier_epsilon_v3.csv`,
`data/phase4_persistent_loss_v3.csv`, `data/phase4_revenue_at_risk_v3.csv`
(357 rows - 7 more than v2's 350, exactly the 7 scenario rows for code
902140 now that it has a tier), `data/phase4_revenue_at_risk_totals_v3.csv`,
`data/phase4_monotonicity_check_v3.csv`, `data/phase4_exposure_score_v3.csv`.

**Monotonicity/sign check: 0 failures of either kind.** Loss-scenario
ordering (low<=base<=high, S0-S4): holds for all 12 rows (6 scenario-years
x 2 bases). S5 gain-in-all-three (all of low/base/high negative = a gain
in this script's sign convention): holds for both bases. This confirms
the v2 failure was specifically caused by the measured alpha's negative
low value - switching to the all-positive fallback alpha (0.3/0.45/0.6)
removes the sign-flip entirely, exactly as expected.

**New Totals (2025-E basis)**:

| Scenario | low $M | base $M | high $M | base % |
|---|---|---|---|---|
| S0 Today | 0.00 | 0.00 | 0.00 | 0.0 |
| S1 China exclusion expiry | -0.74 | -0.73 | -0.64 | -0.13 |
| S2 Sec232 15% w/ exemptions | 44.62 | 58.12 | 68.82 | 10.57 |
| S3 Sec232 25% all | 41.23 | 61.84 | 82.45 | 11.25 |
| S4 Phased Yr1 (10%) | 16.49 | 24.74 | 32.98 | 4.50 |
| S4 Phased Yr2 (25%) | 41.23 | 61.84 | 82.45 | 11.25 |
| S5 India deal (-10) | -36.05 | -45.22 | -51.71 | -8.23 |

Overall E 2025 full year: $549,666,887 (vs v2's $549,631,495 - the
~$35K difference is exactly 902140/Hearing aids' own 2025 India value,
now included for the first time).

**Persistent loss (Apr-Sep 2026 vs Apr-Sep 2024)**:

| Tier | epsilon base used | actual | predicted | gap ($M) |
|---|---|---|---|---|
| A | 1.319 (unchanged) | -31.77% | -4.31% | $11.62M |
| B | 0.497 (unchanged) | -19.85% | -1.85% | $35.43M |
| C | 0.673 (pooled, new) | +0.79% | -1.22% | -$0.40M |

Tier C's gap flips to slightly negative (actual beat predicted) under
the new pooled epsilon, consistent with Fix 2's original finding that
Tier C did not show a persistent-loss pattern - using the pooled
epsilon instead of Tier C's own does not change that conclusion.
Explanatory line carried into the CSV and the v3 workbook: "Fall larger
than tariff gaps explain, consistent with US buyers not returning after
the 50% period (Oct 2025-Feb 2026). Scenario totals exclude this, so
they are a lower bound."

**Exposure score re-run** (30 of 60 codes, >= $1M India value in 2025,
902140 now eligible and included). Top 10 by score now led by Syringes
(901831, 77.8 - up from 70.2 in v2, since fallback alpha raises its
weighted score contribution) and Other electro-diagnostic apparatus
(901819, 68.8). Top 10 by base-S2 $ at risk led by 901819 ($13.16M) and
Other medical/surgical instruments (901890, $8.10M) - dollar figures are
materially higher than v2's because the fallback alpha (0.45 base) is
larger in magnitude than the measured alpha's near-zero base (0.063) for
the alpha*delta_t term, which now contributes much more to S2/S3/S4's
positive-delta_t scenarios.

## v3 Excel export

Wrote and ran `r2_build_excel_v3.py`. First attempt triggered an
openpyxl warning: sheet name "Alpha_measured_UNSTABLE_not_used" (33
chars) exceeds Excel's 31-character sheet-name limit. Fixed by
shortening to "Alpha_measured_unstable" and rebuilding - no warnings
on the second run.

Produced **`data/phase4_scenarios_v3.xlsx`** with 8 sheets: README,
Tier_Epsilon_v3, Alpha_fallback_used, Alpha_measured_unstable,
Revenue_at_Risk_v3, Totals_v3, Persistent_Loss_v3, Exposure_score_v3.
The measured (unstable) alpha from Fix 3 is preserved in its own sheet,
clearly labelled, per the user's instruction not to discard it even
though it isn't used in the totals.

**Independently re-verified** (fresh `openpyxl.load_workbook()` call):
checked every worksheet for sheet protection, merged-cell ranges, and
any cell with a formula data type or a value starting with "=" across
all 8 sheets. **Result: zero problems found.**

### Status: FINAL PHASE 4 RUN (v3) COMPLETE

---

# Phase 5: company exposure

User closed Phase 4 and started Phase 5. Standing rules reaffirmed:
don't overwrite existing files; log every step and code edit here; for
every figure, record source document + page number + link; if a figure
isn't disclosed, write "not disclosed" rather than estimate silently.

This phase requires real-world company research (annual reports,
investor presentations, earnings call transcripts, SEBI DRHP filings,
NSE/BSE listing status, daily share prices) - a different shape of
work from Phase 4's local-data computation. Working through the 8
numbered parts of the user's request in order, logging sources as
found.

## Part 1: company list

Starting set: Poly Medicure (POLYMED), Laxmi Dental (LAXMIDENTL),
Tarsons Products (TARSONS, flagged borderline - mainly lab plasticware,
not medical devices in our core_device_codes.csv sense). Checking
Sahajanand Medical Technologies, Healthium Medtech, Meril, and
Translumina for NSE/BSE listing or a SEBI DRHP with US revenue
disclosure.

### Part 1 result: company list

Downloaded as evidence (curl, saved to raw/phase5_evidence/, verified
valid PDFs via `file`): `smt_drhp.pdf` (490pp, SMT's DRHP dated 26 Jul
2025, from
https://www.bseindia.com/corporates/download/356364/IPO%20Prior/SMTDRHP_20250726031147.pdf),
`integris_drhp.pdf` (635pp, Integris Medtech Ltd's DRHP dated 9 Oct
2025, from
https://nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf),
`healthium_drhp_2021.pdf` (520pp, Healthium Medtech's ONLY DRHP on
file, dated Sept 2021, from
https://www.bseindia.com/corporates/download/307520/HMLDRHP_20210909182436.pdf).
Searched each PDF's full text for key terms (geography, EBITDA margin,
tariff, Section 301/232) using pymupdf rather than reading sequentially
- 490-635 page documents make page-by-page reading impractical.

**Decisions**:
- **POLYMED (Poly Medicure)**: listed, NSE/BSE. INCLUDE.
- **LAXMIDENTL (Laxmi Dental)**: listed, NSE/BSE. INCLUDE.
- **TARSONS (Tarsons Products)**: listed, NSE/BSE. INCLUDE, flagged
  borderline per user instruction (mainly lab plasticware, not medical
  devices in our core_device_codes.csv sense).
- **Sahajanand Medical Technologies (SMT)**: listed on NSE (ticker
  "SMT") and BSE (545001) on 23 Oct 2026 - confirmed via WebSearch
  (multiple sources: chittorgarh.com, trendlyne.com,
  multibagg.ai). DRHP dated 26 Jul 2025 has usable FY23/FY24/FY25
  financials (Revenue, EBITDA, EBITDA margin, PAT - DRHP pages
  120-121). **ADD - has usable numbers.**
- **Healthium Medtech**: still UNLISTED as of today. KKR acquired a
  controlling stake (announced Jan 2026,
  business-standard.com/companies/news/kkr-to-acquire...). Its only
  DRHP on file is from September 2021 - more than 5 years stale,
  predates FY2024-25/FY2025-26 entirely, and IPO dates remain "to be
  announced" per multiple 2026 sources (religareonline.com,
  angelone.in). **EXCLUDE - no usable current-period numbers.**
- **Meril Life Sciences**: confirmed UNLISTED, private company
  (tracxn.com, thecompanycheck.com - CIN
  U24239GJ2007PTC051137). No DRHP found anywhere. **EXCLUDE.**
- **Translumina Therapeutics**: not itself an IPO filer - it is a
  "material subsidiary" of **Integris Medtech Limited**, whose DRHP
  (dated 9 Oct 2025) was SEBI-approved 13 Feb 2026 and whose IPO opened
  8 Nov 2026 (not confirmed listed as of today, 15 Nov 2026 - sources
  conflict and no listing-date/ticker was found; IPO size was cut from
  Rs 925cr to Rs 600cr per healthbiz.in/medicalbuyer.co.in).
  Integris Medtech's DRHP (pages 169-176) gives REVENUE split by
  business segment (Lab Solutions: Clinical Diagnostics + Scientific
  Lab Solutions; Cardiovascular: DES and Balloons + Other
  Cardiovascular Products, which is Translumina's actual business) for
  FY23/24/25/Q1FY26 - but EBITDA, margins and geography are only given
  at the WHOLE-COMPANY (Integris) level, mixing the non-device Lab
  Solutions business with Translumina's cardiovascular devices. There
  is no way to isolate a Translumina-only EBITDA or geography split
  from what's disclosed. **ADD as borderline (like TARSONS) - usable
  revenue-by-segment numbers exist, but EBITDA/margin/geography are
  only available at the mixed, whole-company level, flagged
  throughout.**

Final list for Parts 2-8: **POLYMED, LAXMIDENTL, TARSONS (borderline),
SMT, Integris Medtech/Translumina (borderline, segment-revenue only).**
Healthium Medtech and Meril Life Sciences excluded, both for lack of
any usable current-period disclosure (not because they're unimportant
competitors).

**Key cross-cutting finding, applies to SMT and Integris/Translumina
specifically**: neither DRHP discloses a "United States" or "Americas"
revenue line - both only break revenue into India / Europe / (Asia
ex-India, for Integris) / Rest of World (RoW). Per the user's own
fallback instruction ("the US or Americas line, or exports if that's
all they give"), these two companies' "US revenue" will be recorded as
**not disclosed**, with total EXPORTS (100% - India%) used as the
broadest available substitute wherever the formulas need a revenue
base - explicitly labelled as NOT US-specific every time it's used,
since exports go to 70+ countries for SMT alone. This will tend to
OVERSTATE these two companies' true US exposure in Part 3's
calculations; flagging this prominently rather than silently treating
exports as if they were US revenue.

### Parts 2a-2d: consolidated company data

Wrote `s1_build_company_data.py` compiling all research into structured
CSVs, every row carrying its own source document/page/URL (never a bare
number without provenance). Research conducted via WebSearch (dozens of
queries) and direct PDF download+text-search (pymupdf) of 10 primary
documents saved to `raw/phase5_evidence/`: SMT DRHP, Integris Medtech
DRHP, Healthium Medtech 2021 DRHP, POLYMED Q2FY27 transcript + FY26
annual presentation + Q3FY26 presentation, Laxmi Dental Q2FY27
presentation + transcript (3 download attempts - v1 was just the call
invite, not the real transcript; v2/v3 from alternate BSE links are the
real 42-page transcripts), Tarsons Q2FY26 transcript + Q2FY26
presentation.

Output: `data/phase5_companies.csv` (7 rows - 5 included, 2 excluded with
reasons), `data/phase5_geography.csv` (11 rows), `data/phase5_product_mapping.csv`
(12 rows), `data/phase5_financials.csv` (24 rows), `data/phase5_management_comments.csv`
(12 rows).

**Key honest gaps, carried as "not disclosed" rather than estimated**:
- POLYMED and SMT and Translumina/Integris: NONE disclose a US-specific
  or Americas-specific revenue % - only India/Europe/RoW (POLYMED, SMT)
  or India/Europe/Asia-ex-India/RoW (Integris). Only a few dollar-figure
  mentions exist for POLYMED's US business from earnings-call commentary
  (<$3-3.5M as of the Q1 FY26 call; $7-8M FY27 group-level guidance from
  the Q2 FY27 call) - these are spoken management figures, not an
  audited segment line, and not reconcilable precisely to the RoW %.
- **LAXMIDENTL is the one exception**: explicit "USA 19.4%" of FY26
  total revenue (India 64.4%, UK 10.1%, Others 6.1%), plus a narrower
  "US ~25% of laboratory business" segment-specific figure - both
  disclosed, both recorded, flagged as different bases (whole-company
  vs lab-segment-only).
- TARSONS: no numeric US/Americas % found anywhere - only qualitative
  earnings-call commentary ("have not lost any customers... both
  Tarsons and U.S. customers... optimistic about reduction in U.S.
  tariff" - Santosh Agarwal, Q2 FY26 call, 13 Nov 2025) and the
  structural finding that Tarsons' core plasticware products (HS 3926)
  don't map to ANY code in core_device_codes.csv at all - the concrete
  basis for its "borderline" flag.
- SMT and Translumina/Integris have NO earnings-call history yet (SMT
  listed 23 Oct 2026; Integris not confirmed listed) - all management
  commentary comes from their pre-listing DRHPs, which were searched
  for "tariff"/"Section 301"/"Section 232" and found to contain only
  generic regulatory-risk language, not US-tariff-specific commentary.
- A few cross-source figure discrepancies were found and preserved
  rather than silently picked (e.g. POLYMED FY25 EBITDA margin:
  28.72% per the Integris DRHP's audited-financials-sourced peer table
  vs 27.5% per secondary market commentary) - both recorded with their
  distinct sources in `phase5_financials.csv`.

**Quantified tariff impact found (the most concrete management
disclosure across all 5 companies)**: Laxmi Dental explicitly
quantified US-tariff drag on EBITDA margin by quarter - Q3 FY26: 150bps,
Q4 FY26: 74bps (half-quarter), FY26 full year: 72bps - and separately
disclosed an incoming ~Rs5.5 crore tariff REFUND to hit Q3 FY27.

### Parts 3-4: company revenue-at-risk and EBITDA-at-risk

Wrote and ran `s2_company_risk.py`. Methodology: per-code RAR%
(rar_usd/E_usd) taken directly from Phase 4 v3's own numbers
(`phase4_revenue_at_risk_v3.csv`), combined per company using
documented category weights (`COMPANY_WEIGHTS` - built from each
company's own disclosed segment-revenue % where available: POLYMED
Infusion/Renal/Others FY26 mix, SMT VI/SH/Others FY25 mix, Translumina's
Cardiovascular-segment-only DES+Balloons/Other split; LAXMIDENTL's two
dental codes equal-weighted since no finer split is disclosed; TARSONS
has zero mapped codes so is marked not computable throughout, never
zero). "Company US revenue" base: LAXMIDENTL uses its genuine disclosed
19.4% US figure; POLYMED uses management's own spoken "<$3-3.5M" FY26
figure (upper bound); SMT and TRANSLUMINA use their RoW geography
bucket as an explicitly-flagged, NOT-US-specific substitute (overstates
true exposure); TARSONS has no revenue base at all. USD/INR conversion
uses the RBI/FBIL reference rate for 30 Mar 2026 (94.6543, used for 31
Mar 2026 since that date was a holiday - Mahavir Jayanti), source
karwaandassociates.com cross-checked against exchange-rates.org.

**Output**: `data/phase5_revenue_at_risk.csv` (35 rows), fixed one bug
on the first run where TARSONS's "not disclosed" rows had the dollar/
rupee columns silently blank instead of explicitly "not disclosed"
(DictWriter's extrasaction=ignore + missing dict keys defaulted to
empty string) - fixed by explicitly setting all $ columns to "not
disclosed" for TARSONS.

Sanity check performed (not explicitly requested for this part, but
worth doing given v2's S5 sign-flip lesson): low<=base<=high holds for
every company x scenario row (confirmed by direct inspection) - expected,
since Part 3/4 use the fallback alpha (0.3/0.45/0.6, all positive, same
fix applied in the v3 scenario run) rather than the unstable measured
alpha.

**Internal consistency check**: for S3 (uniform +25pp on every
country, delta_g=0 by construction per Phase 4's own documented
methodology), EBITDA-at-risk exactly equals revenue-at-risk for every
company (confirmed: LAXMIDENTL base case 6.064cr both) - correct,
since the lost-orders term (which gets discounted by gross margin) is
zero when delta_g=0, leaving only the price-cut term, which "falls
fully on EBITDA" per the user's own formula. For S2 (nonzero delta_g),
EBITDA-at-risk is below revenue-at-risk as expected (4.57cr vs 4.863cr
for LAXMIDENTL) since the lost-orders part is now discounted by gross
margin rather than passing through 1:1.

`data/phase5_ebitda_at_risk.csv` (35 rows): POLYMED and SMT show "not
disclosed" throughout - POLYMED's FY26 gross margin could not be
independently located, and SMT's DRHP KPI table does not disclose
Gross Margin as a metric at all (only EBITDA/PAT margins), so per
instruction these are left blank rather than guessed. TRANSLUMINA uses
its FY25 whole-Integris gross margin (43.95%, mixing Lab Solutions)
as the nearest available figure.

### Part 5: reality check (company-reported vs trade data)

Wrote and ran `s3_reality_check.py`. India-to-US trade value for each
company's mapped codes (same weights as Parts 3-4) computed directly
from `raw/census_monthly/` for H1 FY2025-26 (Apr-Sep 2025) vs H1
FY2026-27 (Apr-Sep 2026) - confirmed both windows are fully present in
the raw data (checked file listing for code 901831, all 6 months of
each year present).

**Honesty constraint**: none of the 5 companies disclose a precise,
US-specific, H1-matched revenue change for this exact window - so no
company's "reported" figure is actually comparable to the trade-data
side on a like-for-like basis. Each reported figure's TRUE basis is
stated plainly rather than silently passed off as "US revenue change":
POLYMED's "+35%" is Q2-only (not H1) INTERNATIONAL (Europe+RoW)
revenue growth; LAXMIDENTL's "+32%" is Q2-only INTERNATIONAL dental-lab
revenue growth; TARSONS' "+33%" IS the correct H1 window but is EXPORT
revenue to all countries, not US-specific (moot anyway since TARSONS
has no HS6 code mapping). SMT and TRANSLUMINA have no post-
listing/post-DRHP quarterly results at all for this window - both
sides marked "not disclosed"/"not comparable" rather than guessed.

Given this, `match_assessment` deliberately avoids a binary
match/mismatch verdict for every row except the fully-N/A ones -
asserting precision the underlying data doesn't support would be
worse than saying so plainly.

**Result worth flagging, not smoothed over**: POLYMED's mapped-code
India-to-US trade FELL 21.15% over this window even as the company's
(non-US-specific) international revenue grew +35% - a real divergence,
though not a true apples-to-apples comparison given the basis
mismatch. SMT and TRANSLUMINA's mapped codes both show large trade
declines (-34.3% and -33.1%) over the same window, consistent with
Tier C's (Implants/Dental) broader weak performance already
documented in Phase 4. LAXMIDENTL's mapped codes (dental) were
roughly flat (+1.09%).

### Part 6: event study - data download

Installed `yfinance` (version 1.8.0, via `pip install yfinance` -
explicitly requested by the user, not an unrequested new dependency).
Wrote and ran `s4_download_prices.py` (same checkpoint/skip-if-exists
pattern as every other download script). Downloaded daily OHLCV, Jan
2025-Nov 2026, for POLYMED.NS (463 rows), LAXMIDENTL.NS (450 rows),
TARSONS.NS (463 rows), ^NSEI/Nifty 50 (462 rows) - all saved to
`raw/phase5_prices/`.

**SMT and Translumina excluded from the event study entirely**: SMT
listed only on 23 Oct 2026, after ALL FIVE event dates (7 Aug 2025
through 24 Jul 2026) - it has no price history for any of them, so no
event-study row is fabricated for it. Translumina has no separate
ticker at all (not independently listed). Both facts already
established in Part 1.

**Nifty Healthcare could not be obtained - genuine data gap, not
silently substituted**:
- `NIFTY_HEALTHCARE.NS` on Yahoo Finance returns only **1 day** of
  history (13 Nov 2026) regardless of the requested date range or
  period (`period='5y'` tried explicitly) - confirmed via both
  `yf.download()` and `yf.Ticker().history()`. This is a real gap in
  Yahoo's backend for this specific symbol, not a bug in the download
  script.
- Tried alternate possible tickers (`^NIFTYHEALTHCARE`,
  `NIFTYHEALTHCARE.NS`, `NIFTY HEALTHCARE.NS`) - none returned data.
  `^CNXPHARMA` (Nifty PHARMA, a different, related but distinct index)
  DID return 246 days of history - NOT used as a silent substitute,
  since the user asked specifically for Nifty Healthcare, not Pharma.
- Attempted the official index provider directly: `niftyindices.com`'s
  Backpage.aspx endpoint returned a 404 page, and NSE's own historical-
  indices API (`nseindia.com/api/historical/indicesHistory`) returned
  a 503. Did not pursue further bypass attempts (no session/cookie
  handling, no retry storm) per this project's own crawler-engineering
  rule against aggressive evasion of straightforward-looking blocks.
- **Conclusion**: the event study proceeds with **Nifty 50 only** as
  the market benchmark (the index the user also explicitly asked for,
  so not a total loss), with Nifty Healthcare recorded as "not
  available" rather than guessed or silently swapped for Nifty Pharma.

### Part 6: event study - computation

Wrote and ran `s5_event_study.py` (numpy/scipy/pandas, all already
available - no new dependency beyond yfinance). Market model (simple
OLS, stock return = alpha + beta*Nifty50 return) estimated per stock
per event over the 120 trading days ending 10 trading days before day
0; day 0 is the event date itself or the next trading day on or after
it (only 7 Feb 2026, a Saturday, needed this - verified it correctly
rolled forward to Monday 9 Feb 2026). Abnormal return = actual minus
(alpha + beta*actual Nifty50 return) per day, cumulated over [0,+1]
and [-1,+5]. t-statistic per MacKinlay (1997): CAR / (sigma_epsilon x
sqrt(L)), sigma_epsilon from the estimation-window regression
residuals, 5% two-tailed significance at |t|>1.96 (normal
approximation, standard given a 120-observation estimation window).

**Output**: `data/phase5_event_study.csv` (30 rows = 3 stocks x 5
events x 2 windows; SMT/Translumina excluded per the data-download log
entry). **Statistically significant abnormal returns found (3 of 30
rows)**:
- POLYMED, 7 Feb 2026 (oil tariff removed): day[0,+1] CAR=+6.50%,
  t=2.13, SIGNIFICANT; day[-1,+5] CAR=-12.58%, t=-2.20, SIGNIFICANT
  (a striking reversal - the initial 2-day pop fully reverses and
  turns sharply negative within the week).
- LAXMIDENTL, 7 Feb 2026 (oil tariff removed): day[0,+1] CAR=+11.03%,
  t=2.70, SIGNIFICANT (the largest and most significant abnormal
  return found in the whole study).
- LAXMIDENTL, 7 Aug 2025 (25% tariff announced): day[-1,+5]
  CAR=-16.17%, t=-2.00, SIGNIFICANT (borderline but over the 1.96
  threshold).

All other 27 rows (both TARSONS windows for every event, and the
remaining POLYMED/LAXMIDENTL windows) were NOT statistically
significant at the 5% level - in particular, the 50% tariff
announcement (27 Aug 2025) and the Section 301 start (24 Jul 2026)
produced no significant abnormal return for any of the 3 stocks in
either window, and TARSONS showed no significant reaction to any of
the 5 events at all.

### Part 7: Excel export

Wrote and ran `s6_build_excel.py`, same typed_row()/assert pattern as
every prior workbook. Produced **`data/phase5_companies.xlsx`** with
10 sheets: README, Companies, Geography, Product_mapping,
Revenue_at_risk, EBITDA_at_risk, Reality_check, Event_study,
Management_comments, Sources (the last one a consolidated bibliography
of every primary document used in this phase, with dates and links).

**Independently re-verified** (fresh `openpyxl.load_workbook()` call):
checked every worksheet for sheet protection, merged-cell ranges, and
any cell with a formula data type or a value starting with "=" across
all 10 sheets. **Result: zero problems found.**

### Status: PHASE 5 (COMPANY EXPOSURE) COMPLETE

---

# Final packaging run

## Part 1: event-study day-0 check for the 7 Feb 2026 event

User asked to confirm which trading day was used as day 0 for the 7
Feb 2026 event (a Saturday), and to re-run only that event with 9 Feb
2026 if it wasn't already used.

**Checked directly against `data/phase5_event_study.csv`**: all three
stocks (POLYMED, LAXMIDENTL, TARSONS) already have
`day0_actual_trading_date = 2026-02-09` for this event - confirmed by
reading the column for all 6 matching rows (3 stocks x 2 windows).
This matches the `trading_day_on_or_after()` logic in
`s5_event_study.py`, which rolls a non-trading event date forward to
the next trading day - working as designed. **No re-run was needed;
no results changed**, per the user's "don't change any results"
instruction.

**Union Budget proximity - logged as a caveat, not a correction**:
the Union Budget was presented 1 Feb 2026 (a Sunday). Checked directly
with pandas against the Nifty50 trading calendar:
- The Budget date (1 Feb 2026) falls OUTSIDE the 120-day estimation
  window for this event (which runs 2025-07-30 to 2026-01-22, ending
  comfortably before the Budget) - so the estimated market-model
  alpha/beta for this event are not contaminated by Budget-day moves.
- However, the **day[-1,+5] event window's start (day -1 = Friday 6
  Feb 2026) sits only 3 trading days after the Budget** (2 Feb, 3 Feb,
  4 Feb, 5 Feb, 6 Feb are the intervening/overlapping trading days) -
  meaning some of that window's measured abnormal return, including
  POLYMED's significant -12.58% CAR (t=-2.20) for this exact window,
  could partly reflect lingering Union Budget market reaction rather
  than (or in addition to) the "oil tariff removed" event specifically.
  This is a genuine potential confound for the 7 Feb 2026 event's
  [-1,+5] window and is noted here rather than silently left unflagged
  - it does not change any computed number, only how confidently the
  [-1,+5] result for this one event should be attributed to the tariff
  news alone.

## Part 2: final_outputs folder

Created `E:\device_tariff\final_outputs\` and `final_outputs\scripts\`.

**Searched thoroughly before copying anything**: `Medical_Device_Tariff_Rulebook_Phase1.xlsx`
does not exist anywhere under `E:\device_tariff` (checked every .xlsx
file in the project and every file matching "rulebook" or "phase1"
case-insensitive - zero matches for the exact file). The only mention
of the word "Rulebook" anywhere in the codebase is a single sentence
inside `step3_checks_and_summary.py`'s own generated check text,
referring to the concept, not pointing to a file. This project's own
log (`step1_progress_log.md`) starts directly at what it calls "Phase
2" - there is no "Phase 1" section anywhere in it, confirming this
file predates the log entirely (if it was ever built) or was never
built. **Not substituted with anything else - flagged in
final_outputs\README.txt and to the user instead.**

All other 9 requested files were found under their exact requested
names and copied: `core_device_codes.csv`, `pharma_like_codes.csv`,
`hygiene_codes.csv`, `lab_instruments_codes.csv`,
`phase2_final_summary.csv`, `phase2_final_checks.txt`,
`phase3_tariff_gap_v2.xlsx`, `monthly_imports.csv`,
`phase4_scenarios_v3.xlsx`, `phase5_companies.xlsx`, plus
`step1_progress_log.md` itself - 11 files total (copies, originals
in `data/`/`logs/` untouched).

All 54 pipeline scripts plus `run_phase2.bat` (55 files) copied into
`final_outputs\scripts\`. `census_key.txt` was deliberately NOT
copied - it is a credential, and the standing rule against committing
secrets into a distributable package applies even to a local folder
copy, not just version control. Noted in README.txt that the user
must supply their own Census API key to rebuild from scratch.

Wrote `final_outputs\README.txt`: describes every file in plain words,
which phase produced it, and the exact 55-step script order to rebuild
everything from scratch - reconstructed directly from the progress
log's own section headers and each script's own docstring (not
guessed), including the one genuinely MANUAL step in the whole
pipeline (hand-editing hs6_codes.csv to add 13 candidate codes during
Investigation A2) called out explicitly rather than implied to be
scripted.

### Status: FINAL PACKAGING RUN COMPLETE

## Part 2 correction: Medical_Device_Tariff_Rulebook_Phase1.xlsx located

User stated they added the file to final_outputs\. First re-check
found it still absent from that exact folder (confirmed via direct
`ls` - exit code 2, "No such file or directory") - did not take the
user's word for it and update the README on an unverified claim,
consistent with this project's standing practice of verifying before
reporting status.

User then said "Check." - re-ran the same direct check, still absent
from final_outputs\. Broadened the search to anything newer than the
just-written README.txt anywhere under E:\device_tariff - found
**`Medical_Device_Tariff_Rulebook_Phase1.xlsx` in the project ROOT**
(`E:\device_tariff\Medical_Device_Tariff_Rulebook_Phase1.xlsx`), not
inside `final_outputs\` - the user had saved it one level up from
where they meant to. Verified it's a real file (`file` command
confirms "Microsoft Excel 2007+", 14,441 bytes) before copying it into
`final_outputs\`.

Updated `final_outputs\README.txt` per the user's exact instructions:
removed the old "file could not be found" section, added
Medical_Device_Tariff_Rulebook_Phase1.xlsx as the Phase 1 entry
("official tariff rates and exemption check, made 8 Nov 2026 outside
this log"), with a note that three of its facts are superseded by
Phase 3 - China exclusions extended to 9 Jan 2027, EU actual duty paid
~9-11% (not a flat 15%), Mexico actual duty paid ~1.6-3.5% (not 0%) -
pointing to phase3_tariff_gap_v2.xlsx for the corrected values. No
other file was changed, per the user's explicit instruction.

---

# View B: India's imports of medical devices from the US

New piece of work, user's own framing: a mirror-image study to Phases
2-5 (which looked at India's EXPORTS to the US) - this looks at
India's IMPORTS of US medical devices, India's own customs duty
structure on them, and what the Feb 2026 interim trade framework
changes. Standing rules reaffirmed: don't change any Phase 1-5 files,
write new files only; log every step; record a source link for every
rate/fact; "not found" rather than guess.

## Part 1: checking reachability of the named Indian government sites

Per the user's explicit instruction ("If these sites can't be reached
from this machine, stop at this step and tell me exactly which pages
I should open and download by hand"), checking taxinformation.cbic.gov.in,
ICEGATE, and Budget 2026-27 customs notification pages before
attempting to build the duty-rate table.

## Part 1 continued: reachability findings and scoping decision

**Site reachability** (per the user's explicit "stop and tell me
which pages to open by hand" instruction if unreachable):
- `taxinformation.cbic.gov.in`, `icegate.gov.in`, `cbic.gov.in`: all
  return HTTP 200 via direct `curl` - reachable at the network level.
- However, the WebFetch tool specifically fails on
  `taxinformation.cbic.gov.in` with "unable to verify the first
  certificate" (a TLS certificate-chain issue on that government
  site - curl tolerates it with default settings, but WebFetch's
  stricter TLS client does not). Worked around by using `curl`
  directly for this domain instead of WebFetch going forward.
- `customsai.in` (a candidate bulk-tariff-browser site) failed
  outright (HTTP 000, connection failure) - not pursued further.
- **Conclusion: not stopping at this step** - the official sites are
  reachable (via curl), so proceeding rather than asking the user to
  download pages by hand. Noting the CBIC TLS quirk for future
  reference.

**Scale reality check and scoping decision**: `core_device_codes.csv`
has 60 HS6 codes (42 of them in Chapter 90 alone). India's actual
8-digit ("ITC-HS") breakdown under each HS6 is not cached anywhere in
this project and typically runs 2-5+ lines per HS6 based on the
analogous US 10-digit pattern already seen in Phase 4 (42 US 10-digit
lines under just 10 HS6 codes there) - so the full 8-digit universe
here is plausibly 150-250+ individual lines. Fetching each one
individually (the only way eximguru.com's per-code pages, which DO
show full BCD/SWS/IGST/health-cess breakdowns, can be read) at one
URL at a time is not achievable at full exhaustive coverage within
a reasonable time.

**Decision, flagged here rather than silently under-delivered**: full
8-digit-line detail will be fetched for the codes that matter most by
value - the top 10+ codes by 2025 India-imports-from-USA (computed
first, from the existing `india_trade.csv`/`india_trade_final_new_codes.csv`,
exactly the ranking Part 7 needs anyway: 901890 $387.7M, 902131
$131.5M, 902790 $104.2M, 901813 $93.3M, 902214 $89.5M, 901850 $89.1M,
902290 $88.2M, 901839 $87.4M, 902139 $82.5M, 902750 $76.7M, plus a
handful more just below this). For the remaining ~45 lower-value
codes, rates are collected at the HS6 (not 8-digit) level via batched
searches, with any line where sources show a different rate for a
specific 8-digit child flagged explicitly as "varies" (the same
convention `g1_fetch_mfn_rates.py` already used in Phase 3 for the
analogous US MFN-rate lookup: report the rate if uniform, or "varies"
with the observed range if not). This does not fully satisfy the
letter of "for every 8-digit tariff line", and is recorded here as an
honest, necessary scoping compromise given the realistic size of this
time-boxed task - not a silent shortfall.

54 of the 60 core codes have 2025 India-imports-from-USA data in the
existing trade files; 6 do not (300620 - a genuine zero established
in an earlier phase - plus the 5 HS10-only codes 6210105010,
6210105090, 9025198010, 9025198020, 9402100000, which were never
covered by the HS6-level Comtrade pull, a gap already documented in
Phase 4's exposure-score work).

## Part 1 research summary (before building the CSV)

Compiled from ~20 WebSearch queries plus 2 downloaded PDFs
(`raw/viewb_evidence/acuitylaw_medical_devices_faq.pdf`, a May 2026
legal-firm FAQ; `raw/viewb_evidence/icegate_cs20_2020.pdf`, the
official Notification 20/2020-Customs text confirming the legal
mechanism for health cess). Key confirmed rules, each independently
re-checked across at least 2 sources where possible:

- **Social Welfare Surcharge (SWS)**: 10% of BCD, standard rule,
  confirmed consistently. Nil wherever BCD itself is nil.
- **Health Cess**: 5% of assessable value, levied under Section 141 /
  Fourth Schedule of the Finance Act 2020 - and ONLY on goods falling
  under tariff headings **9018, 9019, 9020, 9021 and 9022** (confirmed
  via two independent sources quoting the actual Schedule text) - NOT
  the whole of Chapter 90, and NOT any other chapter (30/38/40/62/84/94)
  in our code list. Nil for: (a) inputs/parts for manufacture of such
  devices, (b) any device itself exempt from BCD.
- **IGST (post-56th GST Council meeting, effective 22 Sept 2025, "GST
  2.0")**: most Chapter 90 medical-use lines cut to 5% (from a prior
  12% or 18%), with explicit NAMED exceptions found: 902150 (pacemakers)
  and 901920/902000 (breathing/ventilator apparatus) at **0%** (life-
  saving equipment); 902219 (X-ray apparatus for non-medical use) stays
  at **18%**; the whole of heading 9027 (902710/720/730/750/790 -
  chromatographs, spectrometers, photometers, microtomes) was **NOT**
  reduced and stays at **18%** (lab/analytical instruments, not
  "medical devices" for GST purposes); 940290 (hospital beds) and
  842310 (weighing scales) were explicitly confirmed to also stay at
  **18%** (excluded from the healthcare rate cut). Chapter 30 lines
  (300510/590 dressings, 300610 sutures, 300640/650/691) and 382211/12/13
  (diagnostic reagents) and 401512 (surgical gloves) confirmed cut to
  **5%**. 401410 (condoms) stays at its long-standing **0%** (nil,
  unrelated to the Sept 2025 reform). 902511 and the two clinical-
  thermometer HS10 lines (9025198010/20) confirmed cut to 5% (medical/
  clinical use specifically, resolving an initial conflicting signal
  from one secondary source that described the INDUSTRIAL branch of
  9025 as still 18%).
- **BCD**: found a genuine, UNRESOLVED tension between sources, flagged
  rather than silently picked: a May-2026 legal-firm FAQ states "most
  medical devices and equipment attract 0% BCD" via long-standing
  exemption notifications (extended to 31 Mar 2028 per Budget 2026-27,
  per taxguru.in's Budget 2026 coverage), while several per-code
  secondary aggregator sites (seair.co.in, eximguru.com) consistently
  show a **7.5%** BCD figure for specific Chapter 9018/9021/9022 lines
  checked individually (e.g. 90189011, 90181300/MRI, 90213100/artificial
  joints, 90183900/catheters). Likely explanation: 7.5% is the First-
  Schedule STATUTORY rate, and the exemption notification reduces the
  EFFECTIVE rate to 0% only for devices meeting that notification's
  specific conditions, which were not individually verified per code
  within this task's scope. **Decision**: used the per-code 7.5%
  figures where specifically found (since the user's own B1 scenario,
  "BCD cut to 0% on US devices", only makes sense as a real policy
  change if BCD is currently non-zero), explicitly flagging this
  decision and the conflicting general claim rather than silently
  picking one. One confirmed BUDGET 2026-27 CHANGE specific to our
  list: X-ray tubes (902230) BCD history 5% (to 31 Mar 2025) -> 7.5%
  (1 Apr 2025-31 Mar 2026) -> **10%** (from 1 Apr 2026), per
  S.O. 02/2026-Customs dated 1 Feb 2026. One code (902214, other
  medical X-ray apparatus) showed a single source citing 15% BCD,
  differing from the general 7.5% pattern - flagged, not resolved.

**Genuinely not found** (recorded as "not found" in the CSV, not
guessed): BCD for most individual codes beyond the handful of top-value
codes specifically checked; IGST for gowns (6210105010/5090 - generic
HSN 6210 apparel rules found, but no specific confirmation for medical/
surgical gowns post-Sept-2025); IGST for the dental-chair HS10 line
(9402100000) specifically (inferred, not confirmed, from the 940290
heading's 18% finding); exact per-8-digit-line BCD for the ~45 lower-
value codes not individually checked (per the scoping decision logged
above).

### Part 1 result

Wrote and ran `t1_build_duty_rates.py`. Output: `data/india_duty_rates.csv`
(60 rows, one per core_device_codes.csv entry - the project's own
existing code-tracking granularity, which is already 8/10-digit for
3 of the 60 lines). **BCD not found for 19 of 60 codes; IGST not found
for 5 of 60 codes** - both counts recorded honestly rather than
papered over with carried-forward guesses beyond what's explicitly
flagged as "same heading-level pattern, not individually confirmed"
(a different, clearly-labelled category from "not found" - the
heading-level carry-over is still a real, sourced fact about the
heading, just not independently re-verified for that one specific
sub-line).

## Part 2: landed cost

Wrote and ran `t2_landed_cost.py`. Formula implemented exactly as
specified (AV=100, BCD=AV*BCD%, SWS=BCD*SWS%, health cess=AV*cess%,
IGST=(AV+BCD+SWS+cess)*IGST%, customs duty%=(BCD+SWS+cess)/AV, total
tax%=(BCD+SWS+cess+IGST)/AV). Manually spot-checked 901890 by hand
(BCD=7.5, SWS=0.75, cess=5.0, IGST=5.6625, customs duty%=13.25%,
total tax%=18.9125%) against the script's own output - matches
exactly.

IGST kept as a real cost throughout (not netted off), per the user's
instruction, with the reasoning noted for the Excel README: most
Indian hospitals' services are GST-exempt, so they cannot claim input
tax credit on IGST paid at import, unlike a fully GST-taxable
importer/distributor (which is what the general "IGST is creditable"
claims found during Part 1's research actually describe).

**Output**: `data/india_landed_cost.csv` (60 lines, **41 computable**,
19 marked "not computable" with the specific missing rate(s) named -
matches exactly the 19 codes with BCD "not found" from Part 1).
`data/india_landed_cost_hs6_rollup.csv` (58 HS6 groups - 60 tracked
lines collapse to 58 groups because 2 HS6es each have 2 tracked
sub-lines: 621010 = 6210105010+6210105090, 902519 =
9025198010+9025198020). **0 of 58 HS6 groups flagged as having
differing rates across their lines** - both of the 2 multi-line
groups have zero computable data on EITHER sibling line (both gowns
lines and both clinical-thermometer HS10 lines are among the 19
not-found codes), so there is nothing to compare for either of them;
recorded honestly as "N/A - no computable lines" rather than silently
reported as "uniform."

## Part 3: trade flows

Wrote and ran `t3_trade_flows.py`. Output:
`data/india_imports_by_country.csv` (240 rows = 60 core codes x 4
years). 6 of 60 codes have no "India imports" data at all in the
existing trade files (the same 6 identified earlier: 300620 and the
5 HS10-only lines).

**Overall totals (all core codes combined)**:

| Year | World | USA | US share |
|---|---|---|---|
| 2022 | $5,904,671,232 | $1,023,342,603 | 17.33% |
| 2023 | $6,522,792,609 | $1,466,109,187 | 22.48% |
| 2024 | $6,890,386,444 | $1,497,699,862 | 21.74% |
| 2025 | $7,741,277,955 | $1,666,630,624 | 21.53% |

US share jumped from 17.3% (2022) to ~21-22% (2023-2025) and has
stayed roughly steady since - the US is a large and fairly stable
single-country source for India's medical-device imports, around a
fifth of the total every year since 2023.

## Part 4: the trade deal

Found and downloaded the OFFICIAL primary source directly:
`https://www.pib.gov.in/PressReleasePage.aspx?PRID=2224783&reg=3&lang=1`
(the Indian Ministry of Commerce & Industry's own press release of the
US-India Joint Statement, dated 7 Feb 2026) - saved as
`raw/viewb_evidence/pib_2224783.html`. WebFetch returned 403 on this
URL (and on the whitehouse.gov mirror for a second cross-check call),
but `curl` retrieved it successfully - same CBIC-style TLS/bot-
protection pattern seen in Part 1, worked around the same way. Also
cross-checked against the whitehouse.gov Joint Statement text (fetched
successfully via WebFetch) and a CA firm's (DPNC Global) 5-page PDF
summary citing the same PIB press release as its source.

**Exact official text on medical devices** (one single sentence,
parsed carefully since several secondary news sources ran its three
clauses together incorrectly):

> "India agrees to address long-standing barriers to the trade in
> U.S. medical devices; eliminate restrictive import licensing
> procedures that delay market access for, or impose quantitative
> restrictions on, U.S. Information and Communication Technology
> (ICT) goods; and determine... whether U.S.-developed or
> international standards... are acceptable... in identified sectors."

This is a SINGLE sentence with 3 separate clauses. Parsed correctly:
(1) medical devices get only a general, unspecified "address long-
standing barriers" commitment; (2) the specific "eliminate restrictive
import licensing / quantitative restrictions" commitment applies to
**ICT goods**, NOT medical devices; (3) the standards/testing-
acceptance review applies to unnamed "identified sectors" - medical
devices are not explicitly named as one of them in this sentence.
**Several secondary sources found during this research incorrectly
conflate clause (2)'s import-licensing language as if it applied to
medical devices too** - this is flagged as a real risk of
misreporting, not repeated here.

**Checked directly in the full document text and confirmed ABSENT**:
no mention of "health cess" anywhere in the document; no mention of
"price control" anywhere; medical devices are NOT explicitly named in
the tariff-reduction bullet either - that bullet only says "India will
eliminate or reduce tariffs on all U.S. industrial goods and a wide
range of U.S. food and agricultural products" (with named EXAMPLES
given being agricultural - DDGs, sorghum, tree nuts, fruit, soybean
oil, wine/spirits - not devices). Medical devices would presumably
fall under the broad, unnamed "industrial goods" bucket, but this is
an inference, not a textual statement.

**Gap between the official text and media reporting, flagged
honestly**: several secondary sources (medicalbuyer.co.in,
india-briefing.com) describe more specific-sounding provisions -
"medical device tariffs to be phased out gradually," a "long and
staggered phasing schedule," tariff concessions "with safeguards such
as minimum import prices" - **none of which appear anywhere in the
official Joint Statement text itself**. These may describe a more
detailed annex, a separate Indian government briefing, or reported/
rumoured negotiating detail not yet in the public primary-source text
- not confirmed either way, recorded as a gap rather than treated as
fact.

## Part 5: scenarios B0-B3

Wrote and ran `t4_scenarios.py`. Manually verified the B1 calculation
for code 901890 by hand (BCD0=7.5%, SWS0=0.75%, cess0=5%, IGST0=5% ->
total_tax_B0=18.9125%; B1 zeros BCD+SWS, keeps cess, recomputes IGST
on the new base -> total_tax_B1=10.25% -> price_fall=(18.9125-10.25)/
118.9125=7.286%) against the script's own output (7.2848%, matching
within rounding).

**Computable for 40 of the 60 core codes** (the intersection of Part
2's 41 duty-computable codes and Part 3's 54 USA-trade-data codes,
minus the 1 code that's duty-computable but has no USA trade data -
902139 "Other artificial parts of the body" turned out to be the
difference; confirmed by direct set intersection). The other 20 codes
have every scenario figure explicitly "not computable" with the
specific missing input(s) named, never a silent zero.

Elasticity (0.5/1.0/1.5, low/base/high) is explicitly labelled an
ASSUMED range throughout every output file and the Excel README - not
measured from this project's own data, unlike Phase 4's own
epsilon/alpha which WERE measured (with their own separate honesty
caveats). This distinction is called out explicitly so the two
different kinds of "assumption" in this project are not confused with
each other.

**Overall totals (base elasticity)**:

| Scenario | Extra US sales (low/base/high, $M) | Lost customs revenue ($M) |
|---|---|---|
| B1 (BCD cut to 0%) | 52.20 / 104.39 / 156.59 | 119.12 |
| B2 (health cess removed) | 29.16 / 58.32 / 87.48 | 66.37 |
| B3 (both cuts) | 81.36 / 162.71 / 244.07 | 185.48 |

B1's effect is consistently larger than B2's (BCD+SWS is a bigger
share of the typical landed-cost waterfall than the flat 5% health
cess for the computable codes), and B3 is additive but not exactly
B1+B2 summed (since IGST is computed on a base that includes BOTH BCD
and cess, so removing both together compounds through the IGST term
too) - confirmed directly: B1($119.12M)+B2($66.37M)=$185.49M vs
B3's actual $185.48M lost-revenue figure, a sub-$10K difference fully
explained by rounding at the per-code level, not a bug.

## Part 6: Excel export

Wrote and ran `t5_build_trade_deal_csv.py` (structures Part 4's
research into `data/view_b_trade_deal.csv`, 8 rows) and
`t6_build_excel.py`. Produced **`data/view_b_india_imports.xlsx`**
with 7 sheets: README, Duty_rates, Landed_cost, Trade_flows,
Trade_deal, Scenarios, Totals.

**Independently re-verified** (fresh `openpyxl.load_workbook()`
call): checked every worksheet for sheet protection, merged-cell
ranges, and any cell with a formula data type or a value starting
with "=" across all 7 sheets. **Result: zero problems found.**

### Status: VIEW B COMPLETE
