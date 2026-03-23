"""
Regime Detector — Correlation + Volatility
Determines if a pair is in a tradeable regime before generating signals.
 
Rules:
- Correlation < 0.3  → pair not moving together → SKIP
- Correlation > 0.95 → pair too correlated → no alpha possible → SKIP
- ATR/Price < 0.005  → too quiet, no movement → SKIP
- ATR/Price > 0.08   → too volatile, correlations break → REDUCE confidence
- Regime stored in DB, checked before each signal
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
 
# Thresholds
CORR_MIN      = 0.30   # below this → pair not correlated enough
CORR_MAX      = 0.95   # above this → no divergence possible
ATR_MIN       = 0.005  # below this → too quiet (0.5% daily range)
ATR_MAX       = 0.08   # above this → too volatile (8% daily range)
LOOKBACK_DAYS = 20     # rolling window for correlation and ATR
 
 
def get_price_history(ticker: str, days: int = 30) -> list:
    """Get recent closing prices from yfinance."""
    try:
        import yfinance as yf
        from config import YAHOO_MAP
        symbol = YAHOO_MAP.get(ticker, ticker)
        hist   = yf.Ticker(symbol).history(period=f"{days}d")
        if hist.empty:
            return []
        return hist["Close"].tolist()
    except Exception:
        return []
 
 
def calculate_correlation(prices_a: list, prices_b: list) -> float:
    """Pearson correlation between two price series."""
    n = min(len(prices_a), len(prices_b), LOOKBACK_DAYS)
    if n < 10:
        return None
 
    a = prices_a[-n:]
    b = prices_b[-n:]
 
    mean_a = sum(a) / n
    mean_b = sum(b) / n
 
    num   = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a = sum((x - mean_a) ** 2 for x in a) ** 0.5
    den_b = sum((x - mean_b) ** 2 for x in b) ** 0.5
 
    if den_a == 0 or den_b == 0:
        return None
 
    return round(num / (den_a * den_b), 4)
 
 
def calculate_atr_ratio(prices: list) -> float:
    """
    Normalized ATR: average daily range / price.
    Measures how much the ticker moves relative to its price.
    """
    n = min(len(prices), LOOKBACK_DAYS)
    if n < 5:
        return None
 
    recent = prices[-n:]
    ranges = [abs(recent[i] - recent[i-1]) / recent[i-1]
              for i in range(1, len(recent)) if recent[i-1] > 0]
 
    if not ranges:
        return None
 
    return round(sum(ranges) / len(ranges), 6)
 
 
def init_regime_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pair_regimes (
            pair_name     VARCHAR(100) PRIMARY KEY,
            correlation   DECIMAL(6,4),
            atr_a         DECIMAL(8,6),
            atr_b         DECIMAL(8,6),
            regime        VARCHAR(20),
            conf_multiplier DECIMAL(4,2),
            reason        TEXT,
            updated_at    TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit(); cur.close(); conn.close()
 
 
def save_regime(pair_name: str, corr: float, atr_a: float, atr_b: float,
                regime: str, multiplier: float, reason: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO pair_regimes
            (pair_name, correlation, atr_a, atr_b, regime, conf_multiplier, reason, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (pair_name) DO UPDATE SET
            correlation     = EXCLUDED.correlation,
            atr_a           = EXCLUDED.atr_a,
            atr_b           = EXCLUDED.atr_b,
            regime          = EXCLUDED.regime,
            conf_multiplier = EXCLUDED.conf_multiplier,
            reason          = EXCLUDED.reason,
            updated_at      = NOW()
    """, (pair_name, corr, atr_a, atr_b, regime, multiplier, reason))
    conn.commit(); cur.close(); conn.close()
 
 
def get_regime(pair_name: str) -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT regime, conf_multiplier, correlation, atr_a, atr_b, reason
            FROM pair_regimes WHERE pair_name = %s
        """, (pair_name,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return {
                "regime":     row[0],
                "multiplier": float(row[1]),
                "corr":       float(row[2]) if row[2] else None,
                "atr_a":      float(row[3]) if row[3] else None,
                "atr_b":      float(row[4]) if row[4] else None,
                "reason":     row[5],
            }
    except Exception:
        cur.close(); conn.close()
    return {"regime": "unknown", "multiplier": 1.0, "reason": "no data"}
 
 
def evaluate_pair_regime(pair: dict) -> dict:
    """
    Evaluate if a pair is in a tradeable regime.
    Returns regime classification and confidence multiplier.
    """
    ticker_a = pair["a"]
    ticker_b = pair["b"]
    pair_name = pair["name"]
 
    prices_a = get_price_history(ticker_a, 30)
    prices_b = get_price_history(ticker_b, 30)
 
    if not prices_a or not prices_b:
        return {
            "pair":       pair_name,
            "regime":     "no_data",
            "multiplier": 0.0,
            "reason":     "insufficient price data",
        }
 
    corr  = calculate_correlation(prices_a, prices_b)
    atr_a = calculate_atr_ratio(prices_a)
    atr_b = calculate_atr_ratio(prices_b)
    avg_atr = (atr_a + atr_b) / 2 if atr_a and atr_b else None
 
    # ── Regime classification ─────────────────────────────────
    regime     = "tradeable"
    multiplier = 1.0
    reason     = "normal regime"
 
    if corr is None or avg_atr is None:
        regime     = "no_data"
        multiplier = 0.0
        reason     = "cannot calculate correlation or ATR"
 
    elif corr < CORR_MIN:
        regime     = "decorrelated"
        multiplier = 0.0
        reason     = f"correlation {corr:.2f} < {CORR_MIN} — pair not moving together"
 
    elif corr > CORR_MAX:
        regime     = "overcorrelated"
        multiplier = 0.0
        reason     = f"correlation {corr:.2f} > {CORR_MAX} — no divergence possible"
 
    elif avg_atr < ATR_MIN:
        regime     = "too_quiet"
        multiplier = 0.0
        reason     = f"ATR {avg_atr:.4f} < {ATR_MIN} — insufficient movement"
 
    elif avg_atr > ATR_MAX:
        regime     = "too_volatile"
        multiplier = 0.6
        reason     = f"ATR {avg_atr:.4f} > {ATR_MAX} — high volatility, reduce size"
 
    elif corr < 0.5:
        regime     = "weak_correlation"
        multiplier = 0.7
        reason     = f"correlation {corr:.2f} — weak, trade with caution"
 
    else:
        regime     = "tradeable"
        multiplier = 1.0
        reason     = f"correlation {corr:.2f}, ATR {avg_atr:.4f} — good regime"
 
    result = {
        "pair":       pair_name,
        "regime":     regime,
        "multiplier": multiplier,
        "corr":       corr,
        "atr_a":      atr_a,
        "atr_b":      atr_b,
        "reason":     reason,
    }
 
    save_regime(pair_name, corr, atr_a, atr_b, regime, multiplier, reason)
    return result
 
 
def run_regime_detector(pairs: list) -> dict:
    """
    Evaluate all pairs and return regime map.
    Returns dict: pair_name -> regime info
    """
    init_regime_table()
    print(f"\n[Regime Detector] Evaluating {len(pairs)} pairs...")
 
    results = {}
    for pair in pairs:
        try:
            result = evaluate_pair_regime(pair)
            results[pair["name"]] = result
            emoji = "✅" if result["regime"] == "tradeable" else \
                    ("⚠️" if result["multiplier"] > 0 else "❌")
            print(f"    {emoji} {pair['name']:30} {result['regime']:15} "
                  f"corr={result.get('corr') or 'N/A'}")
        except Exception as e:
            print(f"    [Regime] Error for {pair['name']}: {e}")
            results[pair["name"]] = {"regime": "error", "multiplier": 1.0}
 
    return results
 
 
def apply_regime_to_signals(signal_results: list, regimes: dict) -> list:
    """
    Filter and adjust signals based on regime.
    - Skip signals from non-tradeable pairs
    - Reduce confidence for weak/volatile regimes
    """
    adjusted = []
    for signal in signal_results:
        pair_name = signal["pair"]
        regime    = regimes.get(pair_name, {})
        multiplier = regime.get("multiplier", 1.0)
 
        if multiplier == 0.0:
            print(f"    [Regime] SKIP {pair_name} — {regime.get('reason', 'bad regime')}")
            continue
 
        # Apply confidence multiplier
        adjusted_signal = dict(signal)
        original_conf   = signal["confidence"]
        adjusted_conf   = round(original_conf * multiplier, 3)
        adjusted_signal["confidence"]       = adjusted_conf
        adjusted_signal["regime_multiplier"] = multiplier
        adjusted_signal["regime"]            = regime.get("regime", "unknown")
 
        if multiplier < 1.0:
            print(f"    [Regime] REDUCE {pair_name} conf {original_conf:.2f}→{adjusted_conf:.2f} ({regime.get('reason','')})")
 
        adjusted.append(adjusted_signal)
 
    return adjusted
 
 
def format_regime_for_telegram(regimes: dict) -> str:
    """Show regime warnings in Telegram."""
    skipped  = [(k, v) for k, v in regimes.items() if v.get("multiplier") == 0.0]
    reduced  = [(k, v) for k, v in regimes.items() if 0.0 < v.get("multiplier", 1.0) < 1.0]
 
    if not skipped and not reduced:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔬 <b>FILTRO DE RÉGIMEN</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
 
    for pair, data in skipped[:3]:
        lines.append(f"❌ {pair}: {data.get('reason','')[:60]}")
 
    for pair, data in reduced[:3]:
        mult = data.get("multiplier", 1.0)
        lines.append(f"⚠️ {pair}: confianza ×{mult} — {data.get('reason','')[:50]}")
 
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    from config import PAIRS
    regimes = run_regime_detector(PAIRS)
    print("\n── Summary ──")
    tradeable = [k for k, v in regimes.items() if v["regime"] == "tradeable"]
    skipped   = [k for k, v in regimes.items() if v.get("multiplier") == 0.0]
    print(f"Tradeable: {len(tradeable)} | Skipped: {len(skipped)}")