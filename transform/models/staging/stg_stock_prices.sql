select
    stock.key as symbol,
    (stock.value->>'close')::double as close_price,
    (stock.value->>'open')::double as open_price,
    (stock.value->>'high')::double as high_price,
    (stock.value->>'low')::double as low_price,
    (stock.value->>'volume')::bigint as volume,
    (stock.value->>'change')::double as change_usd,
    (stock.value->>'change_pct')::double as change_pct,
    timestamp as scraped_at
from {{ read_raw('stock_prices') }},
unnest(map_entries(data)) as t(stock)
