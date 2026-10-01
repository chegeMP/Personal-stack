-- One row per entity per day, from the last scrape of that day.
select
    crypto_id,
    price_usd,
    price_eur,
    price_gbp,
    market_cap_usd,
    volume_24h_usd,
    change_24h_pct,
    scraped_at::date as snapshot_date,
    scraped_at
from {{ ref('stg_crypto_prices') }}
qualify scraped_at = max(scraped_at) over (partition by scraped_at::date)
