"""
common.py - small helper functions shared by the Phase 2 download scripts.

Nothing here downloads data by itself. The other scripts import these
functions so that the same, well-tested code is used everywhere.

Uses only the Python standard library (no "pip install" needed).
"""

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# The folder this file sits in. All other paths are built from it, so the
# scripts work no matter which folder you start them from.
HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"      # untouched copies of every server answer (evidence)
DATA_DIR = HERE / "data"    # cleaned CSV files built from the raw copies
LOG_DIR = HERE / "logs"     # a text log of every run

for folder in (RAW_DIR, DATA_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def read_codes():
    """Read hs6_codes.csv and return a list of rows (one dict per code)."""
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def log(message, log_name):
    """Print a message and also add it, with the time, to logs/<log_name>.txt."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line)
    with open(LOG_DIR / f"{log_name}.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json_safely(path, data):
    """
    Save data as JSON without ever leaving a half-written file.

    We first write to "<name>.tmp", then rename it. A rename is instant, so if
    you press Ctrl+C or the laptop loses power, either the old file or the
    complete new file exists - never a broken one. This is what makes the
    scripts safe to stop and restart (the "checkpoint").
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def fetch_json(url, params, log_name, tries=5, wait_seconds=2.0):
    """
    Ask a web server for data and return the answer as Python objects.

    url     : the address of the service
    params  : a dict of question parts, e.g. {"time": "2025-12"}
    tries   : how many times to try before giving up
    Returns : (status, data)
        status "ok"       -> data is the decoded JSON answer
        status "no_data"  -> the server said there is nothing for this question
        status "failed"   -> every try failed; data holds the last error text
        status "key_error"-> the server refused because of the API key; the
                             calling script stops the whole run at once

    If the server is busy or the connection drops, we wait and try again,
    waiting twice as long each time (2s, 4s, 8s ...). This is called
    "exponential backoff" and is the polite way to retry.
    """
    full_url = url + "?" + urllib.parse.urlencode(params, safe=",*")
    last_error = ""
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(
                full_url, headers={"User-Agent": "medical-device-tariff-study/1.0"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
                final_url = response.geturl()
                key_error = response.headers.get("X-DataWebAPI-KeyError")
            # A missing or wrong API key: Census redirects to a page named
            # missing_key.html or invalid_key.html. Retrying cannot fix this,
            # so stop at once and say so.
            if key_error or "missing_key" in final_url or "invalid_key" in final_url:
                return "key_error", f"API key missing or invalid (server sent {final_url})"
            # The Census service sends an empty answer (status 204) when a
            # question has no matching rows. That is not an error.
            if not body.strip():
                return "no_data", None
            try:
                return "ok", json.loads(body)
            except json.JSONDecodeError:
                # The server answered with a web page instead of data. That
                # means the question is being refused, not a passing glitch,
                # so we do not retry.
                return "failed", "Server sent a web page, not data: " + body[:200].replace("\n", " ")
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return "no_data", None
            last_error = f"HTTP {e.code}: {e.reason}"
            # 400/404 mean the question itself is wrong; retrying will not help.
            if e.code in (400, 404):
                return "failed", last_error
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = f"{type(e).__name__}: {e}"
        pause = wait_seconds * (2 ** (attempt - 1))
        log(f"  try {attempt}/{tries} failed ({last_error}); waiting {pause:.0f}s", log_name)
        time.sleep(pause)
    return "failed", last_error


def progress(done, total, started_at):
    """Return a short text like '12/40 (30%), about 3.5 min left'."""
    elapsed = time.time() - started_at
    if done == 0:
        return f"{done}/{total}"
    per_item = elapsed / done
    left_min = per_item * (total - done) / 60
    return f"{done}/{total} ({100 * done / total:.0f}%), about {left_min:.1f} min left"


def write_csv(path, rows, columns):
    """Write a list of dicts to a CSV file that Excel opens directly."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
