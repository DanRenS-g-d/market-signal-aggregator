"""
Telegram notifications for Market Signal Aggregator.
Sends trade signals directly to Telegram chat.
"""
 
import os
import requests
 
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "8686403285:AAHLjXR0WDU4zsZaXvjpW7XlBjo4QV9uVMU")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8049206151")
 
STOP_LOSS_PCT   = 0.05
TAKE_PROFIT_PCT = 0.10
 
 
def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code == 200:
            print(f"    [Telegram] Sent successfully")
            return True
        else:
            print(f"    [Telegram] Failed {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        print(f"    [Telegram] Error: {e}")
        return False
 
 
def get_current_price(ticker: str) -> float:
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 4)
    except Exception:
        pass
    return 0.0
 
 
def get_allocation_pct(conf: int) -> int:
    """Return capital allocation % based on confidence."""
    if conf >= 75:
        return 30
    elif conf >= 50:
        return 15
    else:
        return 0
 
 
def build_telegram_message(sentiment_results: list, signal_results: list, resolved_trades: int = 0) -> str:
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
 
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
    high_conf   = [r for r in signal_results if r.get("high_confidence")]
 
    if not non_neutral and resolved_trades == 0:
        return None
 
    lines = []
    lines.append(f"📈 <b>Market Signal Aggregator</b>")
    lines.append(f"🕐 {now}")
    lines.append("")
 
    if high_conf:
        lines.append("🚨 <b>HIGH CONFIDENCE SIGNAL</b>")
        lines.append("")
 
    if non_neutral:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("<b>ÓRDENES A EJECUTAR</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
 
        for r in non_neutral:
            ticker = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
            price  = get_current_price(ticker)
            conf   = int(r["confidence"] * 100)
            hc     = " 🌟" if r.get("high_confidence") else ""
            alloc  = get_allocation_pct(conf)
 
            lines.append("")
            lines.append(f"📊 <b>COMPRAR {ticker}</b>{hc}")
            lines.append(f"Par: {r['pair']}")
            lines.append(f"Confianza: {conf}%")
            lines.append(f"💼 Asignar: <b>{alloc}% del capital disponible</b>")
 
            if price > 0:
                sl   = round(price * (1 - STOP_LOSS_PCT), 2)
                tp   = round(price * (1 + TAKE_PROFIT_PCT), 2)
                s100 = max(1, int(100 / price))
                s200 = max(1, int(200 / price))
                s500 = max(1, int(500 / price))
                lines.append(f"Precio: <b>${price}</b>")
                lines.append(f"✅ Take Profit: ${tp} (+10%)")
                lines.append(f"🛑 Stop Loss: ${sl} (-5%)")
                lines.append(f"📊 Shares: $100→{s100} | $200→{s200} | $500→{s500}")
                lines.append(f"📱 IBKR: busca <code>{ticker}</code> → Limit → GTC")
 
            # HRP allocation if available
            if r.get("hrp_alloc_pct"):
                lines.append(f"⚖️ HRP allocation: <b>{r['hrp_alloc_pct']}% of capital</b>")
            else:
                lines.append(f"⚠️ Precio no disponible — verificar en IBKR")
 
    if resolved_trades > 0:
        lines.append("")
        lines.append(f"✅ {resolved_trades} paper trade(s) resueltos hoy")
 
    lines.append("")
    lines.append("─────────────────────")
    lines.append("Próxima revisión en 6h")
 
    return "\n".join(lines)
 
 
def notify_telegram(sentiment_results: list, signal_results: list, resolved_trades: int = 0):
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
    if not non_neutral and resolved_trades == 0:
        print("    [Telegram] All neutral, no message sent.")
        return
 
    message = build_telegram_message(sentiment_results, signal_results, resolved_trades)
    if message:
        send_telegram(message)
 
 
def notify_telegram_with_forex(sentiment_results: list, signal_results: list,
                                resolved_trades: int = 0, forex_tech: dict = None,
                                vol_context: dict = None, regimes: dict = None,
                                marine_data: dict = None, macro_data: dict = None,
                                show_hrp: bool = True):
    """Extended notify with forex signals and technical confirmation."""
    from forex_signals import get_forex_signals, format_forex_for_telegram
    from forex_technicals import format_forex_technicals_for_telegram
 
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
    if not non_neutral and resolved_trades == 0:
        print("    [Telegram] All neutral, no message sent.")
        return
 
    message = build_telegram_message(sentiment_results, signal_results, resolved_trades)
    if not message:
        return
 
    # Add forex signals
    forex_signals = get_forex_signals(signal_results)
    if forex_signals:
        forex_text = format_forex_for_telegram(forex_signals)
        message = message + forex_text
 
        # Add technical confirmation if available
        if forex_tech:
            tech_text = format_forex_technicals_for_telegram(forex_tech, forex_signals)
            if tech_text:
                message = message + "\n" + tech_text
 
    # Add HRP allocation summary
    if show_hrp:
        from hrp_optimizer import format_hrp_for_telegram
        hrp_text = format_hrp_for_telegram(signal_results)
        if hrp_text:
            message = message + hrp_text
 
    # Add macro consumer signals
    if macro_data:
        from macro_consumer import format_macro_for_telegram
        macro_text = format_macro_for_telegram(macro_data)
        if macro_text:
            message = message + macro_text
 
    # Add marine traffic signals
    if marine_data:
        from marine_traffic import format_marine_for_telegram
        marine_text = format_marine_for_telegram(marine_data)
        if marine_text:
            message = message + marine_text
 
    # Add regime filter warnings
    if regimes:
        from regime_detector import format_regime_for_telegram
        regime_text = format_regime_for_telegram(regimes)
        if regime_text:
            message = message + regime_text
 
    # Add volatility context
    if vol_context:
        from volatility import format_volatility_for_telegram
        vol_text = format_volatility_for_telegram(vol_context)
        if vol_text:
            message = message + vol_text
 
    send_telegram(message)
 
 
if __name__ == "__main__":
    send_telegram("✅ Market Signal Aggregator conectado correctamente")