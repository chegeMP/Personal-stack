{#- Every snapshot a scraper has written, as one (timestamp, data) row per file. -#}
{% macro read_raw(source, data_type='MAP(VARCHAR, JSON)') %}
read_json(
    '{{ var("raw_dir") }}/{{ source }}/*.json',
    columns = {'timestamp': 'TIMESTAMP', 'data': '{{ data_type }}'}
)
{% endmacro %}
