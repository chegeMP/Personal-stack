-- One row per stock per day, from the last scrape of that day.
select
    symbol,
    close_price,
    open_price,
    high_price,
    low_price,
    volume,
    change_usd,
    change_pct,
    scraped_at::date as snapshot_date,
    scraped_at
from {{ ref('stg_stock_prices') }}
qualify scraped_at = max(scraped_at) over (partition by symbol, scraped_at::date)
