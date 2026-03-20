"""
Email notifications via SendGrid.
Sends actionable trade instructions after each pipeline run.
"""
 
import os
import requests
from datetime import datetime
 
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL       = os.environ.get("NOTIFY_FROM", "drengifosulbaran@gmail.com")
 
TO_EMAILS = [
    "drengifosulbaran@gmail.com",
    "isissulbaran@gmail.com",
    "scarlettsrengifos@gmail.com",
    "krengifosulbaran8s@gmail.com",
]
 
STOP_LOSS_PCT   = 0.05   # 5%
TAKE_PROFIT_PCT = 0.10   # 10%
KELLY_FRACTION  = 0.15
 
 
def send_email(subject: str, html_body: str) -> bool:
    if not SENDGRID_API_KEY:
        print("    [Email] SENDGRID_API_KEY not set, skipping.")
        return False
 
    payload = {
        "personalizations": [{"to": [{"email": e} for e in TO_EMAILS]}],
        "from": {"email": FROM_EMAIL, "name": "Market Signal Aggregator"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }
 
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
 
    if r.status_code in (200, 202):
        print(f"    [Email] Sent to {len(TO_EMAILS)} recipients")
        return True
    else:
        print(f"    [Email] Failed {r.status_code}: {r.text[:200]}")
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
 
 
def build_email(sentiment_results: list, signal_results: list, resolved_trades: int = 0) -> tuple:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
 
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
    high_conf   = [r for r in signal_results if r.get("high_confidence")]
 
    if high_conf:
        subject = f"🚨 HIGH CONFIDENCE SIGNAL | {now}"
    elif non_neutral:
        subject = f"📊 {len(non_neutral)} Trade Signal(s) | {now}"
    else:
        subject = f"📋 All Neutral | {now}"
 
    # ── Build trade instruction cards ─────────────────────────────
    trade_cards = ""
    for r in non_neutral:
        ticker    = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
        price     = get_current_price(ticker)
        conf_pct  = int(r["confidence"] * 100)
        hc_badge  = '<span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:4px;font-size:11px;margin-left:6px">HIGH CONF</span>' if r.get("high_confidence") else ""
 
        if price > 0:
            stop_loss    = round(price * (1 - STOP_LOSS_PCT), 2)
            take_profit  = round(price * (1 + TAKE_PROFIT_PCT), 2)
            price_str    = f"${price:.2f}"
            sl_str       = f"${stop_loss:.2f} (-{int(STOP_LOSS_PCT*100)}%)"
            tp_str       = f"${take_profit:.2f} (+{int(TAKE_PROFIT_PCT*100)}%)"
            shares_500   = max(1, int(500 / price))
            shares_200   = max(1, int(200 / price))
            shares_100   = max(1, int(100 / price))
        else:
            price_str   = "ver broker"
            sl_str      = f"-{int(STOP_LOSS_PCT*100)}% del precio de entrada"
            tp_str      = f"+{int(TAKE_PROFIT_PCT*100)}% del precio de entrada"
            shares_500  = "~"
            shares_200  = "~"
            shares_100  = "~"
 
        border_color = "#16a34a" if not r.get("high_confidence") else "#f59e0b"
 
        trade_cards += f"""
        <div style="border:2px solid {border_color};border-radius:8px;padding:16px;margin:12px 0;background:white;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <span style="font-size:20px;font-weight:500;">
                    📈 COMPRAR {ticker} (NYSE)
                    {hc_badge}
                </span>
                <span style="background:#16a34a;color:white;padding:4px 12px;border-radius:4px;font-size:13px;">{conf_pct}% confianza</span>
            </div>
 
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr style="background:#f9fafb;">
                    <td style="padding:8px 12px;font-weight:500;width:40%;">Par analizado</td>
                    <td style="padding:8px 12px;">{r['pair']}</td>
                </tr>
                <tr>
                    <td style="padding:8px 12px;font-weight:500;">Ticker</td>
                    <td style="padding:8px 12px;font-family:monospace;font-size:16px;font-weight:bold;">{ticker}</td>
                </tr>
                <tr style="background:#f9fafb;">
                    <td style="padding:8px 12px;font-weight:500;">Precio actual</td>
                    <td style="padding:8px 12px;">{price_str}</td>
                </tr>
                <tr>
                    <td style="padding:8px 12px;font-weight:500;color:#16a34a;">Take Profit</td>
                    <td style="padding:8px 12px;color:#16a34a;font-weight:500;">{tp_str}</td>
                </tr>
                <tr style="background:#f9fafb;">
                    <td style="padding:8px 12px;font-weight:500;color:#dc2626;">Stop Loss</td>
                    <td style="padding:8px 12px;color:#dc2626;font-weight:500;">{sl_str}</td>
                </tr>
            </table>
 
            <div style="margin-top:12px;background:#f0fdf4;border-radius:6px;padding:12px;">
                <p style="margin:0 0 6px;font-weight:500;font-size:13px;">💰 Cuántas acciones comprar:</p>
                <p style="margin:2px 0;font-size:13px;">Con $100 USD → <strong>{shares_100} acciones</strong></p>
                <p style="margin:2px 0;font-size:13px;">Con $200 USD → <strong>{shares_200} acciones</strong></p>
                <p style="margin:2px 0;font-size:13px;">Con $500 USD → <strong>{shares_500} acciones</strong></p>
            </div>
 
            <div style="margin-top:10px;background:#fffbeb;border-radius:6px;padding:10px;font-size:12px;color:#92400e;">
                <strong>Cómo ejecutar en IBKR:</strong> Busca <code>{ticker}</code> → Order Type: Limit → 
                Price: {price_str} → Quantity: [ver arriba] → Time in Force: GTC → Submit
            </div>
        </div>"""
 
    # ── Sentiment summary ──────────────────────────────────────────
    sentiment_rows = ""
    for r in sentiment_results:
        color = "#16a34a" if r["signal"] == "bullish" else ("#dc2626" if r["signal"] == "bearish" else "#6b7280")
        arrow = "▲" if r["signal"] == "bullish" else ("▼" if r["signal"] == "bearish" else "—")
        sentiment_rows += f"""
        <tr>
            <td style="padding:6px 12px;font-weight:500;">{r['ticker']}</td>
            <td style="padding:6px 12px;color:{color}">{arrow} {r['signal'].upper()}</td>
            <td style="padding:6px 12px;font-family:monospace">{r['score']:+.3f}</td>
            <td style="padding:6px 12px;color:#6b7280">{r.get('article_count', 0)} artículos</td>
        </tr>"""
 
    resolved_section = ""
    if resolved_trades > 0:
        resolved_section = f"""
        <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:12px 16px;margin:16px 0;border-radius:4px">
            ✅ <strong>{resolved_trades} paper trade(s)</strong> resueltos hoy.
        </div>"""
 
    neutral_note = ""
    if not non_neutral:
        neutral_note = """
        <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:12px 0;text-align:center;color:#6b7280;">
            No hay señales de trading esta ronda — todos los pares en NEUTRAL.<br>
            <small>No tomar posiciones. Próxima revisión en 6 horas.</small>
        </div>"""
 
    html = f"""
    <div style="font-family:sans-serif;max-width:620px;margin:0 auto;color:#1f2937;">
        <div style="background:#1e293b;color:white;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;font-size:18px;">📈 Market Signal Aggregator</h2>
            <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">{now}</p>
        </div>
 
        <div style="background:white;border:1px solid #e5e7eb;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px;">
            {resolved_section}
 
            <h3 style="margin:0 0 8px;font-size:14px;text-transform:uppercase;color:#6b7280;letter-spacing:0.05em;">
                Órdenes a Ejecutar
            </h3>
            {trade_cards}
            {neutral_note}
 
            <h3 style="margin:20px 0 8px;font-size:14px;text-transform:uppercase;color:#6b7280;letter-spacing:0.05em;">
                Sentimiento por Ticker
            </h3>
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:6px;">
                <thead>
                    <tr style="background:#f9fafb;font-size:12px;color:#6b7280;">
                        <th style="padding:8px 12px;text-align:left;">Ticker</th>
                        <th style="padding:8px 12px;text-align:left;">Señal</th>
                        <th style="padding:8px 12px;text-align:left;">Score</th>
                        <th style="padding:8px 12px;text-align:left;">Fuentes</th>
                    </tr>
                </thead>
                <tbody>{sentiment_rows}</tbody>
            </table>
 
            <p style="margin:20px 0 0;font-size:12px;color:#9ca3af;border-top:1px solid #f3f4f6;padding-top:12px;">
                market-signal-aggregator · Railway · próxima revisión en 6 horas
            </p>
        </div>
    </div>
    """
 
    return subject, html
 
 
def should_send(signal_results: list, resolved_trades: int) -> bool:
    has_signal   = any(r["signal"] != "neutral" for r in signal_results)
    has_high_conf = any(r.get("high_confidence") for r in signal_results)
    return has_signal or has_high_conf or resolved_trades > 0
 
 
def notify(sentiment_results: list, signal_results: list, resolved_trades: int = 0):
    if not should_send(signal_results, resolved_trades):
        print("    [Email] All neutral, no email sent.")
        return
    subject, html = build_email(sentiment_results, signal_results, resolved_trades)
    
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
    print(f"    [Email] Subject: {subject}")
    for r in non_neutral:
        ticker = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
        print(f"    [Email] Trade: BUY {ticker} | pair={r['pair']} | conf={r['confidence']:.2f}")
    
    send_email(subject, html)