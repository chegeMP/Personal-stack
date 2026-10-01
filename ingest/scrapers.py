"""One scraper per data source. Each run writes one snapshot to data/raw/<name>/."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

from base import BaseScraper


class CryptoPriceScraper(BaseScraper):
    """CoinGecko spot prices, market cap and 24h volume. No API key needed."""

    name = "crypto_prices"
    coins = [
        "bitcoin", "ethereum", "cardano", "solana", "ripple",
        "polkadot", "dogecoin", "litecoin", "chainlink", "uniswap",
    ]

    def run(self) -> None:
        data = self.fetch(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ",".join(self.coins),
                "vs_currencies": "usd,eur,gbp",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
        )
        self.save_json(data)


class ForexRatesScraper(BaseScraper):
    """exchangerate-api.com daily rates against FOREX_BASE (default USD). No API key needed."""

    name = "forex_rates"

    def run(self) -> None:
        base = os.getenv("FOREX_BASE", "USD")
        data = self.fetch(f"https://api.exchangerate-api.com/v4/latest/{base}")
        self.save_json(data)


class StockPriceScraper(BaseScraper):
    """Stock prices from Yahoo Finance via yfinance (real data, no API key needed)."""

    name = "stock_prices"
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "JPM", "JNJ", "V"]

    def run(self) -> None:
        data = {}
        def fetch_stock(symbol):
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist.empty:
                raise ValueError(f"No data for {symbol}")
            today = hist.iloc[-1]
            yesterday = hist.iloc[-2] if len(hist) > 1 else today

            close = float(today["Close"])
            prev_close = float(yesterday["Close"])
            change_usd = close - prev_close
            change_pct = (change_usd / prev_close * 100) if prev_close != 0 else 0

            return symbol, {
                "close": round(close, 2),
                "open": round(float(today["Open"]), 2),
                "high": round(float(today["High"]), 2),
                "low": round(float(today["Low"]), 2),
                "volume": int(today["Volume"]),
                "change": round(change_usd, 2),
                "change_pct": round(change_pct, 2),
            }
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_stock, symbol): symbol for symbol in self.symbols}
            for future in as_completed(futures):
                symbol, stock_data = future.result()
                data[symbol] = stock_data
        self.save_json(data)


class AssetPriceScraper(BaseScraper):
    """gold-api.com spot prices for precious metals, in USD per troy ounce. No API key needed."""

    name = "asset_prices"
    symbols = {"XAU": "gold", "XAG": "silver", "XPT": "platinum", "XPD": "palladium"}

    def run(self) -> None:
        data = {}
        def fetch_price(symbol_pair):
            symbol, metal = symbol_pair
            quote = self.fetch(f"https://api.gold-api.com/price/{symbol}")
            return metal, {"price": quote["price"], "currency": quote["currency"]}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(fetch_price, item): item for item in self.symbols.items()}
            for future in as_completed(futures):
                metal, price_data = future.result()
                data[metal] = price_data
        self.save_json(data)


ALL_SCRAPERS = [
    CryptoPriceScraper,
    StockPriceScraper,
    ForexRatesScraper,
    AssetPriceScraper,
]
