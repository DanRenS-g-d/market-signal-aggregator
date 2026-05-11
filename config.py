# PAIRS — pruned after ablation testing (April 2026)
# Tier A: 76-100% accuracy — core alpha
# Tier B: 61-69% accuracy — marginal, keep for now
# Tier C: removed — Cemargos/TGLS, HY/IG, EM bonds, Korea/Asia pairs
 
PAIRS = [
    # ── Tier A: Colombia Oil & Gas ────────────────────────────
    # CNEC.CN removed — delisted
    {"name": "Oil Integrated vs E&P", "a": "EC",         "b": "GPRK",          "a_name": "Ecopetrol",   "b_name": "GeoPark",     "sector": "oil_gas",      "tier": "B"},
 
    # ── Tier A: Colombia Banking ──────────────────────────────
    {"name": "CIB Ord vs Pfd",        "a": "CIBEST.CL",  "b": "PFCIBEST.CL",   "a_name": "CIB Ord",     "b_name": "CIB Pfd",     "sector": "banking",      "tier": "A"},
    # PFBCOLOM.CL removed — delisted
    {"name": "Aval vs Bancolombia",   "a": "AVAL",       "b": "CIB",           "a_name": "Grupo Aval",  "b_name": "Bancolombia", "sector": "banking",      "tier": "B"},
 
    # ── Tier A: Colombia Utilities ────────────────────────────
    {"name": "ISA vs GEB",            "a": "ISA.CL",     "b": "GEB.CL",        "a_name": "ISA",         "b_name": "GEB",         "sector": "utilities",    "tier": "A"},
 
    # ── Colombia Conglomerates ────────────────────────────────
    # GRUPSURA.CL removed — delisted
    # Replaced with CIB vs AVAL (both liquid, same sector)
    {"name": "Bancolombia vs Aval",   "a": "CIB",        "b": "AVAL",          "a_name": "Bancolombia", "b_name": "Grupo Aval",  "sector": "banking",      "tier": "B"},
 
    # ── Tier A: Latam ETFs ────────────────────────────────────
    {"name": "Brazil vs Mexico",      "a": "EWZ",        "b": "EWW",           "a_name": "Brazil ETF",  "b_name": "Mexico ETF",  "sector": "latam",        "tier": "A"},
    {"name": "Mexico vs Peru",        "a": "EWW",        "b": "EPU",           "a_name": "Mexico ETF",  "b_name": "Peru ETF",    "sector": "latam",        "tier": "A"},
    {"name": "Peru vs Chile",         "a": "EPU",        "b": "ECH",           "a_name": "Peru ETF",    "b_name": "Chile ETF",   "sector": "latam",        "tier": "A"},
    {"name": "Brazil vs Chile",       "a": "EWZ",        "b": "ECH",           "a_name": "Brazil ETF",  "b_name": "Chile ETF",   "sector": "latam",        "tier": "A"},
 
    # ── Tier B: Risk-on / Risk-off ────────────────────────────
    {"name": "Brazil vs Long Bonds",  "a": "EWZ",        "b": "TLT",           "a_name": "Brazil ETF",  "b_name": "US Long Bonds","sector": "risk",         "tier": "B"},
    {"name": "EM vs US Bonds",        "a": "EWZ",        "b": "IEF",           "a_name": "Brazil ETF",  "b_name": "US Mid Bonds", "sector": "risk",         "tier": "B"},
 
    # ── Tier B: Africa ────────────────────────────────────────
    # NGE removed — no price data
    {"name": "South Africa vs Brazil","a": "EZA",        "b": "EWZ",           "a_name": "S.Africa ETF","b_name": "Brazil ETF",  "sector": "africa",       "tier": "B"},
]
 
# REMOVED (Tier C — ablation showed negative/low alpha):
# Cemargos vs Tecnoglass  35% accuracy
# Aval vs Bancolombia     32% accuracy
# HY vs IG Bonds           0% accuracy
# EM Bonds vs US Bonds    29% accuracy
# Korea vs Taiwan         45% accuracy
# Korea vs Indonesia      45% accuracy
# Korea vs Long Bonds     78% acc but -0.64% avg P&L
# Indonesia vs Thailand   40% accuracy
# Sura Ord vs Pfd         (replaced by Sura vs Aval)
 
SEARCH_TERMS = {
    # Colombia stocks
    "EC":            ["Ecopetrol", "EC stock", "Ecopetrol oil"],
    "GPRK":          ["GeoPark", "GPRK stock", "GeoPark oil"],
    "CIB":           ["Bancolombia", "CIB stock", "Grupo Cibest"],
    "AVAL":          ["Grupo Aval", "AVAL stock", "Aval acciones"],
    "CIBEST.CL":     ["Bancolombia BVC", "CIBEST", "Bancolombia accion"],
    "PFCIBEST.CL":   ["Bancolombia preferencial", "PFCIBEST"],
    "ISA.CL":        ["Interconexion Electrica", "ISA Colombia", "ISA energia"],
    "GEB.CL":        ["Grupo Energia Bogota", "GEB Colombia", "energia bogota"],
    "CEMARGOS.CL":   ["Cementos Argos", "CEMARGOS", "Argos cemento"],
    "TGLS":          ["Tecnoglass", "TGLS stock", "Tecnoglass Colombia"],
 
    # Latin America ETFs — top companies + index names
    "EWZ":  ["EWZ ETF", "Brazil stocks", "Petrobras", "Vale mining",
             "Itau Unibanco", "Bradesco bank", "Ambev", "Embraer",
             "Eletrobras", "WEG industries", "Ibovespa", "Brazil economy",
             "Banco do Brasil", "Suzano", "Brazil real BRL"],
    "EWW":  ["EWW ETF", "Mexico stocks", "Femsa", "America Movil",
             "Grupo Mexico", "Cemex", "Banorte", "Walmex", "Televisa",
             "Gruma", "BMV Mexico", "Mexico economy", "Mexican peso"],
    "ECH":  ["ECH ETF", "Chile stocks", "Falabella", "Codelco copper",
             "SQM lithium", "Copec", "Banco de Chile", "Cencosud",
             "Antofagasta", "IPSA index", "Chile economy", "Chilean peso"],
    "EPU":  ["EPU ETF", "Peru stocks", "Credicorp", "Buenaventura gold",
             "Alicorp", "Intercorp", "BVL Lima", "Peru economy",
             "Peruvian sol", "Peru copper", "Peru mining"],
 
    # Africa ETFs — top companies + index names
    "EZA":  ["EZA ETF", "South Africa stocks", "Naspers", "Prosus",
             "Sasol energy", "Anglo American", "Standard Bank",
             "FirstRand", "MTN Group", "Shoprite", "JSE index",
             "South Africa economy", "South African rand"],
             "Nigerian Stock Exchange", "Nigeria economy", "Nigerian naira",
             "Nigeria oil production"],
 
    # Southeast Asia ETFs — top companies + index names
    "EWY":  ["EWY ETF", "Korea stocks", "Samsung Electronics",
             "SK Hynix", "LG Electronics", "Hyundai", "Kia",
             "Kakao", "Naver", "POSCO", "KOSPI index",
             "South Korea economy", "Korean won"],
    "EWT":  ["EWT ETF", "Taiwan stocks", "TSMC", "Taiwan Semiconductor",
             "MediaTek", "Foxconn", "ASE Technology", "Largan",
             "TAIEX index", "Taiwan economy", "Taiwan dollar",
             "Taiwan chips", "semiconductor Taiwan"],
    "EIDO": ["EIDO ETF", "Indonesia stocks", "Bank Central Asia",
             "Bank Rakyat Indonesia", "Telkom Indonesia", "Astra International",
             "Bumi Resources", "IDX Composite", "Indonesia economy",
             "Indonesian rupiah", "Indonesia palm oil"],
    "THD":  ["THD ETF", "Thailand stocks", "PTT oil", "Advanced Info",
             "Kasikorn Bank", "Siam Cement", "Bangkok Bank",
             "SET index Thailand", "Thailand economy", "Thai baht",
             "Thailand tourism"],
 
    # Bond ETFs
    "TLT":  ["TLT ETF", "US treasury bonds", "long bonds",
             "20 year treasury", "bond market", "treasury yield",
             "US government bonds", "bond rally", "flight to safety"],
    "IEF":  ["IEF ETF", "10 year treasury", "intermediate bonds",
             "US bonds", "treasury note", "10yr yield"],
    "HYG":  ["HYG ETF", "high yield bonds", "junk bonds",
             "credit spreads", "corporate bonds", "HY spreads"],
    "EMB":  ["EMB ETF", "emerging market bonds", "EM bonds",
             "sovereign debt", "EM debt", "dollar bonds emerging"],
}
 
TICKERS = list(SEARCH_TERMS.keys())
 
YAHOO_MAP = {
    # Colombia stocks
    "EC":            "EC",
    "GPRK":          "GPRK",
    "CIB":           "CIB",
    "AVAL":          "AVAL",
    "CIBEST.CL":     "CIBEST.CL",
    "PFCIBEST.CL":   "PFCIBEST.CL",
    "ISA.CL":        "ISA.CL",
    "GEB.CL":        "GEB.CL",
    "CEMARGOS.CL":   "CEMARGOS.CL",
    "TGLS":          "TGLS",
 
    # Latin America ETFs
    "EWZ":           "EWZ",
    "EWW":           "EWW",
    "ECH":           "ECH",
    "EPU":           "EPU",
 
    # Africa ETFs
    "EZA":           "EZA",
 
    # Southeast Asia ETFs
    "EWY":           "EWY",
    "EWT":           "EWT",
    "EIDO":          "EIDO",
    "THD":           "THD",
 
    # Bond ETFs
    "TLT":           "TLT",
    "IEF":           "IEF",
    "HYG":           "HYG",
    "EMB":           "EMB",
}