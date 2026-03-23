"""
Prediction Markets Integration
Fetches active markets from Polymarket and Kalshi,
detects divergences vs system signals, sends alerts to Telegram.
"""
 
import os
import requests
from datetime import datetime
 
DIVERGENCE_THRESHOLD = 0.20  # 20% gap triggers alert
 
# Keywords to search for relevant markets
SEARCH_KEYWORDS = {
    "oil price":        ["EC", "GPRK"],
    "crude oil":        ["EC", "GPRK"],
    "fed rate":         ["CIB", "AVAL"],
    "federal reserve":  ["CIB", "AVAL"],
    "brazil gdp":       ["EWZ"],
    "brazil economy":   ["EWZ"],
    "mexico economy":   ["EWW"],
    "colombia economy": ["EC", "CIB", "AVAL"],
    "emerging market":  ["EWZ", "EWW", "ECH", "EPU"],
    "korea economy":    ["EWY"],
    "taiwan economy":   ["EWT"],
    "south africa":     ["EZA"],
    "nigeria oil":      ["NGE"],
    "opec":             ["EC", "GPRK"],
    "recession":        ["EWZ", "EWW", "EWY"],
}
 
# Only accept markets with these financial keywords in the question
FINANCIAL_KEYWORDS = [
    "gdp", "economy", "economic", "recession", "inflation", "rate", "market",
    "stock", "oil", "crude", "opec", "fed", "central bank", "currency",
    "peso", "real", "won", "rand", "rupiah", "baht", "dollar", "etf",
    "emerging", "index", "trade", "export", "import", "growth", "deficit",
]
 
 
# ── Polymarket ────────────────────────────────────────────────────────────────
 
def fetch_polymarket_markets(keyword: str) -> list:
    """Search active Polymarket markets by keyword."""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": 20,
            "q": keyword,
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            markets = data if isinstance(data, list) else data.get("markets", [])
            return markets
    except Exception as e:
        print(f"    [Polymarket] Error fetching '{keyword}': {e}")
    return []
 
 
def is_financial_market(question: str) -> bool:
    """Filter out non-financial markets (sports, entertainment, etc)."""
    q = question.lower()
    # Reject if contains entertainment/sports keywords
    reject = ["nba", "nfl", "nhl", "mlb", "ufc", "oscars", "grammy", "celebrity",
              "movie", "film", "actor", "actress", "singer", "album", "song",
              "game", "gta", "playstation", "xbox", "manga", "anime",
              "kardashian", "trump tweet", "elon tweet", "viral"]
    if any(r in q for r in reject):
        return False
    # Accept if contains financial keywords
    return any(f in q for f in FINANCIAL_KEYWORDS)
 
 
def parse_polymarket_market(market: dict) -> dict | None:
    """Extract relevant fields from a Polymarket market."""
    try:
        question = market.get("question", "")
        if not is_financial_market(question):
            return None
        outcomes = market.get("outcomes", "[]")
        prices   = market.get("outcomePrices", "[]")
 
        # Parse string arrays if needed
        if isinstance(outcomes, str):
            import json
            outcomes = json.loads(outcomes)
        if isinstance(prices, str):
            import json
            prices = json.loads(prices)
 
        if not outcomes or not prices:
            return None
 
        # Get Yes probability (first outcome usually)
        yes_idx = next((i for i, o in enumerate(outcomes)
                       if str(o).lower() in ["yes", "yes."]), 0)
        yes_prob = float(prices[yes_idx]) if yes_idx < len(prices) else 0.5
 
        return {
            "source":      "Polymarket",
            "question":    question,
            "yes_prob":    round(yes_prob, 3),
            "url":         f"https://polymarket.com/market/{market.get('conditionId', '')}",
            "end_date":    market.get("endDate", ""),
            "volume":      market.get("volume", 0),
        }
    except Exception:
        return None
 
 
# ── Kalshi ────────────────────────────────────────────────────────────────────
 
def fetch_kalshi_markets(keyword: str) -> list:
    """Search active Kalshi markets by keyword."""
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {
            "status":        "open",
            "series_ticker": "",
            "limit":         20,
        }
        headers = {"Accept": "application/json"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            markets = r.json().get("markets", [])
            # Filter by keyword in title
            keyword_lower = keyword.lower()
            return [m for m in markets
                    if keyword_lower in m.get("title", "").lower()
                    or keyword_lower in m.get("subtitle", "").lower()]
    except Exception as e:
        print(f"    [Kalshi] Error fetching '{keyword}': {e}")
    return []
 
 
def parse_kalshi_market(market: dict) -> dict | None:
    """Extract relevant fields from a Kalshi market."""
    try:
        yes_price = market.get("yes_bid", market.get("last_price", 50))
        yes_prob  = float(yes_price) / 100 if yes_price > 1 else float(yes_price)
 
        return {
            "source":   "Kalshi",
            "question": market.get("title", ""),
            "yes_prob": round(yes_prob, 3),
            "url":      f"https://kalshi.com/markets/{market.get('ticker', '')}",
            "end_date": market.get("close_time", ""),
            "volume":   market.get("volume", 0),
        }
    except Exception:
        return None
 
 
# ── Divergence Detection ──────────────────────────────────────────────────────
 
def get_signal_confidence(ticker: str, signal_results: list) -> float | None:
    """Get system confidence for a ticker from signal results."""
    for result in signal_results:
        if result["signal"] == "neutral":
            continue
        active_ticker = result["ticker_a"] if result["signal"] == "long_a" else result["ticker_b"]
        if active_ticker == ticker:
            return result["confidence"]
    return None
 
 
def detect_divergences(signal_results: list) -> list:
    """
    Search prediction markets for topics related to active signals.
    Detect divergences where market probability differs from system confidence.
    """
    if not signal_results:
        return []
 
    divergences = []
    checked_questions = set()
 
    for keyword, tickers in SEARCH_KEYWORDS.items():
        # Check if any related ticker has an active signal
        relevant_signals = []
        for ticker in tickers:
            conf = get_signal_confidence(ticker, signal_results)
            if conf and conf >= 0.50:
                relevant_signals.append((ticker, conf))
 
        if not relevant_signals:
            continue
 
        # Fetch from both platforms
        pm_markets = fetch_polymarket_markets(keyword)
        kl_markets = fetch_kalshi_markets(keyword)
 
        all_markets = []
        for m in pm_markets:
            parsed = parse_polymarket_market(m)
            if parsed:
                all_markets.append(parsed)
        for m in kl_markets:
            parsed = parse_kalshi_market(m)
            if parsed:
                all_markets.append(parsed)
 
        for market in all_markets:
            question = market["question"]
            if question in checked_questions:
                continue
            checked_questions.add(question)
 
            yes_prob = market["yes_prob"]
 
            # Compare with system confidence
            for ticker, system_conf in relevant_signals:
                gap = abs(system_conf - yes_prob)
 
                if gap >= DIVERGENCE_THRESHOLD:
                    direction = "ABOVE" if system_conf > yes_prob else "BELOW"
                    divergences.append({
                        "ticker":      ticker,
                        "system_conf": system_conf,
                        "market_prob": yes_prob,
                        "gap":         round(gap, 3),
                        "direction":   direction,
                        "question":    question,
                        "source":      market["source"],
                        "url":         market["url"],
                    })
 
    # Sort by gap size
    divergences.sort(key=lambda x: x["gap"], reverse=True)
    return divergences[:5]  # top 5 divergences
 
 
# ── Telegram Formatting ───────────────────────────────────────────────────────
 
def format_divergences_for_telegram(divergences: list) -> str:
    if not divergences:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔮 <b>DIVERGENCIAS DETECTADAS</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Tu sistema vs mercados de predicción</i>")
 
    for d in divergences:
        gap_pct      = int(d["gap"] * 100)
        system_pct   = int(d["system_conf"] * 100)
        market_pct   = int(d["market_prob"] * 100)
        emoji        = "🚨" if d["gap"] >= 0.40 else "⚠️"
 
        lines.append("")
        lines.append(f"{emoji} <b>{d['ticker']}</b> — {d['source']}")
        lines.append(f"Tu sistema: {system_pct}% | Mercado: {market_pct}%")
        lines.append(f"Brecha: <b>{gap_pct} puntos</b> ({d['direction']} del mercado)")
        lines.append(f"Mercado: {d['question'][:80]}")
 
        if d["direction"] == "ABOVE":
            lines.append("💡 <i>Tu modelo es más optimista que el mercado</i>")
        else:
            lines.append("💡 <i>El mercado es más optimista que tu modelo</i>")
 
    lines.append("")
    lines.append("⚠️ <i>Divergencias = oportunidad potencial, no garantía</i>")
    return "\n".join(lines)
 
 
def run_prediction_markets(signal_results: list) -> list:
    """Main entry point — detect and return divergences."""
    print(f"\n[Prediction Markets] Scanning for divergences...")
    try:
        divergences = detect_divergences(signal_results)
        if divergences:
            print(f"    [PM] Found {len(divergences)} divergence(s)")
            for d in divergences:
                print(f"    [PM] {d['ticker']}: system={int(d['system_conf']*100)}% market={int(d['market_prob']*100)}% gap={int(d['gap']*100)}pts — {d['source']}")
        else:
            print(f"    [PM] No significant divergences found")
        return divergences
    except Exception as e:
        print(f"    [PM] Error (non-fatal): {e}")
        return []
 
 
if __name__ == "__main__":
    # Test with sample signals
    test_signals = [
        {"signal": "long_a", "ticker_a": "EWZ", "ticker_b": "EWW",
         "pair": "Brazil vs Mexico", "confidence": 0.75},
        {"signal": "long_a", "ticker_a": "EC", "ticker_b": "GPRK",
         "pair": "Oil Integrated vs E&P", "confidence": 0.50},
    ]
    divs = run_prediction_markets(test_signals)
    print(format_divergences_for_telegram(divs))