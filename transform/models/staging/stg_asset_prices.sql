select
    metal.key as asset_name,
    metal.value->>'currency' as currency,
    (metal.value->>'price')::double as price,
    timestamp as scraped_at
from {{ read_raw('asset_prices') }},
unnest(map_entries(data)) as t(metal)
