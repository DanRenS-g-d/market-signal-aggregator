"""
Forex Signal Translation Layer
Translates stock/ETF signals into correlated forex pair signals.
"""
 
TICKER_FOREX_MAP = {
    # Colombia oil -> commodity currencies
    "EC": [
        ("USD/COP", "short", "strong", "Ecopetrol — oil up = COP stronger"),
        ("USD/MXN", "short", "medium", "Oil up = MXN stronger"),
        ("USD/CAD", "short", "medium", "Oil up = CAD stronger"),
        ("USD/BRL", "short", "weak",   "Oil up = EM risk-on"),
    ],
    "GPRK": [
        ("USD/COP", "short", "medium", "Colombian E&P — oil up = COP stronger"),
        ("USD/MXN", "short", "weak",   "Oil correlation"),
        ("USD/CAD", "short", "weak",   "Oil correlation"),
    ],
    "CNEC.CN": [
        ("USD/COP", "short", "medium", "Colombian gas — energy up = COP stronger"),
    ],
 
    # Colombia banking -> COP
    "CIB": [
        ("USD/COP", "short", "medium", "Bancolombia — Colombian banking = COP strength"),
    ],
    "AVAL": [
        ("USD/COP", "short", "medium", "Grupo Aval — Colombian banking = COP strength"),
    ],
    "PFBCOLOM.CL": [
        ("USD/COP", "short", "weak",   "Davivienda — Colombian financial sector"),
    ],
    "CIBEST.CL": [
        ("USD/COP", "short", "weak",   "Bancolombia BVC — COP correlated"),
    ],
    "GRUPSURA.CL": [
        ("USD/COP", "short", "weak",   "Grupo Sura — Colombian holding"),
    ],
    "ISA.CL": [
        ("USD/COP", "short", "weak",   "Colombian utilities — COP correlated"),
    ],
    "GEB.CL": [
        ("USD/COP", "short", "weak",   "Colombian energy — COP correlated"),
    ],
    "CEMARGOS.CL": [
        ("USD/COP", "short", "weak",   "Colombian materials — COP correlated"),
    ],
    "TGLS": [
        ("USD/COP", "short", "weak",   "Tecnoglass — Colombian manufacturer"),
    ],
 
    # Latin America ETFs
    "EWZ": [
        ("USD/BRL", "short", "strong", "Brazil ETF — BRL direct correlation"),
        ("USD/COP", "short", "weak",   "EM risk-on spillover"),
        ("USD/MXN", "short", "weak",   "EM risk-on spillover"),
    ],
    "EWW": [
        ("USD/MXN", "short", "strong", "Mexico ETF — MXN direct correlation"),
        ("USD/BRL", "short", "weak",   "EM risk-on spillover"),
    ],
    "ECH": [
        ("USD/CLP", "short", "strong", "Chile ETF — CLP direct correlation"),
        ("USD/BRL", "short", "weak",   "Latam risk-on spillover"),
    ],
    "EPU": [
        ("USD/PEN", "short", "strong", "Peru ETF — PEN direct correlation"),
        ("USD/CLP", "short", "weak",   "Andean markets correlation"),
    ],
 
    # Africa ETFs
    "EZA": [
        ("USD/ZAR", "short", "strong", "South Africa ETF — ZAR direct correlation"),
    ],
    "NGE": [
        ("USD/NGN", "short", "medium", "Nigeria ETF — NGN correlation"),
        ("USD/ZAR", "short", "weak",   "African markets spillover"),
    ],
 
    # Southeast Asia ETFs
    "EWY": [
        ("USD/KRW", "short", "strong", "Korea ETF — KRW direct correlation"),
        ("USD/TWD", "short", "weak",   "Asian tech risk-on"),
    ],
    "EWT": [
        ("USD/TWD", "short", "strong", "Taiwan ETF — TWD direct correlation"),
        ("USD/KRW", "short", "weak",   "Asian tech risk-on"),
    ],
    "EIDO": [
        ("USD/IDR", "short", "strong", "Indonesia ETF — IDR direct correlation"),
        ("USD/MYR", "short", "weak",   "SE Asia risk-on"),
    ],
    "THD": [
        ("USD/THB", "short", "strong", "Thailand ETF — THB direct correlation"),
        ("USD/IDR", "short", "weak",   "SE Asia risk-on"),
    ],
}
 
# Most liquid pairs available in IBKR (flag for execution priority)
IBKR_LIQUID_PAIRS = {
    "USD/MXN", "USD/BRL", "USD/CAD",
    "USD/ZAR", "USD/KRW", "USD/TWD",
    "USD/COP", "USD/CLP", "USD/PEN",
}
 
STRENGTH_EMOJI = {
    "strong": "🔴🔴🔴",
    "medium": "🟡🟡",
    "weak":   "🟢",
}
 
STRENGTH_ORDER = {"strong": 3, "medium": 2, "weak": 1}
 
 
def get_forex_signals(signal_results: list) -> list:
    forex_votes = {}
 
    for result in signal_results:
        if result["signal"] == "neutral":
            continue
 
        ticker = result["ticker_a"] if result["signal"] == "long_a" else result["ticker_b"]
        confidence = result["confidence"]
        correlations = TICKER_FOREX_MAP.get(ticker, [])
 
        for pair, direction, strength, reason in correlations:
            if pair not in forex_votes:
                forex_votes[pair] = {"long": 0.0, "short": 0.0, "reasons": [], "strength": "weak"}
 
            weight = STRENGTH_ORDER[strength] * confidence
 
            if direction == "short":
                forex_votes[pair]["short"] += weight
            else:
                forex_votes[pair]["long"] += weight
 
            forex_votes[pair]["reasons"].append(f"{ticker} → {direction} {pair} ({strength})")
 
            if STRENGTH_ORDER[strength] > STRENGTH_ORDER[forex_votes[pair]["strength"]]:
                forex_votes[pair]["strength"] = strength
 
    forex_signals = []
    for pair, votes in forex_votes.items():
        net = votes["long"] - votes["short"]
        if abs(net) < 0.1:
            continue
 
        direction = "long" if net > 0 else "short"
        base, quote = pair.split("/")
        action = f"BUY {base} / SELL {quote}" if direction == "long" else f"SELL {base} / BUY {quote}"
        liquid = pair in IBKR_LIQUID_PAIRS
 
        forex_signals.append({
            "pair":      pair,
            "direction": direction,
            "action":    action,
            "strength":  votes["strength"],
            "score":     round(abs(net), 3),
            "reasons":   votes["reasons"][:2],
            "liquid":    liquid,
        })
 
    forex_signals.sort(key=lambda x: (x["score"], x["liquid"]), reverse=True)
    return forex_signals
 
 
def format_forex_for_telegram(forex_signals: list) -> str:
    if not forex_signals:
        return ""
 
    # Only show top 3 to keep message clean
    top = forex_signals[:3]
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💱 <b>SEÑALES FOREX DERIVADAS</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
 
    for sig in top:
        emoji  = STRENGTH_EMOJI[sig["strength"]]
        liquid = " ✅" if sig["liquid"] else " ⚠️ baja liquidez"
        lines.append("")
        lines.append(f"{emoji} <b>{sig['pair']}</b>{liquid}")
        lines.append(f"Acción: {sig['action']}")
        if sig["reasons"]:
            lines.append(f"Por: {sig['reasons'][0]}")
 
    lines.append("")
    lines.append("✅ = disponible en IBKR | ⚠️ = liquidez limitada")
    lines.append("⚠️ <i>Forex tiene mayor riesgo. Usar con capital limitado.</i>")
 
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    test_signals = [
        {"signal": "long_a", "ticker_a": "EWZ", "ticker_b": "EWW",
         "pair": "Brazil vs Mexico", "confidence": 0.75, "high_confidence": False},
        {"signal": "long_a", "ticker_a": "EC", "ticker_b": "GPRK",
         "pair": "Oil Integrated vs E&P", "confidence": 0.50, "high_confidence": False},
    ]
    signals = get_forex_signals(test_signals)
    print(format_forex_for_telegram(signals))