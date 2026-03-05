"""
Layer 4: Pair Signal Generation
- Combines sentiment + technicals for each pair
- Generates long_a | long_b | neutral signal
- Tracks source reputation
- Opens paper trades
"""

import os, sys, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
from config import PAIRS
from layer4.db_layer4 import (
    save_pair_signal, save_paper_trade,
    resolve_pending_paper_trades, upsert_source_reputation, prune_worst_sources
)


def get_week_number():
    return int(datetime.utcnow().strftime("%U")) + (datetime.utcnow().year - 2026) * 52


def extract_domain(url: str) -> str:
    if not url:
        return "unknown"
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return match.group(1) if match else "unknown"


def get_sentiment(ticker: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT signal, score, avg_positive, avg_negative
        FROM sentiment WHERE ticker=%s
        ORDER BY analyzed_at DESC LIMIT 1
    """, (ticker,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        return {"signal": row[0], "score": float(row[1]),
                "avg_pos": float(row[2]), "avg_neg": float(row[3])}
    return {"signal": "neutral", "score": 0.0, "avg_pos": 0.0, "avg_neg": 0.0}


def get_technicals(ticker: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rsi, rsi_signal, macd_signal, sma20_signal, price
        FROM technicals WHERE ticker=%s AND error IS NULL
        ORDER BY fetched_at DESC LIMIT 1
    """, (ticker,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        return {"rsi": float(row[0]) if row[0] else None,
                "rsi_signal": row[1], "macd_signal": row[2],
                "sma20_signal": row[3], "price": float(row[4]) if row[4] else None}
    return {"rsi": None, "rsi_signal": None, "macd_signal": None,
            "sma20_signal": None, "price": None}


def get_recent_articles(ticker: str) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (title) title, link, fetched_at
        FROM news WHERE ticker=%s
        ORDER BY title, fetched_at DESC
        LIMIT 30
    """, (ticker,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"title": r[0], "link": r[1], "fetched_at": r[2]} for r in rows]


def score_to_direction(score: float) -> int:
    """Convert sentiment score to directional vote: +1 bull, -1 bear, 0 neutral."""
    if score > 0.05:
        return 1
    if score < -0.05:
        return -1
    return 0


def tech_to_direction(tech: dict) -> int:
    """Convert technicals to directional vote."""
    if not tech:
        return 0
    bull = sum([
        tech.get("macd_signal") == "bullish",
        tech.get("sma20_signal") == "bullish",
        tech.get("rsi_signal") == "oversold",
    ])
    bear = sum([
        tech.get("macd_signal") == "bearish",
        tech.get("sma20_signal") == "bearish",
        tech.get("rsi_signal") == "overbought",
    ])
    if bull >= 2: return 1
    if bear >= 2: return -1
    return 0


def get_similarity_score(ticker: str) -> float:
    """Get latest similarity score from corpus (Layer 4.5). Returns 0.5 if not available."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT similarity_score FROM pair_signals
            WHERE ticker_a=%s OR ticker_b=%s
            ORDER BY created_at DESC LIMIT 1
        """, (ticker, ticker))
        row = cur.fetchone()
        cur.close(); conn.close()
        return float(row[0]) if row and row[0] else 0.5
    except Exception:
        cur.close(); conn.close()
        return 0.5


def generate_pair_signal(pair: dict) -> dict:
    ticker_a = pair["a"]
    ticker_b = pair["b"]
    week = get_week_number()

    # Gather data
    sent_a = get_sentiment(ticker_a)
    sent_b = get_sentiment(ticker_b)
    tech_a = get_technicals(ticker_a)
    tech_b = get_technicals(ticker_b)
    articles_a = get_recent_articles(ticker_a)
    articles_b = get_recent_articles(ticker_b)

    # Track source reputation
    for art in articles_a:
        domain = extract_domain(art.get("link", ""))
        upsert_source_reputation(domain, ticker_a, art["title"], sent_a["signal"], week)
    for art in articles_b:
        domain = extract_domain(art.get("link", ""))
        upsert_source_reputation(domain, ticker_b, art["title"], sent_b["signal"], week)

    # Directional votes for A (positive = A outperforms B)
    sent_vote_a = score_to_direction(sent_a["score"])
    sent_vote_b = score_to_direction(sent_b["score"])
    tech_vote_a = tech_to_direction(tech_a)
    tech_vote_b = tech_to_direction(tech_b)

    # Net vote: A bull votes vs B bull votes
    # If A is more bullish than B -> long_a
    net = (sent_vote_a - sent_vote_b) + (tech_vote_a - tech_vote_b)
    total_votes = len(articles_a) + len(articles_b)

    # Confidence = |net| / max possible votes (4)
    confidence = min(abs(net) / 4.0, 1.0)

    if net >= 2:
        signal = "long_a"
    elif net <= -2:
        signal = "long_b"
    else:
        signal = "neutral"

    # Similarity score from Layer 4.5 (0.5 until corpus is built)
    sim_score = get_similarity_score(ticker_a)

    # High confidence = signal confirmed + similarity > 0.6
    high_confidence = confidence >= 0.5 and sim_score >= 0.6

    # Save signal
    signal_id = save_pair_signal(
        pair_name=pair["name"],
        ticker_a=ticker_a, ticker_b=ticker_b,
        signal=signal, confidence=confidence,
        sentiment_a=sent_a["score"], sentiment_b=sent_b["score"],
        rsi_a=tech_a.get("rsi"), rsi_b=tech_b.get("rsi"),
        similarity_score=sim_score,
        sources_used=total_votes
    )

    # Open paper trade if signal is not neutral
    paper_trade_id = None
    if signal != "neutral" and signal_id:
        ticker = ticker_a if signal == "long_a" else ticker_b
        price = tech_a.get("price") if signal == "long_a" else tech_b.get("price")
        paper_trade_id = save_paper_trade(signal_id, ticker, "long", price)

    return {
        "pair": pair["name"],
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "signal": signal,
        "confidence": round(confidence, 3),
        "net_votes": net,
        "sentiment_a": sent_a["score"],
        "sentiment_b": sent_b["score"],
        "rsi_a": tech_a.get("rsi"),
        "rsi_b": tech_b.get("rsi"),
        "similarity_score": sim_score,
        "high_confidence": high_confidence,
        "paper_trade_id": paper_trade_id,
        "signal_id": signal_id,
    }


def run_signal_generation():
    print(f"\n{'='*50}")
    print(f"Layer 4: Signal Generation at {datetime.utcnow().isoformat()}")
    print(f"{'='*50}")

    # Resolve pending paper trades (5 days old)
    resolved = resolve_pending_paper_trades()
    if resolved:
        print(f"  [Paper] Resolved {resolved} pending trades")

    # Prune worst sources after 25 weeks
    pruned = prune_worst_sources(min_weeks=25)
    if pruned:
        print(f"  [Prune] Removed {pruned} underperforming sources")

    results = []
    for pair in PAIRS:
        print(f"\n[->] {pair['name']}: {pair['a']} vs {pair['b']}")
        result = generate_pair_signal(pair)

        # Display
        arrow = "^A" if result["signal"] == "long_a" else ("^B" if result["signal"] == "long_b" else "--")
        hc = " *** HIGH CONFIDENCE ***" if result["high_confidence"] else ""
        print(f"    Signal: {result['signal'].upper()} [{arrow}]{hc}")
        print(f"    Confidence: {result['confidence']:.2f} | Net votes: {result['net_votes']:+d}")
        print(f"    Sentiment: {result['ticker_a']}={result['sentiment_a']:+.3f}  {result['ticker_b']}={result['sentiment_b']:+.3f}")
        if result['rsi_a']:
            print(f"    RSI: {result['ticker_a']}={result['rsi_a']:.1f}  {result['ticker_b']}={result['rsi_b'] or 'N/A'}")
        if result['paper_trade_id']:
            print(f"    [Paper] Trade opened id={result['paper_trade_id']}")

        results.append(result)

    return results


if __name__ == "__main__":
    from layer4.db_layer4 import init_layer4_tables
    init_layer4_tables()
    run_signal_generation()