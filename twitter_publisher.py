"""
Twitter/X Publisher
Posts one public signal per pipeline run to attract subscribers.
Shows signal direction and accuracy but NOT prices, TP, SL, or shares.
Those details are for paid Telegram subscribers only.
"""

import os
import requests
from datetime import datetime, timezone

# Credentials — set in Railway environment variables
TWITTER_API_KEY             = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET          = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

SUBSCRIBE_LINK = os.environ.get("SUBSCRIBE_LINK", "t.me/your_channel")


def post_tweet(text: str) -> bool:
    """Post a tweet using Twitter API v2 with OAuth 1.0a."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        print("    [Twitter] Missing credentials — skipping")
        return False

    try:
        import hmac, hashlib, base64, time, uuid
        from urllib.parse import quote

        url     = "https://api.twitter.com/2/tweets"
        method  = "POST"
        payload = {"text": text}

        # OAuth 1.0a signature
        ts      = str(int(time.time()))
        nonce   = uuid.uuid4().hex

        params = {
            "oauth_consumer_key":     TWITTER_API_KEY,
            "oauth_nonce":            nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp":        ts,
            "oauth_token":            TWITTER_ACCESS_TOKEN,
            "oauth_version":          "1.0",
        }

        # Build signature base string
        sorted_params = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}"
                                 for k, v in sorted(params.items()))
        base_str = f"{method}&{quote(url, safe='')}&{quote(sorted_params, safe='')}"
        sign_key = f"{quote(TWITTER_API_SECRET, safe='')}&{quote(TWITTER_ACCESS_TOKEN_SECRET, safe='')}"
        sig = base64.b64encode(
            hmac.new(sign_key.encode(), base_str.encode(), hashlib.sha1).digest()
        ).decode()

        params["oauth_signature"] = sig
        auth_header = "OAuth " + ", ".join(
            f'{quote(k, safe="")}="{quote(v, safe="")}"'
            for k, v in sorted(params.items())
        )

        r = requests.post(
            url,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )

        if r.status_code in (200, 201):
            print(f"    [Twitter] Posted successfully")
            return True
        else:
            print(f"    [Twitter] Failed {r.status_code}: {r.text[:150]}")
            return False

    except Exception as e:
        print(f"    [Twitter] Error: {e}")
        return False


def pick_best_signal(signal_results: list) -> dict | None:
    """
    Pick the single best signal to post publicly.
    Priority: highest confidence, then highest regime_score.
    Only post if confidence >= 0.50.
    """
    candidates = [r for r in signal_results
                  if r["signal"] != "neutral" and r["confidence"] >= 0.50]

    if not candidates:
        return None

    # Sort by confidence desc, then regime_score desc
    candidates.sort(
        key=lambda x: (x["confidence"], x.get("regime_score", 0)),
        reverse=True
    )
    return candidates[0]


def build_tweet(signal: dict, accuracy: float, total_trades: int) -> str:
    """
    Build public tweet — no prices, no TP/SL, no shares.
    Clean format, no emojis, no long dashes.
    Max 280 characters.
    """
    ticker    = signal["ticker_a"] if signal["signal"] == "long_a" else signal["ticker_b"]
    pair      = signal["pair"]
    conf_pct  = int(signal["confidence"] * 100)
    regime    = signal.get("regime", "")
    now       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Confidence label
    if conf_pct >= 75:
        conf_label = "High confidence"
    else:
        conf_label = "Signal"

    # Regime label
    regime_note = ""
    if regime == "strong":
        regime_note = "Regime: strong\n"
    elif regime == "moderate":
        regime_note = "Regime: moderate\n"

    tweet = (
        f"{conf_label}: LONG ${ticker}\n"
        f"Pair: {pair}\n"
        f"Confidence: {conf_pct}%\n"
        f"{regime_note}"
        f"System accuracy: {accuracy:.1f}% ({total_trades} trades)\n"
        f"Prices, TP and SL: subscribers only\n"
        f"{SUBSCRIBE_LINK}\n"
        f"#QuantTrading #ColombiaStocks #EmergingMarkets"
    )

    # Truncate if over 280 chars
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."

    return tweet


def get_system_accuracy() -> tuple[float, int]:
    """Get current accuracy from DB."""
    try:
        from db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins
            FROM paper_trades
            WHERE resolved = TRUE
        """)
        row = cur.fetchone()
        cur.close(); conn.close()
        total = int(row[0]) if row[0] else 0
        wins  = int(row[1]) if row[1] else 0
        acc   = round(wins / total * 100, 1) if total > 0 else 0.0
        return acc, total
    except Exception:
        return 0.0, 0


def run_twitter_publisher(signal_results: list) -> bool:
    """Main entry point — pick best signal and post to Twitter."""
    signal = pick_best_signal(signal_results)

    if not signal:
        print("    [Twitter] No signal worth posting (all neutral or low confidence)")
        return False

    accuracy, total_trades = get_system_accuracy()
    tweet = build_tweet(signal, accuracy, total_trades)

    print(f"    [Twitter] Posting: LONG ${signal['ticker_a'] if signal['signal'] == 'long_a' else signal['ticker_b']} conf={int(signal['confidence']*100)}%")
    print(f"    [Twitter] Tweet ({len(tweet)} chars):\n{tweet}")

    return post_tweet(tweet)


if __name__ == "__main__":
    # Test tweet format without posting
    test_signal = {
        "signal":       "long_a",
        "ticker_a":     "AVAL",
        "ticker_b":     "CIB",
        "pair":         "Aval vs Bancolombia",
        "confidence":   0.75,
        "regime":       "strong",
        "regime_score": 0.82,
    }
    tweet = build_tweet(test_signal, 76.9, 103)
    print(f"Tweet ({len(tweet)} chars):\n")
    print(tweet)