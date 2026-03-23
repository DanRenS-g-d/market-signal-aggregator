"""
Volatility & Fear Module
Tracks VIX, put/call ratios, and volatility signals.
Uses yfinance — no API key needed.
 
When VIX is high → market is fearful → reduce EM exposure
When VIX is low → market is calm → normal exposure
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
VIX_FEAR_THRESHOLD    = 25   # VIX > 25 = elevated fear
VIX_EXTREME_THRESHOLD = 35   # VIX > 35 = extreme fear
VIX_CALM_THRESHOLD    = 15   # VIX < 15 = very calm / complacent
 
 
def get_vix() -> dict:
    """Fetch current VIX and interpret."""
    try:
        import yfinance as yf
        hist = yf.Ticker("^VIX").history(period="5d")
        if hist.empty:
            return {"vix": None, "signal": "unknown", "error": "no data"}
 
        vix = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else vix
        change = round(vix - prev, 2)
 
        if vix > VIX_EXTREME_THRESHOLD:
            signal = "extreme_fear"
            emoji  = "🔴🔴"
            advice = "Reducir exposición a EM significativamente"
        elif vix > VIX_FEAR_THRESHOLD:
            signal = "fear"
            emoji  = "🔴"
            advice = "Reducir exposición a EM, considerar bonos"
        elif vix < VIX_CALM_THRESHOLD:
            signal = "complacent"
            emoji  = "🟡"
            advice = "Mercado muy calmado — posible reversión"
        else:
            signal = "normal"
            emoji  = "🟢"
            advice = "Condiciones normales"
 
        return {
            "vix":     vix,
            "prev":    prev,
            "change":  change,
            "signal":  signal,
            "emoji":   emoji,
            "advice":  advice,
            "error":   None,
        }
    except Exception as e:
        return {"vix": None, "signal": "unknown", "error": str(e)}
 
 
def get_put_call_ratio(ticker: str) -> dict:
    """
    Estimate put/call ratio from options chain.
    High ratio (>1.5) = bearish sentiment
    Low ratio (<0.7) = bullish sentiment
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return {"ticker": ticker, "pcr": None, "signal": "no_options"}
 
        # Use nearest expiration
        exp = expirations[0]
        chain = stock.option_chain(exp)
 
        put_vol  = chain.puts["volume"].sum()
        call_vol = chain.calls["volume"].sum()
 
        if call_vol == 0:
            return {"ticker": ticker, "pcr": None, "signal": "no_volume"}
 
        pcr = round(put_vol / call_vol, 3)
 
        if pcr > 1.5:
            signal = "bearish"
        elif pcr < 0.7:
            signal = "bullish"
        else:
            signal = "neutral"
 
        return {
            "ticker":   ticker,
            "pcr":      pcr,
            "put_vol":  int(put_vol),
            "call_vol": int(call_vol),
            "signal":   signal,
            "exp":      exp,
        }
    except Exception as e:
        return {"ticker": ticker, "pcr": None, "signal": "error", "error": str(e)}
 
 
def get_volatility_context(signal_results: list) -> dict:
    """
    Get full volatility context for current market conditions.
    Returns VIX + put/call ratios for NYSE-listed tickers with options.
    """
    OPTIONS_TICKERS = ["EC", "CIB", "AVAL", "GPRK", "TGLS",
                       "EWZ", "EWW", "EWY", "EWT", "TLT", "IEF"]
 
    # Only check PCR for tickers with active signals
    active_tickers = set()
    for r in signal_results:
        if r["signal"] != "neutral":
            active_tickers.add(r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"])
 
    vix_data = get_vix()
    pcr_data = {}
 
    for ticker in OPTIONS_TICKERS:
        if ticker in active_tickers:
            pcr_data[ticker] = get_put_call_ratio(ticker)
 
    return {
        "vix":  vix_data,
        "pcr":  pcr_data,
    }
 
 
def adjust_confidence_for_volatility(confidence: float, vix_signal: str) -> float:
    """
    Reduce confidence when market is fearful.
    Institutional rule: high VIX = higher uncertainty = lower position size.
    """
    multipliers = {
        "extreme_fear": 0.5,   # cut confidence in half
        "fear":         0.75,  # reduce 25%
        "complacent":   0.9,   # slight reduction (overconfidence risk)
        "normal":       1.0,
        "unknown":      0.9,
    }
    return round(confidence * multipliers.get(vix_signal, 1.0), 3)
 
 
def format_volatility_for_telegram(vol_context: dict) -> str:
    """Format volatility data for Telegram message."""
    if not vol_context:
        return ""
 
    vix = vol_context.get("vix", {})
    pcr = vol_context.get("pcr", {})
 
    if vix.get("error") or not vix.get("vix"):
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>CONTEXTO DE VOLATILIDAD</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
 
    # VIX
    change_str = f"{vix['change']:+.2f}" if vix.get("change") else ""
    lines.append(f"{vix['emoji']} <b>VIX: {vix['vix']}</b> ({change_str} vs ayer)")
    lines.append(f"Estado: {vix['signal'].replace('_', ' ').upper()}")
    lines.append(f"💡 {vix['advice']}")
 
    # Put/Call ratios for active tickers
    pcr_signals = [(t, d) for t, d in pcr.items() if d.get("pcr") and d["signal"] != "neutral"]
    if pcr_signals:
        lines.append("")
        lines.append("<b>Put/Call ratios:</b>")
        for ticker, data in pcr_signals:
            emoji = "🐻" if data["signal"] == "bearish" else "🐂"
            lines.append(f"  {emoji} {ticker}: PCR={data['pcr']} ({data['signal']})")
 
    # Confidence adjustment warning
    if vix["signal"] in ("fear", "extreme_fear"):
        mult = 0.75 if vix["signal"] == "fear" else 0.5
        lines.append("")
        lines.append(f"⚠️ <b>Ajuste por volatilidad:</b> confianza ×{mult}")
        lines.append(f"   Reducir tamaño de posición {int((1-mult)*100)}%")
 
    return "\n".join(lines)
 
 
def run_volatility(signal_results: list) -> dict:
    """Main entry point."""
    print(f"\n[Volatility] Fetching VIX and options data...")
    try:
        ctx = get_volatility_context(signal_results)
        vix = ctx.get("vix", {})
        if vix.get("vix"):
            print(f"    [VIX] {vix['vix']} — {vix['signal']} {vix['emoji']}")
        return ctx
    except Exception as e:
        print(f"    [Volatility] Error (non-fatal): {e}")
        return {}
 
 
if __name__ == "__main__":
    ctx = get_volatility_context([])
    print(format_volatility_for_telegram(ctx))