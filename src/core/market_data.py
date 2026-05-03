"""Lightweight market data fetchers for the OLED.

All endpoints are free and require no API key:
  - crypto:   api.coingecko.com  (BTC, ETH, etc.)
  - currency: api.frankfurter.app (USD, EUR, TRY, ...)
  - stock:    query1.finance.yahoo.com (AAPL, TSLA, ...)

Each fetcher returns a dict with at least value + change_pct, or None
on failure. Network calls happen in a QThread so the UI never blocks.
"""
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal


# Common crypto symbol → CoinGecko id.
_CRYPTO_ALIASES = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "LTC": "litecoin", "MATIC": "matic-network",
    "AVAX": "avalanche-2", "DOT": "polkadot", "LINK": "chainlink",
    "TRX": "tron", "BCH": "bitcoin-cash",
}


def _coingecko_id(symbol: str) -> str:
    s = symbol.strip()
    return _CRYPTO_ALIASES.get(s.upper(), s.lower())


def fetch_crypto(symbol: str) -> Optional[dict]:
    """symbol can be 'BTC', 'bitcoin', etc."""
    try:
        import requests
        cid = _coingecko_id(symbol)
        url = (f"https://api.coingecko.com/api/v3/simple/price"
               f"?ids={cid}&vs_currencies=usd&include_24hr_change=true")
        r = requests.get(url, timeout=6, headers={"User-Agent": "MacroPad/1.0"})
        r.raise_for_status()
        data = r.json()
        if cid not in data:
            return None
        usd = data[cid]["usd"]
        change = data[cid].get("usd_24h_change", 0.0) or 0.0
        return {
            "value": _format_value(usd),
            "change": f"{change:+.2f}",
            "currency": "USD",
            "label": symbol.upper(),
        }
    except Exception:
        return None


def fetch_currency(pair: str) -> Optional[dict]:
    """pair like 'USD-TRY' or 'EUR-USD'."""
    try:
        import requests
        if "-" in pair:
            base, quote = pair.split("-", 1)
        elif "/" in pair:
            base, quote = pair.split("/", 1)
        else:
            return None
        base, quote = base.upper().strip(), quote.upper().strip()
        url = f"https://api.frankfurter.app/latest?from={base}&to={quote}"
        r = requests.get(url, timeout=6, headers={"User-Agent": "MacroPad/1.0"})
        r.raise_for_status()
        data = r.json()
        rates = data.get("rates", {})
        if quote not in rates:
            return None
        return {
            "value": _format_value(rates[quote]),
            "change": "",
            "currency": quote,
            "label": f"{base}/{quote}",
        }
    except Exception:
        return None


def fetch_stock(symbol: str) -> Optional[dict]:
    """symbol like 'AAPL', 'MSFT', 'THYAO.IS' (BIST)."""
    try:
        import requests
        sym = symbol.strip().upper()
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
               f"?interval=1d&range=2d")
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return None
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        if price is None or prev is None or prev == 0:
            return None
        change = ((price - prev) / prev) * 100.0
        currency = meta.get("currency", "")
        return {
            "value": _format_value(price),
            "change": f"{change:+.2f}",
            "currency": currency,
            "label": sym,
        }
    except Exception:
        return None


def _format_value(v) -> str:
    """Compact human-friendly value for the OLED."""
    try:
        v = float(v)
    except (ValueError, TypeError):
        return ""
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 10_000:
        return f"{v:,.0f}"
    if v >= 100:
        return f"{v:,.1f}"
    if v >= 1:
        return f"{v:.2f}"
    return f"{v:.4f}".rstrip("0").rstrip(".")


class MarketFetchWorker(QThread):
    """One-shot worker — fetches a single symbol then emits result/none."""
    result = pyqtSignal(dict)
    failed = pyqtSignal()

    def __init__(self, mode: str, symbol: str):
        super().__init__()
        self._mode = mode
        self._symbol = symbol

    def run(self):
        if self._mode == "crypto":
            data = fetch_crypto(self._symbol)
        elif self._mode == "currency":
            data = fetch_currency(self._symbol)
        elif self._mode == "stock":
            data = fetch_stock(self._symbol)
        else:
            data = None
        if data:
            self.result.emit(data)
        else:
            self.failed.emit()
