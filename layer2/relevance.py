"""
Relevance filter for news articles.
Filters out articles that don't actually discuss the target ticker/company.

Two-layer approach:
1. Keyword match  — title/summary must mention the company or ticker
2. Domain denylist — known noisy domains that generate false positives
"""

# ── Company keywords per ticker ───────────────────────────────
TICKER_KEYWORDS = {
    "EC": [
        "ecopetrol", "ec stock", "ec shares", "ec nyse",
        "colombia oil", "colombia energy", "castilla crude",
        "ecopetrol sa", "ecopetrol adr",
    ],
    "CNEC.CN": [
        "canacol", "cnec", "canacol energy", "canadian gas co",
        "colombia gas", "colombia natural gas",
    ],
    "CIB": [
        "bancolombia", "cib stock", "cib shares", "cib nyse",
        "grupo cibest", "bancolombia sa", "bancolombia",
    ],
    "PFBCOLOM.CL": [
        "davivienda", "pfbcolom", "banco davivienda",
        "davivienda bank", "scotiabank davivienda",
    ],
}

# ── Domains known to generate false positives ─────────────────
# These sites use ticker symbols generically (e.g. "CIB" = Chartered Insurance Broker)
NOISY_DOMAINS = {
    "EC": [
        "immunitybc.com", "immunobio.com",        # ImmunityBio ticker confusion
        "theguardian.com",                         # wildlife/environment articles
        "bbc.com", "bbc.co.uk",                   # general news rarely EC-specific
    ],
    "CNEC.CN": [
        "law360.com",                              # legal firm articles
    ],
    "CIB": [
        "nasdaq.com",    # "Grupo Cibest Becomes Oversold (CIB)" = wrong company
        "sec.gov",       # raw SEC filings not useful for sentiment
    ],
    "PFBCOLOM.CL": [],
}


def is_relevant(ticker: str, title: str, summary: str = "", link: str = "") -> tuple[bool, str]:
    """
    Returns (is_relevant: bool, reason: str)
    
    An article is relevant if:
    1. Its domain is not in the denylist for this ticker
    2. Its title or summary contains at least one keyword for the ticker
    """
    title_lower = (title or "").lower()
    summary_lower = (summary or "").lower()
    link_lower = (link or "").lower()
    combined = title_lower + " " + summary_lower

    # ── Layer 1: Domain denylist ──────────────────────────────
    noisy = NOISY_DOMAINS.get(ticker, [])
    for domain in noisy:
        if domain in link_lower:
            return False, f"noisy_domain:{domain}"

    # ── Layer 2: Keyword match ────────────────────────────────
    keywords = TICKER_KEYWORDS.get(ticker, [ticker.lower()])
    for kw in keywords:
        if kw in combined:
            return True, f"keyword:{kw}"

    # No keyword matched — article is likely about a different company
    return False, "no_keyword_match"


def filter_articles(ticker: str, articles: list[dict]) -> tuple[list[dict], dict]:
    """
    Filter a list of articles for relevance.
    Returns (relevant_articles, stats)
    """
    relevant = []
    filtered_out = []

    for art in articles:
        ok, reason = is_relevant(
            ticker,
            art.get("title", ""),
            art.get("summary", ""),
            art.get("link", ""),
        )
        if ok:
            relevant.append(art)
        else:
            filtered_out.append({"title": art.get("title", "")[:60], "reason": reason})

    stats = {
        "total": len(articles),
        "relevant": len(relevant),
        "filtered": len(filtered_out),
        "filtered_items": filtered_out,
    }

    return relevant, stats