import os
import time
import requests
import feedparser
from datetime import datetime
from config import SEARCH_TERMS

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

# ── GOOGLE NEWS RSS ───────────────────────────────────────────────────────────

def fetch_google_news(ticker: str) -> list[dict]:
    results = []
    for term in SEARCH_TERMS.get(ticker, [ticker]):
        url = f"https://news.google.com/rss/search?q={term.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            results.append({
                "ticker": ticker,
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        time.sleep(1)
    return results


# ── ALPHA VANTAGE TECHNICALS ──────────────────────────────────────────────────

def compute_technicals(ticker: str) -> dict:
    if not ALPHA_VANTAGE_KEY:
        return {"ticker": ticker, "error": "no ALPHA_VANTAGE_KEY set"}

    symbol_map = {
        "EC":           "EC",
        "CNEC.CN":      "CNEC",
        "CIB":          "CIB",
        "PFBCOLOM.CL":  "PFBCOLOM",
    }
    symbol = symbol_map.get(ticker, ticker)

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": ALPHA_VANTAGE_KEY,
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if "Time Series (Daily)" not in data:
            note = data.get("Note") or data.get("Information") or "unknown error"
            return {"ticker": ticker, "error": f"Alpha Vantage: {note[:100]}"}

        series = data["Time Series (Daily)"]
        dates = sorted(series.keys(), reverse=True)[:30]
        closes = [float(series[d]["4. close"]) for d in dates]
        volumes = [float(series[d]["5. volume"]) for d in dates]
        closes.reverse()
        volumes.reverse()

        # RSI 14
        def calc_rsi(prices, period=14):
            gains, losses = [], []
            for i in range(1, len(prices)):
                diff = prices[i] - prices[i-1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            if len(gains) < period:
                return 50.0
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            return round(100 - (100 / (1 + rs)), 2)

        # MACD 12/26/9
        def ema(prices, span):
            k = 2 / (span + 1)
            result = [prices[0]]
            for p in prices[1:]:
                result.append(p * k + result[-1] * (1 - k))
            return result

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd_line = [a - b for a, b in zip(ema12, ema26)]
        signal_line = ema(macd_line, 9)
        macd_signal = "bullish" if macd_line[-1] > signal_line[-1] else "bearish"

        # SMA 20
        sma20 = sum(closes[-20:]) / 20
        current = closes[-1]
        sma_signal = "bullish" if current > sma20 else "bearish"

        # Volume
        avg_vol = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else volumes[-1]
        vol_signal = "high" if volumes[-1] > avg_vol else "normal"

        rsi = calc_rsi(closes)

        return {
            "ticker":        ticker,
            "price":         round(current, 4),
            "rsi":           rsi,
            "rsi_signal":    "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal":   macd_signal,
            "sma20_signal":  sma_signal,
            "volume_signal": vol_signal,
            "error":         None,
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── TWITTER/X ─────────────────────────────────────────────────────────────────

def fetch_twitter(ticker: str) -> list[dict]:
    token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not token or token == "your_bearer_token_here":
        print(f"[Twitter] No token — skipping {ticker}")
        return []

    results = []
    headers = {"Authorization": f"Bearer {token}"}

    for term in SEARCH_TERMS.get(ticker, [ticker])[:1]:
        params = {
            "query": f"{term} lang:en -is:retweet",
            "max_results": 10,
            "tweet.fields": "created_at,text,public_metrics",
        }
        try:
            r = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=headers,
                params=params,
                timeout=10,
            )
            if r.status_code == 200:
                for tweet in r.json().get("data", []):
                    results.append({
                        "ticker": ticker,
                        "text": tweet.get("text", ""),
                        "created_at": tweet.get("created_at", ""),
                        "likes": tweet.get("public_metrics", {}).get("like_count", 0),
                        "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
                    })
            else:
                print(f"[Twitter] {r.status_code} for '{term}': {r.text[:200]}")
        except Exception as e:
            print(f"[Twitter] Exception: {e}")
        time.sleep(1)

    return results