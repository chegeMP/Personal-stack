"""Streamlit dashboard over the DuckDB warehouse built by dbt."""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "warehouse.duckdb"

BLUE = "#0066cc"
PALETTE = [
    "#0066cc", "#00a3e0", "#1a2b8f", "#6699ff", "#00cc66",
    "#ff9900", "#ff6666", "#7a3db8", "#2eb8b8", "#999999",
]
MAJOR_CURRENCIES = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "INR", "KES", "ZAR", "SGD", "HKD", "SEK"]

st.set_page_config(page_title="Personal Data Analytics", layout="wide")

st.markdown(f"""
<style>
    [data-testid="stMetricValue"] {{ font-size: 2.5rem; color: {BLUE}; font-weight: bold; }}
    [data-testid="stMetricLabel"] {{ font-size: 0.95rem; color: #666; font-weight: 500; }}
    .section-title {{ color: {BLUE}; font-size: 1.3rem; font-weight: 600; margin: 20px 0 15px; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def query(sql: str) -> pd.DataFrame:
    # Short-lived read-only connections, so the nightly dbt run can take the write lock.
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        return conn.execute(sql).df()


def latest(table: str, order_by: str) -> pd.DataFrame:
    """Rows from the most recent snapshot_date in a daily fact table."""
    return query(f"select * from {table} where snapshot_date = "
                 f"(select max(snapshot_date) from {table}) order by {order_by}")


def section_title(text: str) -> None:
    st.markdown(f'<p class="section-title">{text}</p>', unsafe_allow_html=True)


def history_note(history: pd.DataFrame) -> None:
    if history["snapshot_date"].nunique() < 2:
        st.caption("History fills in as the pipeline runs on more days.")


def line_layout(fig: go.Figure, title: str, y_title: str, height: int = 400) -> go.Figure:
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title=y_title, hovermode="x unified",
                      template="plotly_white", height=height, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def crypto_tab() -> None:
    df = latest("fct_crypto_daily", "market_cap_usd desc")
    if df.empty:
        st.info("No crypto data yet. Run the pipeline to populate it.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Market Cap", f"${df['market_cap_usd'].sum() / 1e12:.2f}T",
                f"{df['change_24h_pct'].mean():.2f}% avg")
    btc = df[df["crypto_id"] == "bitcoin"]
    if not btc.empty:
        col2.metric("Bitcoin", f"${btc['price_usd'].iloc[0]:,.0f}", f"{btc['change_24h_pct'].iloc[0]:.2f}%")
    col3.metric("24h Volume", f"${df['volume_24h_usd'].sum() / 1e9:.1f}B", "total")
    top = df.loc[df["change_24h_pct"].idxmax()]
    col4.metric("Top Gainer", top["crypto_id"].capitalize(), f"{top['change_24h_pct']:.2f}%")

    history = query("select crypto_id, snapshot_date, price_usd from fct_crypto_daily order by snapshot_date")

    st.divider()
    left, right = st.columns(2)
    with left:
        coin = st.selectbox("Coin", df["crypto_id"], format_func=str.capitalize, key="crypto_coin")
        coin_history = history[history["crypto_id"] == coin]
        fig = go.Figure(go.Scatter(x=coin_history["snapshot_date"], y=coin_history["price_usd"],
                                   mode="lines+markers", line=dict(color=BLUE, width=3),
                                   hovertemplate="%{y:$,.4f}<extra></extra>"))
        st.plotly_chart(line_layout(fig, f"{coin.capitalize()} Price", "Price (USD)"), width="stretch")
    with right:
        fig = px.pie(df, values="market_cap_usd", names="crypto_id", title="Market Cap Distribution",
                     hole=0.4, color_discrete_sequence=PALETTE)
        fig.update_layout(height=470, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, width="stretch")

    history["indexed"] = history["price_usd"] / history.groupby("crypto_id")["price_usd"].transform("first") * 100
    fig = px.line(history, x="snapshot_date", y="indexed", color="crypto_id", markers=True,
                  color_discrete_sequence=PALETTE)
    st.plotly_chart(line_layout(fig, "Performance Since First Snapshot (first day = 100)", "Index"),
                    width="stretch")
    history_note(history)

    st.divider()
    section_title("Detailed Cryptocurrency Data")
    table = df[["crypto_id", "price_usd", "price_eur", "market_cap_usd", "volume_24h_usd", "change_24h_pct"]]
    table.columns = ["Coin", "Price (USD)", "Price (EUR)", "Market Cap", "Volume (24h)", "Change (24h)"]
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Price (USD)": st.column_config.NumberColumn(format="$%.4f"),
        "Price (EUR)": st.column_config.NumberColumn(format="€%.4f"),
        "Market Cap": st.column_config.NumberColumn(format="$%.0f"),
        "Volume (24h)": st.column_config.NumberColumn(format="$%.0f"),
        "Change (24h)": st.column_config.NumberColumn(format="%.2f%%"),
    })


def forex_tab() -> None:
    df = latest("fct_forex_rates", "target_currency")
    if df.empty:
        st.info("No forex data yet. Run the pipeline to populate it.")
        return

    base = df["base_currency"].iloc[0]
    majors = df[df["target_currency"].isin(MAJOR_CURRENCIES)]
    rates = majors.set_index("target_currency")["exchange_rate"]

    left, right = st.columns([2, 1])
    fig = go.Figure(go.Heatmap(
        z=[majors["exchange_rate"]], x=majors["target_currency"], y=[base],
        colorscale="RdYlBu", text=[majors["exchange_rate"]], texttemplate="%{text:.4f}",
        textfont={"size": 10}, colorbar=dict(title="Rate"),
    ))
    fig.update_layout(title=f"Major Currencies per 1 {base}", height=300, margin=dict(l=0, r=0, t=40, b=0))
    left.plotly_chart(fig, width="stretch")

    with right:
        section_title("Major Pairs")
        st.dataframe(majors[["target_currency", "exchange_rate"]], width="stretch", hide_index=True,
                     column_config={
                         "target_currency": "Currency",
                         "exchange_rate": st.column_config.NumberColumn("Rate", format="%.4f"),
                     })

    st.divider()
    section_title("Rate History")
    currency = st.selectbox("Currency", majors["target_currency"], key="forex_currency")
    history = query(f"select snapshot_date, exchange_rate from fct_forex_rates "
                    f"where target_currency = '{currency}' order by snapshot_date")
    fig = go.Figure(go.Scatter(x=history["snapshot_date"], y=history["exchange_rate"], mode="lines+markers",
                               line=dict(color=BLUE, width=3)))
    st.plotly_chart(line_layout(fig, f"{currency} per 1 {base}", currency, height=350), width="stretch")
    history_note(history)

    st.divider()
    section_title("Exchange Rate Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Currencies Tracked", len(df))
    for col, code in zip([col2, col3, col4], ["EUR", "GBP", "KES"]):
        if code in rates:
            col.metric(f"{code} per {base}", f"{rates[code]:.4f}")


def stocks_tab() -> None:
    df = latest("fct_stock_daily", "close_price desc")
    if df.empty:
        st.info("No stock data yet. Run the pipeline to populate it.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stocks Tracked", len(df))
    avg_change = df['change_pct'].mean()
    col2.metric("Avg Change", f"{avg_change:.2f}%" if avg_change == avg_change else "N/A")
    if df['change_pct'].notna().any():
        top_gainer = df.loc[df["change_pct"].idxmax()]
        col3.metric("Top Gainer", top_gainer["symbol"], f"{top_gainer['change_pct']:.2f}%")
        top_loser = df.loc[df["change_pct"].idxmin()]
        col4.metric("Top Loser", top_loser["symbol"], f"{top_loser['change_pct']:.2f}%")
    else:
        col3.metric("Top Gainer", "—", "—")
        col4.metric("Top Loser", "—", "—")

    st.divider()
    left, right = st.columns(2)
    with left:
        stock = st.selectbox("Stock", df["symbol"], key="stock_symbol")
        stock_history = query(f"select symbol, snapshot_date, close_price from fct_stock_daily "
                             f"where symbol = '{stock}' order by snapshot_date")
        fig = go.Figure(go.Scatter(x=stock_history["snapshot_date"], y=stock_history["close_price"],
                                   mode="lines+markers", line=dict(color=BLUE, width=3),
                                   hovertemplate="$%{y:,.2f}<extra></extra>"))
        st.plotly_chart(line_layout(fig, f"{stock} Price", "Price (USD)"), width="stretch")
    with right:
        fig = px.bar(df.sort_values("change_pct", ascending=False).head(10), x="change_pct", y="symbol",
                     orientation="h", title="Top 10 by Change %", color_discrete_sequence=[BLUE])
        fig.update_layout(template="plotly_white", height=470, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, width="stretch")

    st.divider()
    section_title("Stock Details")
    table = df[["symbol", "close_price", "open_price", "high_price", "low_price", "volume", "change_pct"]]
    table.columns = ["Symbol", "Close", "Open", "High", "Low", "Volume", "Change %"]
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Close": st.column_config.NumberColumn(format="$%.2f"),
        "Open": st.column_config.NumberColumn(format="$%.2f"),
        "High": st.column_config.NumberColumn(format="$%.2f"),
        "Low": st.column_config.NumberColumn(format="$%.2f"),
        "Volume": st.column_config.NumberColumn(format="%d"),
        "Change %": st.column_config.NumberColumn(format="%.2f%%"),
    })


def assets_tab() -> None:
    df = latest("fct_asset_prices", "price desc")
    if df.empty:
        st.info("No asset data yet. Run the pipeline to populate it.")
        return

    section_title("Precious Metals (spot, per troy ounce)")
    for col, (_, row) in zip(st.columns(len(df)), df.iterrows()):
        col.metric(f"{row['asset_name'].capitalize()} ({row['currency']}/oz)", f"${row['price']:,.2f}")

    st.divider()
    metal = st.selectbox("Metal", df["asset_name"], format_func=str.capitalize, key="asset_metal")
    history = query(f"select snapshot_date, price from fct_asset_prices "
                    f"where asset_name = '{metal}' order by snapshot_date")
    fig = go.Figure(go.Scatter(x=history["snapshot_date"], y=history["price"], mode="lines+markers",
                               line=dict(color=BLUE, width=3), hovertemplate="%{y:$,.2f}<extra></extra>"))
    st.plotly_chart(line_layout(fig, f"{metal.capitalize()} Price", "USD per troy ounce", height=350),
                    width="stretch")
    history_note(history)

    st.divider()
    section_title("Asset Details")
    table = df[["asset_name", "currency", "price"]]
    table.columns = ["Asset", "Currency", "Price"]
    st.dataframe(table, width="stretch", hide_index=True,
                 column_config={"Price": st.column_config.NumberColumn(format="$%.2f")})


def warehouse_tab() -> None:
    section_title("Data Warehouse Explorer")
    tables = query("select table_name from information_schema.tables "
                   "where table_schema = 'main' order by table_name")["table_name"].tolist()
    if not tables:
        st.info("No tables in the warehouse yet.")
        return

    selected = st.selectbox("Table", tables, key="warehouse_table")
    df = query(f'select * from "{selected}" limit 100')
    left, right = st.columns([3, 1])
    left.subheader(selected)
    right.metric("Rows shown", len(df))
    st.dataframe(df, width="stretch", height=500)


def last_scraped_at() -> str:
    tables = query("select table_name from information_schema.columns "
                   "where table_name like 'fct_%' and column_name = 'scraped_at'")["table_name"]
    if tables.empty:
        return "never"
    sql = " union all ".join(f"select max(scraped_at) as t from {t}" for t in tables)
    return f"{query(f'select max(t) as t from ({sql})')['t'].iloc[0]:%Y-%m-%d %H:%M}"


TABS = {
    "Cryptocurrency": crypto_tab,
    "Stocks": stocks_tab,
    "Foreign Exchange": forex_tab,
    "Assets": assets_tab,
    "Warehouse": warehouse_tab,
}


def main() -> None:
    st.markdown(f"""
    <h1 style='color: {BLUE}; margin-bottom: 5px;'>Personal Data Analytics</h1>
    <p style='color: #666; margin-top: 0;'>Daily snapshots of cryptocurrency, stocks, and asset prices</p>
    """, unsafe_allow_html=True)

    if not DB_PATH.exists():
        st.info("warehouse.duckdb not found. Run ./run_pipeline.sh first.")
        return

    st.divider()
    for tab, render in zip(st.tabs(list(TABS)), TABS.values()):
        with tab:
            try:
                render()
            except duckdb.CatalogException:
                st.info("No data for this tab yet. Run ./run_pipeline.sh to populate it.")

    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.caption("Source: scheduled API scrapers")
    col2.caption(f"Last scrape: {last_scraped_at()}")
    col3.caption("Built with Streamlit, DuckDB and dbt")


main()
