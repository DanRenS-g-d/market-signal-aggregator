import os
import time
import requests
import feedparser
from datetime import datetime
from config import SEARCH_TERMS, YAHOO_MAP

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

# Alpha Vantage symbol map (AV uses different symbols for some BVC tickers)
AV_SYMBOL_MAP = {
    "EC":            "EC",
    "CNEC.CN":       "CNEC",
    "GPRK":          "GPRK",
    "CIB":           "CIB",
    "PFBCOLOM.CL":   "PFBCOLOM",
    "AVAL":          "AVAL",
    "TGLS":          "TGLS",
    # BVC tickers — Alpha Vantage has limited coverage, fallback to Yahoo
    "CIBEST.CL":     None,
    "PFCIBEST.CL":   None,
    "ISA.CL":        None,
    "GEB.CL":        None,
    "GRUPSURA.CL":   None,
    "PFGRUPSURA.CL": None,
    "CEMARGOS.CL":   None,
}


def fetch_google_news(ticker: str) -> list[dict]:
    results = []
    for term in SEARCH_TERMS.get(ticker, [ticker]):
        url = f"https://news.google.com/rss/search?q={term.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            results.append({
                "ticker":    ticker,
                "title":     entry.get("title", ""),
                "summary":   entry.get("summary", ""),
                "link":      entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        time.sleep(1)
    return results


def _technicals_from_alpha_vantage(ticker: str, symbol: str) -> dict:
    """Fetch technicals from Alpha Vantage for NYSE-listed tickers."""
    try:
        r = requests.get("https://www.alphavantage.co/query", params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": ALPHA_VANTAGE_KEY,
        }, timeout=15)
        data = r.json()

        if "Time Series (Daily)" not in data:
            note = data.get("Note") or data.get("Information") or "unknown"
            return {"ticker": ticker, "error": f"AV: {note[:80]}"}

        series = data["Time Series (Daily)"]
        dates = sorted(series.keys(), reverse=True)[:30]
        closes = [float(series[d]["4. close"]) for d in dates]
        volumes = [float(series[d]["5. volume"]) for d in dates]
        closes.reverse(); volumes.reverse()
        return _compute_indicators(ticker, closes, volumes)

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def _technicals_from_yfinance(ticker: str) -> dict:
    """Fallback: fetch technicals from yfinance for BVC tickers."""
    try:
        import yfinance as yf
        symbol = YAHOO_MAP.get(ticker, ticker)
        hist = yf.Ticker(symbol).history(period="60d")
        if hist.empty:
            return {"ticker": ticker, "error": f"yfinance: no data for {symbol}"}
        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()
        return _compute_indicators(ticker, closes, volumes)
    except Exception as e:
        return {"ticker": ticker, "error": f"yfinance: {e}"}


def _compute_indicators(ticker: str, closes: list, volumes: list) -> dict:
    """Compute RSI, MACD, SMA20 from price series."""
    def calc_rsi(prices, period=14):
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(max(diff, 0)); losses.append(max(-diff, 0))
        if len(gains) < period: return 50.0
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        return round(100 - (100 / (1 + ag / al)), 2) if al else 100.0

    def ema(prices, span):
        k = 2 / (span + 1)
        r = [prices[0]]
        for p in prices[1:]: r.append(p * k + r[-1] * (1 - k))
        return r

    rsi = calc_rsi(closes)
    ema12 = ema(closes, 12); ema26 = ema(closes, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    sig = ema(macd, 9)
    macd_signal = "bullish" if macd[-1] > sig[-1] else "bearish"
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
    sma_signal = "bullish" if closes[-1] > sma20 else "bearish"
    avg_vol = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else volumes[-1]

    return {
        "ticker":        ticker,
        "price":         round(closes[-1], 4),
        "rsi":           rsi,
        "rsi_signal":    "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
        "macd_signal":   macd_signal,
        "sma20_signal":  sma_signal,
        "volume_signal": "high" if volumes[-1] > avg_vol else "normal",
        "error":         None,
    }


def compute_technicals(ticker: str) -> dict:
    if not ALPHA_VANTAGE_KEY:
        return {"ticker": ticker, "error": "no ALPHA_VANTAGE_KEY"}

    av_symbol = AV_SYMBOL_MAP.get(ticker)

    if av_symbol:
        return _technicals_from_alpha_vantage(ticker, av_symbol)
    else:
        # BVC ticker — use yfinance
        return _technicals_from_yfinance(ticker)


def fetch_twitter(ticker: str) -> list[dict]:
    token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not token or token == "your_bearer_token_here":
        print(f"[Twitter] No token — skipping {ticker}")
        return []

    results = []
    headers = {"Authorization": f"Bearer {token}"}
    for term in SEARCH_TERMS.get(ticker, [ticker])[:1]:
        try:
            r = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=headers,
                params={"query": f"{term} lang:en -is:retweet", "max_results": 10,
                        "tweet.fields": "created_at,text,public_metrics"},
                timeout=10,
            )
            if r.status_code == 200:
                for tweet in r.json().get("data", []):
                    results.append({
                        "ticker": ticker, "text": tweet.get("text", ""),
                        "created_at": tweet.get("created_at", ""),
                        "likes": tweet.get("public_metrics", {}).get("like_count", 0),
                        "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
                    })
        except Exception as e:
            print(f"[Twitter] Exception: {e}")
        time.sleep(1)
    return results