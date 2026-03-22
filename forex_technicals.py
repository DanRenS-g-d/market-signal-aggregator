"""
Forex Technicals Module
Computes RSI, MACD, SMA20 for forex pairs using yfinance.
Reuses the same indicator logic as stock technicals.
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
 
# All forex pairs to track technicals for
FOREX_PAIRS = [
    "USD/COP", "USD/MXN", "USD/BRL", "USD/CAD",
    "USD/ZAR", "USD/KRW", "USD/TWD", "USD/CLP",
    "USD/PEN", "USD/IDR", "USD/THB", "USD/NGN",
]
 
# yfinance symbol format: USDMXN=X
def pair_to_yf_symbol(pair: str) -> str:
    return pair.replace("/", "") + "=X"
 
 
def _compute_indicators(pair: str, closes: list, volumes: list) -> dict:
    def calc_rsi(prices, period=14):
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(max(diff, 0)); losses.append(max(-diff, 0))
        if len(gains) < period: return 50.0
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        return round(100 - (100 / (1 + ag / al)), 2) if al else 100.0
 
    def ema(prices, span):
        k = 2 / (span + 1)
        r = [prices[0]]
        for p in prices[1:]: r.append(p * k + r[-1] * (1 - k))
        return r
 
    rsi        = calc_rsi(closes)
    ema12      = ema(closes, 12); ema26 = ema(closes, 26)
    macd       = [a - b for a, b in zip(ema12, ema26)]
    sig        = ema(macd, 9)
    macd_signal = "bullish" if macd[-1] > sig[-1] else "bearish"
    sma20      = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
    sma_signal = "bullish" if closes[-1] > sma20 else "bearish"
 
    return {
        "pair":        pair,
        "price":       round(closes[-1], 6),
        "rsi":         rsi,
        "rsi_signal":  "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
        "macd_signal": macd_signal,
        "sma20_signal": sma_signal,
        "error":       None,
    }
 
 
def compute_forex_technicals(pair: str) -> dict:
    try:
        import yfinance as yf
        symbol = pair_to_yf_symbol(pair)
        hist   = yf.Ticker(symbol).history(period="60d")
        if hist.empty:
            return {"pair": pair, "error": f"no data for {symbol}"}
        closes  = hist["Close"].tolist()
        volumes = hist["Volume"].tolist() if "Volume" in hist else [1] * len(closes)
        return _compute_indicators(pair, closes, volumes)
    except Exception as e:
        return {"pair": pair, "error": str(e)}
 
 
def init_forex_technicals_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forex_technicals (
            id           SERIAL PRIMARY KEY,
            pair         VARCHAR(20) NOT NULL,
            price        DECIMAL(12,6),
            rsi          DECIMAL(6,2),
            rsi_signal   VARCHAR(20),
            macd_signal  VARCHAR(20),
            sma20_signal VARCHAR(20),
            error        TEXT,
            fetched_at   TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit(); cur.close(); conn.close()
 
 
def forex_technicals_fetched_today(pair: str) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id FROM forex_technicals
        WHERE pair = %s AND fetched_at >= NOW() - INTERVAL '20 hours' AND error IS NULL
        LIMIT 1
    """, (pair,))
    result = cur.fetchone()
    cur.close(); conn.close()
    return result is not None
 
 
def save_forex_technicals(data: dict):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO forex_technicals
            (pair, price, rsi, rsi_signal, macd_signal, sma20_signal, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        data.get("pair"), data.get("price"), data.get("rsi"),
        data.get("rsi_signal"), data.get("macd_signal"),
        data.get("sma20_signal"), data.get("error"),
    ))
    conn.commit(); cur.close(); conn.close()
 
 
def get_latest_forex_technicals(pair: str) -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT price, rsi, rsi_signal, macd_signal, sma20_signal
        FROM forex_technicals
        WHERE pair = %s AND error IS NULL
        ORDER BY fetched_at DESC LIMIT 1
    """, (pair,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        return {
            "pair": pair,
            "price": float(row[0]) if row[0] else None,
            "rsi": float(row[1]) if row[1] else None,
            "rsi_signal": row[2],
            "macd_signal": row[3],
            "sma20_signal": row[4],
        }
    return {"pair": pair, "error": "no data"}
 
 
def run_forex_technicals() -> dict:
    """Fetch and save technicals for all forex pairs. Returns dict of results."""
    init_forex_technicals_table()
    results = {}
 
    for pair in FOREX_PAIRS:
        if forex_technicals_fetched_today(pair):
            results[pair] = get_latest_forex_technicals(pair)
            continue
 
        data = compute_forex_technicals(pair)
        save_forex_technicals(data)
 
        if data.get("error"):
            print(f"    [Forex Tech] {pair}: error — {data['error']}")
        else:
            signal = data['macd_signal']
            print(f"    [Forex Tech] {pair}: RSI={data['rsi']:.1f} MACD={signal} price={data['price']}")
 
        results[pair] = data
 
    return results
 
 
def format_forex_technicals_for_telegram(forex_tech: dict, forex_signals: list) -> str:
    """Add technical confirmation to forex signals."""
    if not forex_signals:
        return ""
 
    confirmations = []
    for sig in forex_signals[:3]:
        pair = sig["pair"]
        tech = forex_tech.get(pair, {})
        if tech.get("error"):
            continue
 
        rsi        = tech.get("rsi", 50)
        macd       = tech.get("macd_signal", "neutral")
        rsi_signal = tech.get("rsi_signal", "neutral")
 
        # Check if technicals confirm the forex signal
        direction = sig["direction"]
        confirms  = []
        conflicts = []
 
        if direction == "short":  # short USD = buy the other currency
            if macd == "bearish": confirms.append("MACD bearish ✓")
            else: conflicts.append("MACD bullish ✗")
            if rsi_signal == "overbought": confirms.append("RSI overbought ✓")
        else:
            if macd == "bullish": confirms.append("MACD bullish ✓")
            else: conflicts.append("MACD bearish ✗")
            if rsi_signal == "oversold": confirms.append("RSI oversold ✓")
 
        if confirms:
            confirmations.append(
                f"  {pair}: {' | '.join(confirms)}"
            )
 
    if not confirmations:
        return ""
 
    lines = ["", "<b>📊 Confirmación técnica forex:</b>"]
    lines.extend(confirmations)
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    results = run_forex_technicals()
    for pair, data in results.items():
        if not data.get("error"):
            print(f"{pair}: RSI={data.get('rsi', 'N/A')} MACD={data.get('macd_signal', 'N/A')}")