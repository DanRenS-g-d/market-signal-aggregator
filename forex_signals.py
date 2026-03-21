"""
Forex Signal Translation Layer
Translates stock signals into correlated forex pair signals.
Correlations based on commodity exports and macro relationships.
"""
 
# Correlation map: ticker -> list of forex signals
# Format: (pair, direction, strength, reason)
# direction: "long" = buy base currency, "short" = sell base currency
# pair format: BASE/QUOTE (e.g. USD/COP means buy USD sell COP)
 
TICKER_FOREX_MAP = {
    # Oil tickers -> commodity currency correlations
    "EC": [
        ("USD/COP", "short", "strong", "Ecopetrol drives COP — oil up = COP stronger"),
        ("USD/MXN", "short", "medium", "Oil up = MXN stronger vs USD"),
        ("USD/CAD", "short", "medium", "Oil up = CAD stronger vs USD"),
    ],
    "GPRK": [
        ("USD/COP", "short", "medium", "Colombian oil E&P — oil up = COP stronger"),
        ("USD/MXN", "short", "medium", "Oil correlation"),
    ],
    "CNEC.CN": [
        ("USD/COP", "short", "medium", "Colombian gas — energy up = COP stronger"),
    ],
 
    # Colombian banking -> COP correlation
    "CIB": [
        ("USD/COP", "short", "medium", "Bancolombia profits = COP confidence"),
    ],
    "PFBCOLOM.CL": [
        ("USD/COP", "short", "weak", "Davivienda — Colombian financial sector"),
    ],
    "AVAL": [
        ("USD/COP", "short", "medium", "Grupo Aval — Colombian banking = COP strength"),
    ],
 
    # Colombian conglomerates
    "CEMARGOS.CL": [
        ("USD/COP", "short", "weak", "Colombian materials sector"),
    ],
    "GRUPSURA.CL": [
        ("USD/COP", "short", "weak", "Colombian holding — COP correlated"),
    ],
    "ISA.CL": [
        ("USD/COP", "short", "weak", "Colombian utilities"),
    ],
    "GEB.CL": [
        ("USD/COP", "short", "weak", "Colombian energy utilities"),
    ],
 
    # Tech/Manufacturing
    "TGLS": [
        ("USD/COP", "short", "weak", "Tecnoglass — Colombian manufacturer, USD revenues"),
    ],
}
 
STRENGTH_EMOJI = {
    "strong": "🔴🔴🔴",
    "medium": "🟡🟡",
    "weak":   "🟢",
}
 
STRENGTH_ORDER = {"strong": 3, "medium": 2, "weak": 1}
 
 
def get_forex_signals(signal_results: list) -> list:
    """
    Translate stock signals into forex signals.
    Returns list of forex recommendations ranked by strength.
    """
    forex_votes = {}  # pair -> {long: score, short: score, reasons: []}
 
    for result in signal_results:
        if result["signal"] == "neutral":
            continue
 
        # Determine which ticker is being longed
        if result["signal"] == "long_a":
            ticker = result["ticker_a"]
            direction_multiplier = 1
        else:
            ticker = result["ticker_b"]
            direction_multiplier = 1
 
        confidence = result["confidence"]
        correlations = TICKER_FOREX_MAP.get(ticker, [])
 
        for pair, direction, strength, reason in correlations:
            if pair not in forex_votes:
                forex_votes[pair] = {"long": 0.0, "short": 0.0, "reasons": [], "strength": "weak"}
 
            weight = STRENGTH_ORDER[strength] * confidence * direction_multiplier
 
            if direction == "short":
                forex_votes[pair]["short"] += weight
            else:
                forex_votes[pair]["long"] += weight
 
            forex_votes[pair]["reasons"].append(
                f"{ticker} → {direction} {pair} ({strength})"
            )
 
            # Update strength to highest seen
            if STRENGTH_ORDER[strength] > STRENGTH_ORDER[forex_votes[pair]["strength"]]:
                forex_votes[pair]["strength"] = strength
 
    # Build final signals
    forex_signals = []
    for pair, votes in forex_votes.items():
        net = votes["long"] - votes["short"]
        if abs(net) < 0.1:
            continue  # too weak to act on
 
        direction = "long" if net > 0 else "short"
        base, quote = pair.split("/")
 
        if direction == "long":
            action = f"BUY {base} / SELL {quote}"
        else:
            action = f"SELL {base} / BUY {quote}"
 
        forex_signals.append({
            "pair":      pair,
            "direction": direction,
            "action":    action,
            "strength":  votes["strength"],
            "score":     round(abs(net), 3),
            "reasons":   votes["reasons"][:2],  # top 2 reasons
        })
 
    # Sort by score descending
    forex_signals.sort(key=lambda x: x["score"], reverse=True)
    return forex_signals
 
 
def format_forex_for_telegram(forex_signals: list) -> str:
    if not forex_signals:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💱 <b>SEÑALES FOREX DERIVADAS</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Basadas en correlaciones con señales de acciones</i>")
 
    for sig in forex_signals:
        emoji = STRENGTH_EMOJI[sig["strength"]]
        lines.append("")
        lines.append(f"{emoji} <b>{sig['pair']}</b>")
        lines.append(f"Acción: {sig['action']}")
        lines.append(f"Correlación: {sig['strength'].upper()}")
        if sig["reasons"]:
            lines.append(f"Por: {sig['reasons'][0]}")
 
    lines.append("")
    lines.append("⚠️ <i>Forex tiene mayor riesgo. Usar con capital limitado.</i>")
 
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    # Test with sample signals
    test_signals = [
        {"signal": "long_a", "ticker_a": "EC", "ticker_b": "CNEC.CN",
         "pair": "Oil Integrated vs Gas", "confidence": 0.75, "high_confidence": False},
        {"signal": "long_a", "ticker_a": "AVAL", "ticker_b": "CIB",
         "pair": "Aval vs Bancolombia", "confidence": 0.75, "high_confidence": False},
    ]
    signals = get_forex_signals(test_signals)
    print(format_forex_for_telegram(signals))