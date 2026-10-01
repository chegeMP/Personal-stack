#!/usr/bin/env bash
# Scrape every source, then rebuild the warehouse tables with dbt.
# dbt runs even if a scraper failed, so the other sources still refresh.
set -u
cd "$(dirname "$0")"

.venv/bin/python ingest/run_all.py
scrape_status=$?

(cd transform && ../.venv/bin/dbt run --profiles-dir . --quiet)
dbt_status=$?

exit $(( scrape_status || dbt_status ))
