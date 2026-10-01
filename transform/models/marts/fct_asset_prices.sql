-- One row per entity per day, from the last scrape of that day.
select
    asset_name,
    currency,
    price,
    scraped_at::date as snapshot_date,
    scraped_at
from {{ ref('stg_asset_prices') }}
qualify scraped_at = max(scraped_at) over (partition by scraped_at::date)
