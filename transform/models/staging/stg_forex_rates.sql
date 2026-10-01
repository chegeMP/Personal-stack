select
    data->>'base' as base_currency,
    rate.key as target_currency,
    rate.value as exchange_rate,
    timestamp as scraped_at
from {{ read_raw('forex_rates', 'JSON') }},
unnest(map_entries((data->'rates')::MAP(VARCHAR, DOUBLE))) as t(rate)
