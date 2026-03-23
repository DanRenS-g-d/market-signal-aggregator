"""
Regime Detector v2 — Correlation + Volatility + Stability
Implements:
1. Rolling Pearson correlation (30-60 day window)
2. ATR volatility percentile (only trade in 30-70th percentile)
3. Combined regime_score = corr_score * vol_score
4. Correlation stability (std dev of rolling corr — avoids false relationships)
Only signals with regime_score > SCORE_THRESHOLD pass through.
"""
 
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
 
# ── Thresholds ────────────────────────────────────────────────
CORR_MIN            = 0.50   # below → no trade
CORR_MAX            = 0.95   # above → no divergence
VOL_PERCENTILE_LOW  = 30     # below 30th percentile → too quiet
VOL_PERCENTILE_HIGH = 70     # above 70th percentile → too volatile
CORR_STABILITY_MAX  = 0.20   # std dev of rolling corr — above this = unstable
SCORE_THRESHOLD     = 0.40   # minimum regime_score to trade
LOOKBACK_DAYS       = 60     # main window
SHORT_WINDOW        = 30     # short window for stability check
 
 
def get_price_history(ticker: str, days: int = 65) -> list:
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
 
 
def pearson_correlation(a: list, b: list) -> float | None:
    n = min(len(a), len(b))
    if n < 10:
        return None
    a, b = a[-n:], b[-n:]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num    = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a  = sum((x - mean_a) ** 2 for x in a) ** 0.5
    den_b  = sum((x - mean_b) ** 2 for x in b) ** 0.5
    if den_a == 0 or den_b == 0:
        return None
    return round(num / (den_a * den_b), 4)
 
 
def rolling_correlations(a: list, b: list, window: int = 20) -> list:
    """Compute rolling correlations to measure stability."""
    results = []
    n = min(len(a), len(b))
    for i in range(window, n + 1):
        c = pearson_correlation(a[i-window:i], b[i-window:i])
        if c is not None:
            results.append(c)
    return results
 
 
def correlation_stability(roll_corrs: list) -> float | None:
    """Std dev of rolling correlations — lower = more stable."""
    if len(roll_corrs) < 5:
        return None
    mean = sum(roll_corrs) / len(roll_corrs)
    variance = sum((c - mean) ** 2 for c in roll_corrs) / len(roll_corrs)
    return round(math.sqrt(variance), 4)
 
 
def atr_ratio(prices: list, window: int = 14) -> float | None:
    """Average daily range / price — normalized ATR."""
    n = min(len(prices), window + 1)
    if n < 5:
        return None
    recent = prices[-n:]
    ranges = [abs(recent[i] - recent[i-1]) / recent[i-1]
              for i in range(1, len(recent)) if recent[i-1] > 0]
    if not ranges:
        return None
    return round(sum(ranges) / len(ranges), 6)
 
 
def percentile_rank(value: float, series: list) -> float:
    """Where does this value fall in the series? Returns 0-100."""
    if not series or value is None:
        return 50.0
    below = sum(1 for x in series if x <= value)
    return round(below / len(series) * 100, 1)
 
 
def compute_regime_score(corr: float, corr_stability: float,
                          vol_pct: float) -> tuple[float, str]:
    """
    regime_score = corr_score * vol_score
    Both scores are 0-1. Final score is 0-1.
    Returns (score, reason).
    """
    reasons = []
 
    # ── Correlation score ─────────────────────────────────────
    if corr is None:
        return 0.0, "no correlation data"
 
    if corr < CORR_MIN:
        return 0.0, f"corr {corr:.2f} < {CORR_MIN} — decorrelated"
    if corr > CORR_MAX:
        return 0.0, f"corr {corr:.2f} > {CORR_MAX} — overcorrelated"
 
    # Scale correlation: 0.5 → 0.0, 0.75 → 0.5, 0.95 → 1.0
    corr_score = (corr - CORR_MIN) / (CORR_MAX - CORR_MIN)
    reasons.append(f"corr={corr:.2f}")
 
    # ── Stability penalty ─────────────────────────────────────
    if corr_stability is not None:
        if corr_stability > CORR_STABILITY_MAX:
            stability_penalty = 1 - (corr_stability / 0.40)
            stability_penalty = max(0.2, stability_penalty)
            corr_score *= stability_penalty
            reasons.append(f"unstable(σ={corr_stability:.2f})")
        else:
            reasons.append(f"stable(σ={corr_stability:.2f})")
 
    # ── Volatility score ──────────────────────────────────────
    if vol_pct is None:
        vol_score = 0.5  # neutral if no data
        reasons.append("vol=unknown")
    elif vol_pct < VOL_PERCENTILE_LOW:
        return 0.0, f"vol too low (p{vol_pct:.0f}) — no movement"
    elif vol_pct > VOL_PERCENTILE_HIGH:
        return 0.0, f"vol too high (p{vol_pct:.0f}) — correlations break"
    else:
        # Peak vol score at 50th percentile, tapering at edges
        center = (VOL_PERCENTILE_LOW + VOL_PERCENTILE_HIGH) / 2
        dist   = abs(vol_pct - center) / (center - VOL_PERCENTILE_LOW)
        vol_score = max(0.1, 1.0 - dist * 0.5)
        reasons.append(f"vol=p{vol_pct:.0f}")
 
    regime_score = round(corr_score * vol_score, 3)
    return regime_score, " | ".join(reasons)
 
 
def init_regime_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pair_regimes (
            pair_name       VARCHAR(100) PRIMARY KEY,
            correlation     DECIMAL(6,4),
            corr_stability  DECIMAL(6,4),
            atr_avg         DECIMAL(8,6),
            vol_percentile  DECIMAL(5,1),
            regime_score    DECIMAL(5,3),
            regime          VARCHAR(20),
            conf_multiplier DECIMAL(4,2),
            reason          TEXT,
            updated_at      TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit(); cur.close(); conn.close()
 
 
def save_regime(pair_name: str, corr: float, stability: float,
                atr: float, vol_pct: float, score: float,
                regime: str, multiplier: float, reason: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO pair_regimes
            (pair_name, correlation, corr_stability, atr_avg, vol_percentile,
             regime_score, regime, conf_multiplier, reason, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (pair_name) DO UPDATE SET
            correlation     = EXCLUDED.correlation,
            corr_stability  = EXCLUDED.corr_stability,
            atr_avg         = EXCLUDED.atr_avg,
            vol_percentile  = EXCLUDED.vol_percentile,
            regime_score    = EXCLUDED.regime_score,
            regime          = EXCLUDED.regime,
            conf_multiplier = EXCLUDED.conf_multiplier,
            reason          = EXCLUDED.reason,
            updated_at      = NOW()
    """, (pair_name, corr, stability, atr, vol_pct, score,
          regime, multiplier, reason))
    conn.commit(); cur.close(); conn.close()
 
 
def evaluate_pair_regime(pair: dict) -> dict:
    ticker_a  = pair["a"]
    ticker_b  = pair["b"]
    pair_name = pair["name"]
 
    prices_a = get_price_history(ticker_a, 65)
    prices_b = get_price_history(ticker_b, 65)
 
    if len(prices_a) < 15 or len(prices_b) < 15:
        save_regime(pair_name, None, None, None, None, 0.0,
                    "no_data", 0.0, "insufficient price data")
        return {"pair": pair_name, "regime": "no_data",
                "regime_score": 0.0, "multiplier": 0.0,
                "reason": "insufficient price data"}
 
    # Main correlation
    corr = pearson_correlation(prices_a, prices_b)
 
    # Stability of correlation (rolling 20-day windows)
    roll_corrs = rolling_correlations(prices_a, prices_b, window=20)
    stability  = correlation_stability(roll_corrs)
 
    # ATR for both tickers
    atr_a = atr_ratio(prices_a)
    atr_b = atr_ratio(prices_b)
    avg_atr = (atr_a + atr_b) / 2 if atr_a and atr_b else None
 
    # Historical ATR distribution for percentile
    atr_history_a = [atr_ratio(prices_a[:i]) for i in range(15, len(prices_a))]
    atr_history_b = [atr_ratio(prices_b[:i]) for i in range(15, len(prices_b))]
    atr_history   = [x for x in atr_history_a + atr_history_b if x]
    vol_pct       = percentile_rank(avg_atr, atr_history) if atr_history else None
 
    # Compute regime score
    score, reason = compute_regime_score(corr, stability, vol_pct)
 
    # Regime label and confidence multiplier
    if score == 0.0:
        regime     = "skip"
        multiplier = 0.0
    elif score >= 0.70:
        regime     = "strong"
        multiplier = 1.0
    elif score >= SCORE_THRESHOLD:
        regime     = "moderate"
        multiplier = round(score, 2)
    else:
        regime     = "weak"
        multiplier = 0.0
 
    save_regime(pair_name, corr, stability, avg_atr, vol_pct,
                score, regime, multiplier, reason)
 
    return {
        "pair":         pair_name,
        "regime":       regime,
        "regime_score": score,
        "multiplier":   multiplier,
        "corr":         corr,
        "stability":    stability,
        "vol_pct":      vol_pct,
        "reason":       reason,
    }
 
 
def run_regime_detector(pairs: list) -> dict:
    init_regime_table()
    print(f"\n[Regime Detector] Evaluating {len(pairs)} pairs...")
    results = {}
    for pair in pairs:
        try:
            result = evaluate_pair_regime(pair)
            results[pair["name"]] = result
            emoji = "✅" if result["regime"] == "strong" else \
                    ("🟡" if result["regime"] == "moderate" else "❌")
            print(f"    {emoji} {pair['name']:32} score={result['regime_score']:.2f} "
                  f"corr={result.get('corr') or 'N/A'} | {result['reason'][:40]}")
        except Exception as e:
            print(f"    [Regime] Error {pair['name']}: {e}")
            results[pair["name"]] = {"regime": "error", "multiplier": 1.0, "regime_score": 0.5}
    tradeable = sum(1 for v in results.values() if v.get("multiplier", 0) > 0)
    print(f"    [Regime] {tradeable}/{len(pairs)} pairs in tradeable regime")
    return results
 
 
def apply_regime_to_signals(signal_results: list, regimes: dict) -> list:
    adjusted = []
    for signal in signal_results:
        pair_name  = signal["pair"]
        regime     = regimes.get(pair_name, {})
        multiplier = regime.get("multiplier", 1.0)
 
        if multiplier == 0.0:
            print(f"    [Regime] ❌ SKIP {pair_name} — {regime.get('reason','')[:50]}")
            continue
 
        adj = dict(signal)
        orig_conf = signal["confidence"]
        adj["confidence"]        = round(orig_conf * multiplier, 3)
        adj["regime_multiplier"] = multiplier
        adj["regime_score"]      = regime.get("regime_score", 1.0)
 
        if multiplier < 1.0:
            print(f"    [Regime] ⚠️ REDUCE {pair_name} "
                  f"conf {orig_conf:.2f}→{adj['confidence']:.2f}")
        adjusted.append(adj)
    return adjusted
 
 
def format_regime_for_telegram(regimes: dict) -> str:
    skipped  = [(k, v) for k, v in regimes.items() if v.get("multiplier") == 0.0
                and v.get("regime") not in ("no_data", "error")]
    reduced  = [(k, v) for k, v in regimes.items()
                if 0.0 < v.get("multiplier", 1.0) < 1.0]
 
    if not skipped and not reduced:
        return ""
 
    lines = ["", "━━━━━━━━━━━━━━━━━━━━",
             "🔬 <b>FILTRO DE RÉGIMEN</b>",
             "━━━━━━━━━━━━━━━━━━━━"]
 
    for pair, data in skipped[:4]:
        lines.append(f"❌ {pair}: {data.get('reason','')[:55]}")
 
    for pair, data in reduced[:3]:
        lines.append(f"⚠️ {pair}: score={data.get('regime_score',0):.2f} "
                     f"× conf → {data.get('reason','')[:40]}")
 
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    from config import PAIRS
    regimes = run_regime_detector(PAIRS[:5])  # test first 5