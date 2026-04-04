"""
Macro Consumer Patterns Module
Uses FRED API to track consumption patterns and compare with historical cycles.
Logic:
- Download 30+ years of macro series
- Calculate where we are in the cycle (percentile vs same month historically)
- Detect which historical period current conditions resemble most
- Generate bullish/bearish signals per ticker based on macro regime
"""
 
import os, sys, requests, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
FRED_API_KEY = os.environ.get("FRED_API_KEY", "8c0c21e76a07f492162c1a4ec2bf73eb")
FRED_BASE    = "https://api.stlouisfed.org/fred/series/observations"
 
# ── FRED Series definitions ───────────────────────────────────
SERIES = {
    # Consumer spending
    "RSXFS":    {"name": "Retail Sales",              "tickers": ["EWZ", "EWW", "EWY"], "direction": "positive"},
    "PCE":      {"name": "Personal Consumption",      "tickers": ["EWZ", "EWW", "EWY", "EWT"], "direction": "positive"},
    "UMCSENT":  {"name": "Consumer Sentiment",        "tickers": ["EWZ", "EWW", "EWY"], "direction": "positive"},
 
    # Energy
    "GASDESW":  {"name": "Gas Station Sales",         "tickers": ["EC", "GPRK"], "direction": "positive"},
    "DCOILWTICO":{"name": "WTI Oil Price",            "tickers": ["EC", "GPRK"], "direction": "positive"},
 
    # Industrial
    "INDPRO":   {"name": "Industrial Production",     "tickers": ["EWY", "EWT", "EWZ"], "direction": "positive"},
    "AMTMNO":   {"name": "Manufacturing Orders",      "tickers": ["EWY", "EWT"], "direction": "positive"},
 
    # Dollar & rates
    "DTWEXBGS": {"name": "Dollar Index",              "tickers": ["EC", "EWZ", "EWW"], "direction": "negative"},
    "FEDFUNDS":  {"name": "Fed Funds Rate",           "tickers": ["CIB", "AVAL", "TLT", "IEF"], "direction": "negative"},
    "DGS10":    {"name": "10yr Treasury Yield",       "tickers": ["TLT", "IEF"], "direction": "negative"},
 
    # Inflation & employment
    "CPIAUCSL": {"name": "CPI Inflation",             "tickers": ["CIB", "AVAL", "TLT"], "direction": "negative"},
    "UNRATE":   {"name": "Unemployment Rate",         "tickers": ["EWZ", "EWW", "TLT"], "direction": "negative"},
}
 
PERCENTILE_BULLISH  = 65   # above 65th percentile = bullish
PERCENTILE_BEARISH  = 35   # below 35th percentile = bearish
MIN_HISTORY_YEARS   = 5    # minimum years of data needed
 
 
def fetch_fred_series(series_id: str, years: int = 30) -> list:
    """Fetch historical observations from FRED API."""
    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    try:
        r = requests.get(FRED_BASE, params={
            "series_id":       series_id,
            "api_key":         FRED_API_KEY,
            "file_type":       "json",
            "observation_start": start,
            "sort_order":      "asc",
        }, timeout=15)
 
        if r.status_code != 200:
            return []
 
        observations = r.json().get("observations", [])
        result = []
        for obs in observations:
            try:
                val = float(obs["value"])
                result.append({
                    "date":  obs["date"],
                    "month": obs["date"][5:7],
                    "year":  obs["date"][:4],
                    "value": val,
                })
            except (ValueError, KeyError):
                continue  # skip "." missing values
 
        return result
 
    except Exception as e:
        print(f"    [FRED] Error fetching {series_id}: {e}")
        return []
 
 
def calculate_seasonal_percentile(observations: list) -> dict:
    """
    Calculate where current value sits vs same month in history.
    Removes seasonality by comparing Jan vs Jan, Feb vs Feb, etc.
    Returns percentile 0-100 for current month.
    """
    if not observations or len(observations) < 12:
        return {"percentile": 50, "current": None, "mean": None}
 
    current     = observations[-1]
    cur_month   = current["month"]
    cur_value   = current["value"]
 
    # Get all historical values for same month
    same_month  = [o["value"] for o in observations[:-1]
                   if o["month"] == cur_month]
 
    if len(same_month) < MIN_HISTORY_YEARS:
        return {"percentile": 50, "current": cur_value, "mean": None}
 
    below       = sum(1 for v in same_month if v <= cur_value)
    percentile  = round(below / len(same_month) * 100, 1)
    mean        = round(sum(same_month) / len(same_month), 2)
    yoy_change  = None
 
    # Year-over-year change
    last_year   = [o for o in observations if o["month"] == cur_month
                   and int(o["year"]) == int(current["year"]) - 1]
    if last_year:
        prev_val    = last_year[-1]["value"]
        yoy_change  = round((cur_value - prev_val) / abs(prev_val) * 100, 2) if prev_val != 0 else 0
 
    return {
        "percentile":   percentile,
        "current":      cur_value,
        "mean":         mean,
        "yoy_change":   yoy_change,
        "n_history":    len(same_month),
    }
 
 
def find_similar_historical_period(observations: list, lookback: int = 3) -> dict:
    """
    Find which historical period most resembles current conditions.
    Uses last 3 months of trend to find the closest match in history.
    """
    if len(observations) < lookback + 24:
        return {}
 
    # Current pattern: last 3 months normalized
    recent = [o["value"] for o in observations[-lookback:]]
    if not recent or recent[0] == 0:
        return {}
 
    # Normalize to % change from first value
    recent_norm = [(v - recent[0]) / abs(recent[0]) * 100 for v in recent]
 
    best_match  = None
    best_score  = float("inf")
    history_end = len(observations) - lookback - 12  # avoid recent period
 
    for i in range(lookback, history_end):
        window = [observations[i - lookback + j]["value"] for j in range(lookback)]
        if not window or window[0] == 0:
            continue
        window_norm = [(v - window[0]) / abs(window[0]) * 100 for v in window]
 
        # Euclidean distance
        score = sum((a - b) ** 2 for a, b in zip(recent_norm, window_norm)) ** 0.5
        if score < best_score:
            best_score  = score
            best_match  = observations[i]
 
    if not best_match:
        return {}
 
    # What happened 6 months after that historical match?
    match_idx = next((i for i, o in enumerate(observations)
                      if o["date"] == best_match["date"]), None)
    future_signal = "unknown"
    if match_idx and match_idx + 6 < len(observations):
        future_val    = observations[match_idx + 6]["value"]
        current_val   = observations[-1]["value"]
        future_signal = "bullish" if future_val > current_val else "bearish"
 
    return {
        "similar_period": best_match["date"][:7],
        "similarity_score": round(best_score, 2),
        "historical_outcome": future_signal,
    }
 
 
def generate_ticker_signals(series_results: dict) -> dict:
    """
    Aggregate all macro signals per ticker.
    """
    ticker_votes = {}
 
    for series_id, result in series_results.items():
        if not result.get("percentile_data"):
            continue
 
        series_info  = SERIES[series_id]
        tickers      = series_info["tickers"]
        direction    = series_info["direction"]
        percentile   = result["percentile_data"]["percentile"]
 
        # Raw signal from percentile
        if percentile >= PERCENTILE_BULLISH:
            raw_signal = "bullish"
        elif percentile <= PERCENTILE_BEARISH:
            raw_signal = "bearish"
        else:
            raw_signal = "neutral"
 
        # Flip if negative direction (e.g. dollar up = EM bearish)
        if direction == "negative":
            if raw_signal == "bullish":
                raw_signal = "bearish"
            elif raw_signal == "bearish":
                raw_signal = "bullish"
 
        # Add historical pattern confirmation
        hist = result.get("historical_match", {})
        hist_outcome = hist.get("historical_outcome", "unknown")
 
        for ticker in tickers:
            if ticker not in ticker_votes:
                ticker_votes[ticker] = {"bullish": 0, "bearish": 0, "neutral": 0,
                                        "series": []}
            ticker_votes[ticker][raw_signal] += 1
            if hist_outcome == raw_signal:
                ticker_votes[ticker][raw_signal] += 0.5  # bonus for historical confirmation
            ticker_votes[ticker]["series"].append({
                "series": series_id,
                "name":   series_info["name"],
                "signal": raw_signal,
                "pct":    percentile,
            })
 
    # Finalize signals
    final = {}
    for ticker, votes in ticker_votes.items():
        total   = votes["bullish"] + votes["bearish"] + votes["neutral"]
        if total == 0:
            continue
        if votes["bullish"] > votes["bearish"]:
            signal = "bullish"
            conf   = round(votes["bullish"] / total, 2)
        elif votes["bearish"] > votes["bullish"]:
            signal = "bearish"
            conf   = round(votes["bearish"] / total, 2)
        else:
            signal = "neutral"
            conf   = 0.0
 
        final[ticker] = {
            "signal":     signal,
            "confidence": min(conf, 0.75),  # cap at 0.75 — macro is slow
            "votes":      dict(votes),
        }
 
    return final
 
 
def run_macro_consumer() -> dict:
    """Main entry point — fetch all FRED series and generate signals."""
    print(f"\n[Macro Consumer] Fetching FRED data for {len(SERIES)} series...")
 
    series_results = {}
    for series_id, info in SERIES.items():
        observations = fetch_fred_series(series_id, years=30)
        if not observations:
            print(f"    [FRED] {series_id}: no data")
            continue
 
        percentile_data    = calculate_seasonal_percentile(observations)
        historical_match   = find_similar_historical_period(observations)
 
        series_results[series_id] = {
            "name":             info["name"],
            "percentile_data":  percentile_data,
            "historical_match": historical_match,
        }
 
        pct = percentile_data.get("percentile", 50)
        yoy = percentile_data.get("yoy_change")
        yoy_str = f" | YoY: {yoy:+.1f}%" if yoy is not None else ""
        hist_str = f" | Similar to {historical_match.get('similar_period','?')}" if historical_match else ""
        print(f"    [FRED] {series_id:12} {info['name']:25} p{pct:.0f}{yoy_str}{hist_str}")
 
    ticker_signals = generate_ticker_signals(series_results)
 
    print(f"\n    [Macro] Ticker signals:")
    for ticker, data in ticker_signals.items():
        print(f"    [Macro] {ticker:6} {data['signal']:8} conf={data['confidence']:.2f}")
 
    return {
        "series":  series_results,
        "tickers": ticker_signals,
    }
 
 
def format_macro_for_telegram(macro_data: dict) -> str:
    """Format macro signals for Telegram."""
    if not macro_data or not macro_data.get("tickers"):
        return ""
 
    significant = {k: v for k, v in macro_data["tickers"].items()
                   if v["signal"] != "neutral" and v["confidence"] >= 0.40}
    if not significant:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>MACRO CONSUMER CYCLE</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>FRED data — consumption patterns vs history</i>")
 
    for ticker, data in significant.items():
        arrow = "+" if data["signal"] == "bullish" else "-"
        conf  = int(data["confidence"] * 100)
        lines.append(f"\n{arrow} <b>{ticker}</b>: {data['signal'].upper()} ({conf}% conf)")
 
    # Show most notable series
    series = macro_data.get("series", {})
    notable = [(sid, s) for sid, s in series.items()
               if s.get("percentile_data", {}).get("percentile", 50) >= 75
               or s.get("percentile_data", {}).get("percentile", 50) <= 25]
 
    if notable:
        lines.append("")
        lines.append("<b>Notable macro readings:</b>")
        for sid, s in notable[:4]:
            pct = s["percentile_data"]["percentile"]
            flag = "high" if pct >= 75 else "low"
            lines.append(f"  {s['name']}: p{pct:.0f} ({flag})")
 
    lines.append("")
    lines.append("<i>Source: Federal Reserve FRED API</i>")
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    result = run_macro_consumer()
    print(format_macro_for_telegram(result))