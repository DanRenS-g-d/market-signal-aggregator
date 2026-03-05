"""
LAYER 3: Prediction Market Integration
- Authenticates as admin
- Creates a weekly market question per pair
- Each sentiment/technical source votes as a synthetic user
- Reads resulting probability for Layer 4
"""

import os
import sys
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection

PM_BASE_URL = os.environ.get("PM_BASE_URL", "https://prediction-market-production-6cd6.up.railway.app")
PM_ADMIN_USER = os.environ.get("PM_ADMIN_USER", "admin")
PM_ADMIN_PASS = os.environ.get("PM_ADMIN_PASS", "1234567")

PAIRS = [
    {
        "slug_key": "ec-vs-cnec-signal",
        "title": "Ecopetrol (EC) superara a Canacol (CNEC) en precio esta semana?",
        "ticker_a": "EC",
        "ticker_b": "CNEC.CN",
    },
    {
        "slug_key": "cib-vs-davivienda-signal",
        "title": "Bancolombia (CIB) superara a Davivienda (PFBCOLOM) en precio esta semana?",
        "ticker_a": "CIB",
        "ticker_b": "PFBCOLOM.CL",
    },
]


def get_admin_token():
    try:
        r = requests.post(
            f"{PM_BASE_URL}/api/auth/login",
            json={"username": PM_ADMIN_USER, "password": PM_ADMIN_PASS},
            timeout=10,
        )
        if r.status_code == 200:
            print(f"    [PM] Admin authenticated")
            return r.json().get("token")
        print(f"    [PM] Auth failed {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"    [PM] Auth exception: {e}")
    return None


def get_or_create_user_token(username: str):
    email = f"{username}@synthetic.msa"
    password = f"Synth_{username}_2026!"
    # Try login
    r = requests.post(f"{PM_BASE_URL}/api/auth/login",
                      json={"username": username, "password": password}, timeout=10)
    if r.status_code == 200:
        return r.json().get("token")
    # Register
    r = requests.post(f"{PM_BASE_URL}/api/auth/register",
                      json={"username": username, "email": email, "password": password}, timeout=10)
    if r.status_code == 200:
        return r.json().get("token")
    print(f"    [PM] Could not create user {username}: {r.text[:100]}")
    return None


def get_or_create_market(pair: dict, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    week = datetime.utcnow().strftime("%Y-W%U")
    slug = f"{pair['slug_key']}-{week}"

    # Check existing
    r = requests.get(f"{PM_BASE_URL}/api/markets", timeout=10)
    if r.status_code == 200:
        for m in r.json().get("markets", []):
            if m.get("slug") == slug:
                print(f"    [PM] Market exists id={m['id']}")
                return m["id"]

    # Create
    payload = {
        "title": pair["title"],
        "description": "Senial automatica del market-signal-aggregator",
        "resolution_criteria": f"YES si {pair['ticker_a']} sube mas % que {pair['ticker_b']} esta semana.",
        "sources": "Yahoo Finance, Alpha Vantage, Google News",
        "category": "economia",
        "close_time": (datetime.utcnow() + timedelta(days=5)).isoformat() + "Z",
        "resolve_deadline": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
        "b": 50.0,
        "max_shares_per_buy": 100.0,
        "max_long_position_per_user": 500.0,
    }
    r = requests.post(f"{PM_BASE_URL}/api/admin/create-market",
                      json=payload, headers=headers, timeout=10)
    if r.status_code == 200:
        mid = r.json().get("market", {}).get("id")
        print(f"    [PM] Market created id={mid}")
        return mid
    print(f"    [PM] Create failed: {r.status_code} {r.text[:200]}")
    return None


def cast_vote(market_id: int, outcome: str, shares: float, source: str):
    username = f"synth_{source[:20]}"
    token = get_or_create_user_token(username)
    if not token:
        return False
    r = requests.post(
        f"{PM_BASE_URL}/api/market/{market_id}/buy",
        json={"outcome": outcome, "shares": shares},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code == 200:
        print(f"      [PM] {source} -> {outcome} ({shares:.1f} shares) OK")
        return True
    print(f"      [PM] Vote failed {source}: {r.status_code} {r.text[:100]}")
    return False


def get_market_probability(market_id: int):
    try:
        r = requests.get(f"{PM_BASE_URL}/api/market/{market_id}", timeout=10)
        if r.status_code == 200:
            m = r.json().get("market", {})
            return {"price_yes": m.get("price_yes", 0.5), "price_no": m.get("price_no", 0.5)}
    except Exception as e:
        print(f"    [PM] Probability read error: {e}")
    return {"price_yes": 0.5, "price_no": 0.5}


def get_latest_sentiment(ticker: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT signal, score FROM sentiment
        WHERE ticker = %s ORDER BY analyzed_at DESC LIMIT 1
    """, (ticker,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"signal": row[0], "score": float(row[1])} if row else None


def get_latest_technicals(ticker: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rsi_signal, macd_signal, sma20_signal FROM technicals
        WHERE ticker = %s AND error IS NULL ORDER BY fetched_at DESC LIMIT 1
    """, (ticker,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"rsi_signal": row[0], "macd_signal": row[1], "sma20_signal": row[2]} if row else None


def save_pm_signal(pair_name: str, market_id: int, prob_yes: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pm_signals (
            id              SERIAL PRIMARY KEY,
            pair_name       TEXT NOT NULL,
            market_id       INTEGER NOT NULL,
            probability_yes NUMERIC NOT NULL,
            signal          TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)
    signal = "bullish_a" if prob_yes > 0.55 else ("bearish_a" if prob_yes < 0.45 else "neutral")
    cur.execute("""
        INSERT INTO pm_signals (pair_name, market_id, probability_yes, signal)
        VALUES (%s, %s, %s, %s)
    """, (pair_name, market_id, prob_yes, signal))
    conn.commit(); cur.close(); conn.close()
    return signal


def run_prediction_market_layer():
    print(f"\n{'='*50}")
    print(f"Layer 3: Prediction Market at {datetime.utcnow().isoformat()}")
    print(f"{'='*50}")

    admin_token = get_admin_token()
    if not admin_token:
        print("[PM] Cannot proceed without admin token.")
        return []

    results = []

    for pair in PAIRS:
        print(f"\n[->] {pair['ticker_a']} vs {pair['ticker_b']}")

        sent_a = get_latest_sentiment(pair["ticker_a"])
        sent_b = get_latest_sentiment(pair["ticker_b"])
        tech_a = get_latest_technicals(pair["ticker_a"])

        market_id = get_or_create_market(pair, admin_token)
        if not market_id:
            continue

        # Vote: sentiment A
        if sent_a:
            outcome = "YES" if sent_a["signal"] == "bullish" else "NO"
            shares = min(50.0, max(5.0, abs(sent_a["score"]) * 100))
            cast_vote(market_id, outcome, shares, f"sent_{pair['ticker_a']}")

        # Vote: sentiment B (inverse)
        if sent_b:
            outcome = "NO" if sent_b["signal"] == "bullish" else "YES"
            shares = min(50.0, max(5.0, abs(sent_b["score"]) * 100))
            cast_vote(market_id, outcome, shares, f"sent_{pair['ticker_b']}")

        # Vote: technicals A
        if tech_a:
            bull = sum([
                tech_a.get("macd_signal") == "bullish",
                tech_a.get("sma20_signal") == "bullish",
                tech_a.get("rsi_signal") == "oversold",
            ])
            outcome = "YES" if bull >= 2 else "NO"
            cast_vote(market_id, outcome, 20.0, f"tech_{pair['ticker_a']}")

        prob = get_market_probability(market_id)
        signal = save_pm_signal(
            f"{pair['ticker_a']}_vs_{pair['ticker_b']}", market_id, prob["price_yes"]
        )

        print(f"    -> Probability YES: {prob['price_yes']:.3f} | Signal: {signal.upper()}")
        results.append({
            "pair": f"{pair['ticker_a']}_vs_{pair['ticker_b']}",
            "market_id": market_id,
            "probability_yes": prob["price_yes"],
            "signal": signal,
        })

    return results


if __name__ == "__main__":
    results = run_prediction_market_layer()
    print("\n-- LAYER 3 SUMMARY --")
    for r in results:
        print(f"  {r['pair']}: p={r['probability_yes']:.3f} -> {r['signal'].upper()}")