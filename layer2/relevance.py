"""
Relevance filter for news articles — extended for all 15 tickers.
"""
 
TICKER_KEYWORDS = {
    "EC":            ["ecopetrol", "ec stock", "ec nyse", "ec shares", "castilla crude", "ecopetrol sa", "ecopetrol adr"],
    "CNEC.CN":       ["canacol", "cnec", "canacol energy", "canadian gas co", "colombia gas", "colombia natural gas"],
    "GPRK":          ["geopark", "gprk", "geo park", "geopark oil", "geopark colombia"],
    "CIB":           ["bancolombia", "cib stock", "cib shares", "cib nyse", "grupo cibest", "bancolombia sa"],
    "PFBCOLOM.CL":   ["davivienda", "pfbcolom", "banco davivienda", "scotiabank davivienda"],
    "AVAL":          ["grupo aval", "aval stock", "aval nyse", "aval acciones", "banco de bogota", "banco popular colombia"],
    "CIBEST.CL":     ["bancolombia", "cibest", "bancolombia bvc", "bancolombia accion"],
    "PFCIBEST.CL":   ["bancolombia preferencial", "pfcibest", "bancolombia pfd"],
    "ISA.CL":        ["interconexion electrica", "isa colombia", "isa energia", "isa transmision", "intercolombia"],
    "GEB.CL":        ["grupo energia bogota", "geb colombia", "energia bogota", "gas natural fenosa colombia"],
    "GRUPSURA.CL":   ["grupo sura", "grupsura", "suramericana", "sura inversiones", "grupo de inversiones suramericana"],
    "PFGRUPSURA.CL": ["grupo sura preferencial", "pfgrupsura", "sura pfd"],
    "CEMARGOS.CL":   ["cementos argos", "cemargos", "argos cemento", "argos colombia"],
    "TGLS":          ["tecnoglass", "tgls", "tecnoglass colombia", "tecnoglass barranquilla"],
}
 
NOISY_DOMAINS = {
    "EC":            ["immunitybc.com", "theguardian.com"],
    "CNEC.CN":       ["law360.com"],
    "GPRK":          [],
    "CIB":           ["sec.gov"],
    "PFBCOLOM.CL":   [],
    "AVAL":          [],
    "CIBEST.CL":     ["sec.gov"],
    "PFCIBEST.CL":   ["sec.gov"],
    "ISA.CL":        [],
    "GEB.CL":        [],
    "GRUPSURA.CL":   [],
    "PFGRUPSURA.CL": [],
    "CEMARGOS.CL":   [],
    "TGLS":          [],
}
 
 
def is_relevant(ticker: str, title: str, summary: str = "", link: str = "") -> tuple[bool, str]:
    title_lower = (title or "").lower()
    summary_lower = (summary or "").lower()
    link_lower = (link or "").lower()
    combined = title_lower + " " + summary_lower
 
    for domain in NOISY_DOMAINS.get(ticker, []):
        if domain in link_lower:
            return False, f"noisy_domain:{domain}"
 
    for kw in TICKER_KEYWORDS.get(ticker, [ticker.lower()]):
        if kw in combined:
            return True, f"keyword:{kw}"
 
    return False, "no_keyword_match"
 
 
def filter_articles(ticker: str, articles: list[dict]) -> tuple[list[dict], dict]:
    relevant, filtered_out = [], []
    for art in articles:
        ok, reason = is_relevant(ticker, art.get("title", ""), art.get("summary", ""), art.get("link", ""))
        if ok:
            relevant.append(art)
        else:
            filtered_out.append({"title": art.get("title", "")[:60], "reason": reason})
    return relevant, {"total": len(articles), "relevant": len(relevant),
                      "filtered": len(filtered_out), "filtered_items": filtered_out}
 
# Bond ETF keywords
BOND_ETF_KEYWORDS = {
    "TLT":  ["tlt", "tlt etf", "us treasury", "long bonds", "20 year treasury", "bond market", "treasuries"],
    "IEF":  ["ief", "ief etf", "10 year treasury", "intermediate bonds", "us bonds"],
    "HYG":  ["hyg", "hyg etf", "high yield", "junk bonds", "credit spread", "corporate bonds"],
    "EMB":  ["emb", "emb etf", "emerging market bonds", "em bonds", "sovereign debt"],
}
 
# ETF keywords (append to existing TICKER_KEYWORDS)
ETF_KEYWORDS = {
    "EWZ":  ["ewz", "brazil etf", "ishares brazil", "brazil stocks", "bovespa", "petrobras", "vale"],
    "EWW":  ["eww", "mexico etf", "ishares mexico", "mexico stocks", "bmv", "pemex", "femsa"],
    "ECH":  ["ech", "chile etf", "ishares chile", "chile stocks", "ipsa", "codelco"],
    "EPU":  ["epu", "peru etf", "ishares peru", "peru stocks", "bvl"],
    "EZA":  ["eza", "south africa etf", "ishares south africa", "jse", "naspers", "sasol"],
    "NGE":  ["nge", "nigeria etf", "nigeria stocks", "nse nigeria", "dangote", "gtbank"],
    "EWY":  ["ewy", "korea etf", "ishares korea", "kospi", "samsung", "sk hynix"],
    "EWT":  ["ewt", "taiwan etf", "ishares taiwan", "taiex", "tsmc", "taiwan semiconductor"],
    "EIDO": ["eido", "indonesia etf", "ishares indonesia", "idx indonesia", "bank central asia"],
    "THD":  ["thd", "thailand etf", "ishares thailand", "set thailand", "ptt", "thai market"],
}
 
# Merge into main TICKER_KEYWORDS
TICKER_KEYWORDS.update(ETF_KEYWORDS)
TICKER_KEYWORDS.update(BOND_ETF_KEYWORDS)
 
# No noisy domains for ETFs or bonds
for etf in list(ETF_KEYWORDS.keys()) + list(BOND_ETF_KEYWORDS.keys()):
    if etf not in NOISY_DOMAINS:
        NOISY_DOMAINS[etf] = []