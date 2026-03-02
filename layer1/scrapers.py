import os
import time
import requests
import feedparser
import yfinance as yf
from datetime import datetime
from config import SEARCH_TERMS

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


# ── YAHOO FINANCE TECHNICALS ──────────────────────────────────────────────────

def compute_technicals(ticker: str) -> dict:
    try:
        df = yf.download(ticker, period="30d", interval="1d", progress=False)
        if df.empty:
            return {"ticker": ticker, "error": "no data from Yahoo Finance"}

        close = df["Close"].squeeze()

        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        # MACD 12/26/9
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"

        # SMA 20
        sma20 = float(close.rolling(20).mean().iloc[-1])
        current = float(close.iloc[-1])
        sma_signal = "bullish" if current > sma20 else "bearish"

        # Volume
        vol = df["Volume"].squeeze()
        vol_signal = "high" if float(vol.iloc[-1]) > float(vol.iloc[-6:-1].mean()) else "normal"

        return {
            "ticker": ticker,
            "price": round(current, 4),
            "rsi": round(rsi, 2),
            "rsi_signal": "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal": macd_signal,
            "sma20_signal": sma_signal,
            "volume_signal": vol_signal,
            "error": None,
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
