#!/usr/bin/env python3
"""Run every scraper. A failed scraper sends an alert email and is retried.

Exits non-zero if any scraper still fails after its last attempt.
"""

import logging
import socket
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from base import PROJECT_DIR, send_alert
from scrapers import ALL_SCRAPERS

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 60
LOG_FILE = PROJECT_DIR / "logs" / f"scrape_{datetime.now():%Y-%m-%d}.log"

ALERT_SUBJECT = "[personal-stack] {scraper} failed ({status})"
ALERT_BODY = """\
The {scraper} scraper failed.

Scraper:    {scraper}
Attempt:    {attempt} of {max_attempts}
Time:       {time}
Host:       {host}
Next step:  {next_step}

Error
-----
{error}

Where it failed
---------------
{where}
Full traceback: {log_file}
"""

log = logging.getLogger("run_all")


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )


def project_frames(error: Exception) -> str:
    """The traceback frames inside ingest/, skipping library internals (those stay in the log)."""
    ingest_dir = str(Path(__file__).resolve().parent)
    frames = [f for f in traceback.extract_tb(error.__traceback__) if f.filename.startswith(ingest_dir)]
    return "".join(traceback.format_list(frames)) or "Outside the project code, see the log.\n"


def alert_message(scraper_name: str, attempt: int, error: Exception) -> tuple[str, str]:
    if attempt < MAX_ATTEMPTS:
        status = f"attempt {attempt}/{MAX_ATTEMPTS}, retrying"
        next_step = f"Retrying in {RETRY_DELAY_SECONDS} seconds."
    else:
        status = f"gave up after {MAX_ATTEMPTS} attempts"
        next_step = ("No more retries in this run. The dashboard keeps showing the last "
                     "successful snapshot for this source until a later run succeeds.")
    subject = ALERT_SUBJECT.format(scraper=scraper_name, status=status)
    body = ALERT_BODY.format(
        scraper=scraper_name,
        attempt=attempt,
        max_attempts=MAX_ATTEMPTS,
        time=f"{datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z}",
        host=socket.gethostname(),
        next_step=next_step,
        error=f"{type(error).__name__}: {error}",
        where=project_frames(error),
        log_file=LOG_FILE,
    )
    return subject, body


def run_with_retries(scraper) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            scraper.run()
            log.info("%s succeeded", scraper.name)
            return True
        except Exception as e:
            log.exception("%s failed (attempt %d/%d)", scraper.name, attempt, MAX_ATTEMPTS)
            send_alert(*alert_message(scraper.name, attempt, e))
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    return False


def main() -> int:
    configure_logging()
    results = {cls.name: run_with_retries(cls()) for cls in ALL_SCRAPERS}

    failed = [name for name, ok in results.items() if not ok]
    log.info("%d/%d scrapers succeeded", len(results) - len(failed), len(results))
    if failed:
        log.error("Failed: %s", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
