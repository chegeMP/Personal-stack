-- One row per currency per day, from the last scrape of that day.
select
    base_currency,
    target_currency,
    exchange_rate,
    scraped_at::date as snapshot_date,
    scraped_at
from {{ ref('stg_forex_rates') }}
where target_currency != base_currency
qualify scraped_at = max(scraped_at) over (partition by scraped_at::date)
