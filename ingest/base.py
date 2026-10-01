"""Shared HTTP, storage and alerting code for the scrapers."""

import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

load_dotenv(PROJECT_DIR / ".env")

log = logging.getLogger(__name__)


class BaseScraper:
    """Subclasses set `name` and implement `run()`, raising on failure."""

    name: str

    def __init__(self):
        self.logger = logging.getLogger(self.name)
        self.session = requests.Session()
        # Retries transient HTTP errors with 1s, 2s, 4s backoff before giving up.
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self, url: str, **kwargs) -> Any:
        self.logger.info("GET %s", url)
        response = self.session.get(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def save_json(self, data: Any) -> None:
        """Write one snapshot to data/raw/<name>/<timestamp>.json.

        Snapshots are never overwritten, so the dbt models can build history from them.
        """
        now = datetime.now()
        path = RAW_DIR / self.name / f"{now:%Y-%m-%dT%H%M%S}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": now.isoformat(), "source": self.name, "data": data}
        path.write_text(json.dumps(payload, indent=2, default=str))
        self.logger.info("Saved %s", path)

    def run(self) -> None:
        raise NotImplementedError


def send_alert(subject: str, body: str) -> None:
    """Email an alert if ALERT_EMAIL and the SMTP settings are configured in .env."""
    recipient = os.getenv("ALERT_EMAIL")
    if not recipient:
        return

    sender = os.getenv("SMTP_USERNAME")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(sender, os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)
        log.info("Alert sent to %s", recipient)
    except Exception:
        log.exception("Could not send alert email")
