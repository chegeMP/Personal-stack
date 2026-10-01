select
    coin.key as crypto_id,
    (coin.value->>'usd')::double as price_usd,
    (coin.value->>'eur')::double as price_eur,
    (coin.value->>'gbp')::double as price_gbp,
    (coin.value->>'usd_market_cap')::double as market_cap_usd,
    (coin.value->>'usd_24h_vol')::double as volume_24h_usd,
    (coin.value->>'usd_24h_change')::double as change_24h_pct,
    timestamp as scraped_at
from {{ read_raw('crypto_prices') }},
unnest(map_entries(data)) as t(coin)
