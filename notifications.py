"""
Email notifications via SendGrid.
Sends a summary after each pipeline run.
Only sends if there's something worth reporting (non-neutral signals or paper trade updates).
"""

import os
import requests
from datetime import datetime

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL = os.environ.get("NOTIFY_FROM", "drengifosulbaran@gmail.com")
TO_EMAIL = os.environ.get("NOTIFY_TO", "drengifosulbaran@gmail.com")


def send_email(subject: str, html_body: str) -> bool:
    if not SENDGRID_API_KEY:
        print("    [Email] SENDGRID_API_KEY not set, skipping.")
        return False

    payload = {
        "personalizations": [{"to": [{"email": TO_EMAIL}]}],
        "from": {"email": FROM_EMAIL, "name": "Market Signal Aggregator"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }

    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )

    if r.status_code in (200, 202):
        print(f"    [Email] Sent to {TO_EMAIL}")
        return True
    else:
        print(f"    [Email] Failed {r.status_code}: {r.text[:200]}")
        return False


def build_email(sentiment_results: list, signal_results: list, resolved_trades: int = 0) -> tuple[str, str]:
    """Build subject and HTML body for the pipeline run email."""

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Determine if anything is worth reporting
    non_neutral_signals = [r for r in signal_results if r["signal"] != "neutral"]
    high_confidence = [r for r in signal_results if r.get("high_confidence")]
    bearish_tickers = [r for r in sentiment_results if r["signal"] == "bearish"]
    bullish_tickers = [r for r in sentiment_results if r["signal"] == "bullish"]

    # Subject
    if high_confidence:
        pair = high_confidence[0]["pair"]
        subject = f"🚨 HIGH CONFIDENCE SIGNAL — {pair} | {now}"
    elif non_neutral_signals:
        sig = non_neutral_signals[0]
        arrow = sig["ticker_a"] if sig["signal"] == "long_a" else sig["ticker_b"]
        subject = f"📊 LONG {arrow} signal | Market Aggregator {now}"
    else:
        subject = f"📋 Pipeline run — all neutral | {now}"

    # ── HTML body ─────────────────────────────────────────────
    def signal_badge(signal):
        colors = {"long_a": "#16a34a", "long_b": "#16a34a", "neutral": "#6b7280"}
        bg = colors.get(signal, "#6b7280")
        labels = {"long_a": "LONG A", "long_b": "LONG B", "neutral": "NEUTRAL"}
        label = labels.get(signal, signal.upper())
        return f'<span style="background:{bg};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{label}</span>'

    def sentiment_row(r):
        color = "#16a34a" if r["signal"] == "bullish" else ("#dc2626" if r["signal"] == "bearish" else "#6b7280")
        arrow = "▲" if r["signal"] == "bullish" else ("▼" if r["signal"] == "bearish" else "—")
        score = f"{r['score']:+.3f}"
        count = r.get("article_count", 0)
        return f"""
        <tr>
            <td style="padding:6px 12px;font-weight:bold">{r['ticker']}</td>
            <td style="padding:6px 12px;color:{color}">{arrow} {r['signal'].upper()}</td>
            <td style="padding:6px 12px;font-family:monospace">{score}</td>
            <td style="padding:6px 12px;color:#6b7280">{count} articles</td>
        </tr>"""

    def pair_row(r):
        if r["signal"] == "long_a":
            action = f"LONG {r['ticker_a']} / avoid {r['ticker_b']}"
            color = "#16a34a"
        elif r["signal"] == "long_b":
            action = f"LONG {r['ticker_b']} / avoid {r['ticker_a']}"
            color = "#16a34a"
        else:
            action = "No position"
            color = "#6b7280"

        hc_badge = ' <span style="background:#f59e0b;color:white;padding:1px 6px;border-radius:3px;font-size:11px">HIGH CONF</span>' if r.get("high_confidence") else ""
        conf_pct = int(r["confidence"] * 100)

        return f"""
        <tr style="border-bottom:1px solid #e5e7eb">
            <td style="padding:8px 12px;font-weight:bold">{r['pair']}</td>
            <td style="padding:8px 12px">{signal_badge(r['signal'])}{hc_badge}</td>
            <td style="padding:8px 12px;color:{color}">{action}</td>
            <td style="padding:8px 12px;color:#6b7280">{conf_pct}% conf</td>
        </tr>"""

    sentiment_rows = "".join(sentiment_row(r) for r in sentiment_results)
    pair_rows = "".join(pair_row(r) for r in signal_results)

    resolved_section = ""
    if resolved_trades > 0:
        resolved_section = f"""
        <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:12px 16px;margin:16px 0;border-radius:4px">
            ✅ <strong>{resolved_trades} paper trade(s)</strong> resolved today — check DB for P&L.
        </div>"""

    high_conf_banner = ""
    if high_confidence:
        hc = high_confidence[0]
        ticker = hc["ticker_a"] if hc["signal"] == "long_a" else hc["ticker_b"]
        high_conf_banner = f"""
        <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:16px;margin:16px 0;border-radius:4px;font-size:15px">
            🚨 <strong>HIGH CONFIDENCE SIGNAL:</strong> LONG {ticker} ({hc['pair']})<br>
            <span style="color:#6b7280;font-size:13px">Sentiment + technicals + similarity all agree</span>
        </div>"""

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#1f2937">

        <div style="background:#1e293b;color:white;padding:20px 24px;border-radius:8px 8px 0 0">
            <h2 style="margin:0;font-size:18px">📈 Market Signal Aggregator</h2>
            <p style="margin:4px 0 0;color:#94a3b8;font-size:13px">{now}</p>
        </div>

        <div style="background:white;border:1px solid #e5e7eb;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px">

            {high_conf_banner}
            {resolved_section}

            <h3 style="margin:16px 0 8px;font-size:14px;text-transform:uppercase;color:#6b7280;letter-spacing:0.05em">
                Pair Signals
            </h3>
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:6px">
                <thead>
                    <tr style="background:#f9fafb;font-size:12px;color:#6b7280">
                        <th style="padding:8px 12px;text-align:left">Pair</th>
                        <th style="padding:8px 12px;text-align:left">Signal</th>
                        <th style="padding:8px 12px;text-align:left">Action</th>
                        <th style="padding:8px 12px;text-align:left">Confidence</th>
                    </tr>
                </thead>
                <tbody>{pair_rows}</tbody>
            </table>

            <h3 style="margin:20px 0 8px;font-size:14px;text-transform:uppercase;color:#6b7280;letter-spacing:0.05em">
                Sentiment by Ticker
            </h3>
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:6px">
                <thead>
                    <tr style="background:#f9fafb;font-size:12px;color:#6b7280">
                        <th style="padding:8px 12px;text-align:left">Ticker</th>
                        <th style="padding:8px 12px;text-align:left">Signal</th>
                        <th style="padding:8px 12px;text-align:left">Score</th>
                        <th style="padding:8px 12px;text-align:left">Sources</th>
                    </tr>
                </thead>
                <tbody>{sentiment_rows}</tbody>
            </table>

            <p style="margin:20px 0 0;font-size:12px;color:#9ca3af;border-top:1px solid #f3f4f6;padding-top:12px">
                market-signal-aggregator · Railway · next run in 6 hours
            </p>
        </div>
    </div>
    """

    return subject, html


def should_send(signal_results: list, resolved_trades: int) -> bool:
    """Only send email if there's something actionable."""
    has_signal = any(r["signal"] != "neutral" for r in signal_results)
    has_high_conf = any(r.get("high_confidence") for r in signal_results)
    return has_signal or has_high_conf or resolved_trades > 0


def notify(sentiment_results: list, signal_results: list, resolved_trades: int = 0):
    """Main entry point — build and send email if warranted."""
    if not should_send(signal_results, resolved_trades):
        print("    [Email] All neutral, no email sent.")
        return

    subject, html = build_email(sentiment_results, signal_results, resolved_trades)
    send_email(subject, html)