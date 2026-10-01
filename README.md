# personal-stack

A small self-hosted data pipeline. Python scrapers pull data from public APIs once a day, dbt models it into DuckDB, and a Streamlit dashboard displays it.

```
ingest/       scrapers -> data/raw/<scraper>/<timestamp>.json
transform/    dbt project -> warehouse.duckdb
dashboards/   Streamlit app reading warehouse.duckdb
run_pipeline.sh   scrape, then dbt run (what the scheduler calls)
```

## Data sources

None of these need an API key.

| Scraper | API | dbt fact table |
|---|---|---|
| `crypto_prices` | CoinGecko `simple/price` | `fct_crypto_daily` |
| `stock_prices` | Yahoo Finance via yfinance | `fct_stock_daily` |
| `forex_rates` | exchangerate-api.com v4 | `fct_forex_rates` |
| `asset_prices` | gold-api.com (gold, silver, platinum, palladium) | `fct_asset_prices` |

Each fact table has a matching `stg_` model in `transform/models/staging/`.

## History

Every scraper run writes a new timestamped file, and nothing is overwritten. The staging models read all snapshots of a source (through the `read_raw` macro), so the warehouse holds the full history:

- The `_daily` fact tables keep the last scrape of each day, one row per entity per `snapshot_date`.

`data/raw/` is the source of truth. `warehouse.duckdb` can be deleted and rebuilt from it at any time with `dbt run`. Back up `data/raw/` if the history matters to you.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # optional: SMTP settings for failure alerts
```

## Running

```bash
./run_pipeline.sh                          # scrape everything, then rebuild the warehouse
.venv/bin/streamlit run dashboards/app.py  # dashboard on http://localhost:8501
```

To run the steps separately:

```bash
.venv/bin/python ingest/run_all.py
cd transform && ../.venv/bin/dbt run --profiles-dir .
```

dbt has to be run from `transform/`, because the models and `profiles.yml` use paths relative to it.

The dashboard opens the database read-only and caches each query for 5 minutes, so it can keep running while the pipeline writes.

## Failures and alerts

A scraper that raises is retried up to 3 times, 60 seconds apart, and each failed attempt sends an alert email if `ALERT_EMAIL` is set in `.env`. HTTP 429 and 5xx responses are also retried inside each attempt with a short backoff. `run_all.py` exits non-zero if any scraper still fails after its last attempt, and `run_pipeline.sh` exits non-zero if either the scrape or dbt fails.

Logs are written to `logs/scrape_YYYY-MM-DD.log` and to stdout, which ends up in the systemd journal.

## Scheduling on the VPS

`ingest/scraper.service` runs `run_pipeline.sh`, and `ingest/scraper.timer` triggers it daily at 02:00. The paths and `User=` in the service file assume the project lives at `/home/chegeh/projects/personal-stack`, so adjust them if the VPS layout differs.

```bash
sudo cp ingest/scraper.service ingest/scraper.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now scraper.timer

systemctl list-timers scraper.timer      # next run
sudo systemctl start scraper.service     # run once now
journalctl -u scraper.service -n 100     # output of the last runs
```

If you use cron instead of the timer:

```
0 2 * * * /home/chegeh/projects/personal-stack/run_pipeline.sh
```

## Adding a data source

1. Add a `BaseScraper` subclass to `ingest/scrapers.py` that sets `name` and implements `run()`, fetching with `self.fetch()` and writing with `self.save_json()`. Let exceptions propagate, since `run_all.py` handles retries and alerts. Append the class to `ALL_SCRAPERS`.
2. Add `transform/models/staging/stg_<name>.sql` selecting from `{{ read_raw('<name>') }}`, plus a `fct_` model in `models/marts/`.
3. Add a tab to `dashboards/app.py`.
