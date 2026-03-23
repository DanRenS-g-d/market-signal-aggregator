"""
Prediction Markets Integration
Fetches active markets from Polymarket and Kalshi,
detects divergences vs system signals, sends alerts to Telegram.
"""
 
import os
import requests
from datetime import datetime
 
DIVERGENCE_THRESHOLD = 0.20  # 20% gap triggers alert
 
# Keywords to search for relevant markets
# Bond ETFs — move opposite to stocks (hedging)
BOND_ETFS = ["TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG", "EMB", "BNDX"]
 
# All tickers in system
ALL_TICKERS = [
    # Colombia stocks
    "EC", "GPRK", "CNEC.CN", "CIB", "AVAL", "TGLS",
    "CIBEST.CL", "PFCIBEST.CL", "ISA.CL", "GEB.CL",
    "GRUPSURA.CL", "PFGRUPSURA.CL", "CEMARGOS.CL", "PFBCOLOM.CL",
    # Latam ETFs
    "EWZ", "EWW", "ECH", "EPU",
    # Africa ETFs
    "EZA", "NGE",
    # Asia ETFs
    "EWY", "EWT", "EIDO", "THD",
    # Bond ETFs
] + BOND_ETFS
 
SEARCH_KEYWORDS = {
    # ── Oil & Energy ──────────────────────────────────────────
    "oil":              ["EC", "GPRK"],
    "crude":            ["EC", "GPRK"],
    "petroleo":         ["EC", "GPRK"],
    "opec":             ["EC", "GPRK"],
    "brent":            ["EC", "GPRK"],
    "WTI":              ["EC", "GPRK"],
    "energy":           ["EC", "GPRK"],
    "commodities":      ["EC", "GPRK", "EWZ", "ECH"],
    "commodity":        ["EC", "GPRK"],
    "gold":             ["EZA", "ECH"],
    "silver":           ["ECH", "EPU"],
    "copper":           ["ECH", "EPU"],
 
    # ── Fed & Macro ────────────────────────────────────────────
    "fed":              ["CIB", "AVAL", "EWZ", "EWW", "TLT", "IEF"],
    "fomc":             ["CIB", "AVAL", "TLT", "IEF"],
    "powell":           ["CIB", "AVAL", "TLT"],
    "rate cut":         ["CIB", "AVAL", "EWZ", "TLT", "IEF"],
    "rate hike":        ["CIB", "AVAL", "TLT", "IEF"],
    "federal reserve":  ["CIB", "AVAL", "TLT"],
    "interest rate":    ["CIB", "AVAL", "TLT", "IEF", "SHY"],
    "tasa interes":     ["CIB", "AVAL"],
    "inflation":        ["CIB", "AVAL", "EWZ", "TLT"],
    "inflacion":        ["CIB", "AVAL"],
    "cpi":              ["CIB", "AVAL", "TLT"],
    "gdp":              ["EWZ", "EWW", "EWY"],
    "pib":              ["EWZ", "EWW"],
    "unemployment":     ["EWZ", "EWW", "TLT"],
    "jobs report":      ["EWZ", "EWW", "TLT"],
    "housing":          ["EWZ", "EWW"],
    "real estate":      ["EWZ", "EWW"],
 
    # ── US Markets ─────────────────────────────────────────────
    "recession":        ["EWZ", "EWW", "EWY", "ECH", "TLT", "IEF"],
    "recesion":         ["EWZ", "EWW", "TLT"],
    "S&P":              ["EWZ", "EWW", "EWY", "EWT"],
    "sp500":            ["EWZ", "EWW", "EWY"],
    "stock market":     ["EWZ", "EWW", "EWY"],
    "mercado":          ["EWZ", "EWW"],
    "equities":         ["EWZ", "EWW", "EWY"],
    "acciones":         ["EC", "CIB", "AVAL"],
    "earnings":         ["EC", "CIB", "AVAL", "EWZ"],
    "ipo":              ["EWZ", "EWW", "EWY"],
    "merger":           ["EC", "CIB"],
    "acquisition":      ["EC", "CIB"],
    "macro":            ["EWZ", "EWW", "EWY", "TLT"],
 
    # ── Bonds ──────────────────────────────────────────────────
    "treasury":         ["TLT", "IEF", "SHY"],
    "treasuries":       ["TLT", "IEF", "SHY"],
    "bond":             ["TLT", "IEF", "AGG", "BND"],
    "bonos":            ["TLT", "IEF"],
    "yield":            ["TLT", "IEF", "CIB", "AVAL"],
    "rendimiento":      ["TLT", "IEF"],
    "credit":           ["LQD", "HYG"],
    "high yield":       ["HYG"],
    "emerging bond":    ["EMB"],
 
    # ── Tech ───────────────────────────────────────────────────
    "semiconductor":    ["EWT", "EWY"],
    "tech":             ["EWT", "EWY"],
    "tecnologia":       ["EWT", "EWY"],
    "TSMC":             ["EWT"],
    "Samsung":          ["EWY"],
    "big tech":         ["EWT", "EWY"],
    "apple":            ["EWT", "EWY"],
    "nvidia":           ["EWT", "EWY"],
    "ai":               ["EWT", "EWY"],
    "inteligencia artificial": ["EWT", "EWY"],
 
    # ── Colombia specific ──────────────────────────────────────
    "ecopetrol":        ["EC"],
    "bancolombia":      ["CIB"],
    "grupo aval":       ["AVAL"],
    "davivienda":       ["PFBCOLOM.CL"],
    "geopark":          ["GPRK"],
    "tecnoglass":       ["TGLS"],
    "grupo sura":       ["GRUPSURA.CL"],
    "cementos argos":   ["CEMARGOS.CL"],
    "ISA energia":      ["ISA.CL"],
    "colombia":         ["EC", "CIB", "AVAL"],
    "colombiano":       ["EC", "CIB", "AVAL"],
    "colcap":           ["EC", "CIB", "AVAL", "GRUPSURA.CL", "CEMARGOS.CL"],
    "peso colombiano":  ["EC", "CIB", "AVAL"],
 
    # ── Latin America ──────────────────────────────────────────
    "brazil":           ["EWZ"],
    "brasil":           ["EWZ"],
    "petrobras":        ["EWZ"],
    "mexico":           ["EWW"],
    "pemex":            ["EWW"],
    "chile":            ["ECH"],
    "codelco":          ["ECH"],
    "peru":             ["EPU"],
    "latam":            ["EWZ", "EWW", "ECH", "EPU"],
    "america latina":   ["EWZ", "EWW", "ECH", "EPU"],
    "emerging":         ["EWZ", "EWW", "ECH", "EPU", "EWY"],
    "mercados emergentes": ["EWZ", "EWW", "ECH", "EPU", "EWY"],
 
    # ── Asia ───────────────────────────────────────────────────
    "korea":            ["EWY"],
    "corea":            ["EWY"],
    "taiwan":           ["EWT"],
    "indonesia":        ["EIDO"],
    "thailand":         ["THD"],
    "tailandia":        ["THD"],
    "china":            ["EWY", "EWT"],
    "trade war":        ["EWY", "EWT", "EIDO"],
    "tariff":           ["EWZ", "EWW", "EWY", "EWT"],
    "arancel":          ["EWZ", "EWW", "EWY"],
 
    # ── Africa ─────────────────────────────────────────────────
    "south africa":     ["EZA"],
    "sudafrica":        ["EZA"],
    "nigeria":          ["NGE"],
    "africa":           ["EZA", "NGE"],
 
    # ── Forex ──────────────────────────────────────────────────
    "dollar":           ["EC", "EWZ", "EWW", "TLT"],
    "dolar":            ["EC", "EWZ", "EWW"],
    "forex":            ["EC", "EWZ", "EWW"],
    "exchange rate":    ["EC", "EWZ", "EWW"],
    "tasa cambio":      ["EC", "EWZ"],
    "devaluation":      ["EWZ", "EWW", "EZA"],
    "devaluacion":      ["EWZ", "EWW"],
    "sanctions":        ["EZA", "NGE"],
    "geopolitics":      ["EZA", "NGE", "EWY"],
    "geopolitica":      ["EZA", "NGE"],
 
    # ── Brazil companies (EWZ) ────────────────────────────────
    "petrobras":        ["EWZ"],
    "vale":             ["EWZ"],
    "itau":             ["EWZ"],
    "bradesco":         ["EWZ"],
    "ambev":            ["EWZ"],
    "embraer":          ["EWZ"],
    "eletrobras":       ["EWZ"],
    "banco do brasil":  ["EWZ"],
    "weg":              ["EWZ"],
    "suzano":           ["EWZ"],
    "ibovespa":         ["EWZ"],
    "bovespa":          ["EWZ"],
 
    # ── Mexico companies (EWW) ────────────────────────────────
    "femsa":            ["EWW"],
    "america movil":    ["EWW"],
    "walmex":           ["EWW"],
    "grupo mexico":     ["EWW"],
    "cemex":            ["EWW"],
    "banorte":          ["EWW"],
    "televisa":         ["EWW"],
    "gruma":            ["EWW"],
    "bmv":              ["EWW"],
 
    # ── Chile companies (ECH) ─────────────────────────────────
    "falabella":        ["ECH"],
    "copec":            ["ECH"],
    "entel":            ["ECH"],
    "banco chile":      ["ECH"],
    "cencosud":         ["ECH"],
    "sqm":              ["ECH"],
    "antofagasta":      ["ECH"],
    "ipsa":             ["ECH"],
 
    # ── Peru companies (EPU) ──────────────────────────────────
    "credicorp":        ["EPU"],
    "buenaventura":     ["EPU"],
    "alicorp":          ["EPU"],
    "intercorp":        ["EPU"],
    "bvl":              ["EPU"],
 
    # ── South Africa companies (EZA) ──────────────────────────
    "naspers":          ["EZA"],
    "prosus":           ["EZA"],
    "sasol":            ["EZA"],
    "anglo american":   ["EZA"],
    "standard bank":    ["EZA"],
    "firstrand":        ["EZA"],
    "mtn":              ["EZA"],
    "shoprite":         ["EZA"],
    "jse":              ["EZA"],
 
    # ── Nigeria companies (NGE) ───────────────────────────────
    "dangote":          ["NGE"],
    "gtbank":           ["NGE"],
    "zenith bank":      ["NGE"],
    "access bank":      ["NGE"],
    "nnpc":             ["NGE"],
    "airtel nigeria":   ["NGE"],
 
    # ── Korea companies (EWY) ─────────────────────────────────
    "samsung":          ["EWY"],
    "lg":               ["EWY"],
    "hyundai":          ["EWY"],
    "sk hynix":         ["EWY"],
    "posco":            ["EWY"],
    "kakao":            ["EWY"],
    "naver":            ["EWY"],
    "kia":              ["EWY"],
    "kospi":            ["EWY"],
 
    # ── Taiwan companies (EWT) ────────────────────────────────
    "tsmc":             ["EWT"],
    "mediatek":         ["EWT"],
    "foxconn":          ["EWT"],
    "asus":             ["EWT"],
    "acer":             ["EWT"],
    "taiex":            ["EWT"],
    "taiwan semi":      ["EWT"],
 
    # ── Indonesia companies (EIDO) ────────────────────────────
    "bank central asia": ["EIDO"],
    "bank rakyat":      ["EIDO"],
    "telkom indonesia": ["EIDO"],
    "astra":            ["EIDO"],
    "bumi resources":   ["EIDO"],
    "idx indonesia":    ["EIDO"],
 
    # ── Thailand companies (THD) ──────────────────────────────
    "ptt":              ["THD"],
    "advanced info":    ["THD"],
    "kasikorn":         ["THD"],
    "siam cement":      ["THD"],
    "bangkok bank":     ["THD"],
    "set index":        ["THD"],
    "set thailand":     ["THD"],
}
 
# Only accept markets with these financial keywords in the question
FINANCIAL_KEYWORDS = [
    "gdp", "economy", "economic", "recession", "inflation", "rate", "market",
    "stock", "oil", "crude", "opec", "fed", "central bank", "currency",
    "peso", "real", "won", "rand", "rupiah", "baht", "dollar", "etf",
    "emerging", "index", "trade", "export", "import", "growth", "deficit",
]
 
 
# ── Polymarket ────────────────────────────────────────────────────────────────
 
def fetch_polymarket_markets(keyword: str) -> list:
    """Search active Polymarket markets by keyword."""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": 20,
            "q": keyword,
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            markets = data if isinstance(data, list) else data.get("markets", [])
            return markets
    except Exception as e:
        print(f"    [Polymarket] Error fetching '{keyword}': {e}")
    return []
 
 
def is_financial_market(question: str) -> bool:
    """Filter out non-financial markets (sports, entertainment, etc)."""
    q = question.lower()
    # Reject if contains entertainment/sports keywords
    reject = ["nba", "nfl", "nhl", "mlb", "ufc", "oscars", "grammy", "celebrity",
              "movie", "film", "actor", "actress", "singer", "album", "song",
              "game", "gta", "playstation", "xbox", "manga", "anime",
              "kardashian", "trump tweet", "elon tweet", "viral"]
    if any(r in q for r in reject):
        return False
    # Accept if contains financial keywords
    return any(f in q for f in FINANCIAL_KEYWORDS)
 
 
def parse_polymarket_market(market: dict) -> dict | None:
    """Extract relevant fields from a Polymarket market."""
    try:
        question = market.get("question", "")
        if not is_financial_market(question):
            return None
        outcomes = market.get("outcomes", "[]")
        prices   = market.get("outcomePrices", "[]")
 
        # Parse string arrays if needed
        if isinstance(outcomes, str):
            import json
            outcomes = json.loads(outcomes)
        if isinstance(prices, str):
            import json
            prices = json.loads(prices)
 
        if not outcomes or not prices:
            return None
 
        # Get Yes probability (first outcome usually)
        yes_idx = next((i for i, o in enumerate(outcomes)
                       if str(o).lower() in ["yes", "yes."]), 0)
        yes_prob = float(prices[yes_idx]) if yes_idx < len(prices) else 0.5
 
        return {
            "source":      "Polymarket",
            "question":    question,
            "yes_prob":    round(yes_prob, 3),
            "url":         f"https://polymarket.com/market/{market.get('conditionId', '')}",
            "end_date":    market.get("endDate", ""),
            "volume":      market.get("volume", 0),
        }
    except Exception:
        return None
 
 
# ── Kalshi ────────────────────────────────────────────────────────────────────
 
def fetch_kalshi_markets(keyword: str) -> list:
    """Search active Kalshi markets by keyword."""
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {
            "status":        "open",
            "series_ticker": "",
            "limit":         20,
        }
        headers = {"Accept": "application/json"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            markets = r.json().get("markets", [])
            # Filter by keyword in title
            keyword_lower = keyword.lower()
            return [m for m in markets
                    if keyword_lower in m.get("title", "").lower()
                    or keyword_lower in m.get("subtitle", "").lower()]
    except Exception as e:
        print(f"    [Kalshi] Error fetching '{keyword}': {e}")
    return []
 
 
def parse_kalshi_market(market: dict) -> dict | None:
    """Extract relevant fields from a Kalshi market."""
    try:
        yes_price = market.get("yes_bid", market.get("last_price", 50))
        yes_prob  = float(yes_price) / 100 if yes_price > 1 else float(yes_price)
 
        return {
            "source":   "Kalshi",
            "question": market.get("title", ""),
            "yes_prob": round(yes_prob, 3),
            "url":      f"https://kalshi.com/markets/{market.get('ticker', '')}",
            "end_date": market.get("close_time", ""),
            "volume":   market.get("volume", 0),
        }
    except Exception:
        return None
 
 
# ── Divergence Detection ──────────────────────────────────────────────────────
 
def get_signal_confidence(ticker: str, signal_results: list) -> float | None:
    """Get system confidence for a ticker from signal results."""
    for result in signal_results:
        if result["signal"] == "neutral":
            continue
        active_ticker = result["ticker_a"] if result["signal"] == "long_a" else result["ticker_b"]
        if active_ticker == ticker:
            return result["confidence"]
    return None
 
 
def detect_divergences(signal_results: list) -> list:
    """
    Search prediction markets for topics related to active signals.
    Detect divergences where market probability differs from system confidence.
    """
    if not signal_results:
        return []
 
    divergences = []
    checked_questions = set()
 
    for keyword, tickers in SEARCH_KEYWORDS.items():
        # Check if any related ticker has an active signal
        relevant_signals = []
        for ticker in tickers:
            conf = get_signal_confidence(ticker, signal_results)
            if conf and conf >= 0.50:
                relevant_signals.append((ticker, conf))
 
        if not relevant_signals:
            continue
 
        # Fetch from both platforms
        pm_markets = fetch_polymarket_markets(keyword)
        kl_markets = fetch_kalshi_markets(keyword)
 
        all_markets = []
        for m in pm_markets:
            parsed = parse_polymarket_market(m)
            if parsed:
                all_markets.append(parsed)
        for m in kl_markets:
            parsed = parse_kalshi_market(m)
            if parsed:
                all_markets.append(parsed)
 
        for market in all_markets:
            question = market["question"]
            if question in checked_questions:
                continue
            checked_questions.add(question)
 
            yes_prob = market["yes_prob"]
 
            # Compare with system confidence
            for ticker, system_conf in relevant_signals:
                gap = abs(system_conf - yes_prob)
 
                if gap >= DIVERGENCE_THRESHOLD:
                    direction = "ABOVE" if system_conf > yes_prob else "BELOW"
                    divergences.append({
                        "ticker":      ticker,
                        "system_conf": system_conf,
                        "market_prob": yes_prob,
                        "gap":         round(gap, 3),
                        "direction":   direction,
                        "question":    question,
                        "source":      market["source"],
                        "url":         market["url"],
                    })
 
    # Sort by gap size
    divergences.sort(key=lambda x: x["gap"], reverse=True)
    return divergences[:5]  # top 5 divergences
 
 
# ── Telegram Formatting ───────────────────────────────────────────────────────
 
def format_divergences_for_telegram(divergences: list) -> str:
    if not divergences:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔮 <b>DIVERGENCIAS DETECTADAS</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Tu sistema vs mercados de predicción</i>")
 
    for d in divergences:
        gap_pct      = int(d["gap"] * 100)
        system_pct   = int(d["system_conf"] * 100)
        market_pct   = int(d["market_prob"] * 100)
        emoji        = "🚨" if d["gap"] >= 0.40 else "⚠️"
 
        lines.append("")
        lines.append(f"{emoji} <b>{d['ticker']}</b> — {d['source']}")
        lines.append(f"Tu sistema: {system_pct}% | Mercado: {market_pct}%")
        lines.append(f"Brecha: <b>{gap_pct} puntos</b> ({d['direction']} del mercado)")
        lines.append(f"Mercado: {d['question'][:80]}")
 
        if d["direction"] == "ABOVE":
            lines.append("💡 <i>Tu modelo es más optimista que el mercado</i>")
        else:
            lines.append("💡 <i>El mercado es más optimista que tu modelo</i>")
 
    lines.append("")
    lines.append("⚠️ <i>Divergencias = oportunidad potencial, no garantía</i>")
    return "\n".join(lines)
 
 
def run_prediction_markets(signal_results: list) -> list:
    """Main entry point — detect and return divergences."""
    print(f"\n[Prediction Markets] Scanning for divergences...")
    try:
        divergences = detect_divergences(signal_results)
        if divergences:
            print(f"    [PM] Found {len(divergences)} divergence(s)")
            for d in divergences:
                print(f"    [PM] {d['ticker']}: system={int(d['system_conf']*100)}% market={int(d['market_prob']*100)}% gap={int(d['gap']*100)}pts — {d['source']}")
        else:
            print(f"    [PM] No significant divergences found")
        return divergences
    except Exception as e:
        print(f"    [PM] Error (non-fatal): {e}")
        return []
 
 
if __name__ == "__main__":
    # Test with sample signals
    test_signals = [
        {"signal": "long_a", "ticker_a": "EWZ", "ticker_b": "EWW",
         "pair": "Brazil vs Mexico", "confidence": 0.75},
        {"signal": "long_a", "ticker_a": "EC", "ticker_b": "GPRK",
         "pair": "Oil Integrated vs E&P", "confidence": 0.50},
    ]
    divs = run_prediction_markets(test_signals)
    print(format_divergences_for_telegram(divs))