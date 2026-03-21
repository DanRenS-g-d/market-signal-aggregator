PAIRS = [
    # Oil & Gas (Colombia)
    {"name": "Oil Integrated vs Gas", "a": "EC",        "b": "CNEC.CN",       "a_name": "Ecopetrol",   "b_name": "Canacol",    "sector": "oil_gas"},
    {"name": "Oil Integrated vs E&P", "a": "EC",        "b": "GPRK",          "a_name": "Ecopetrol",   "b_name": "GeoPark",    "sector": "oil_gas"},
    {"name": "E&P Oil vs Gas",        "a": "GPRK",      "b": "CNEC.CN",       "a_name": "GeoPark",     "b_name": "Canacol",    "sector": "oil_gas"},
 
    # Banking & Finance (Colombia)
    {"name": "Bancolombia vs Davivienda", "a": "CIB",       "b": "PFBCOLOM.CL",  "a_name": "Bancolombia", "b_name": "Davivienda", "sector": "banking"},
    {"name": "Aval vs Bancolombia",       "a": "AVAL",      "b": "CIB",          "a_name": "Grupo Aval",  "b_name": "Bancolombia","sector": "banking"},
    {"name": "CIB Ord vs Pfd",            "a": "CIBEST.CL", "b": "PFCIBEST.CL",  "a_name": "CIB Ord",     "b_name": "CIB Pfd",    "sector": "banking"},
 
    # Utilities (Colombia)
    {"name": "ISA vs GEB",            "a": "ISA.CL",     "b": "GEB.CL",        "a_name": "ISA",         "b_name": "GEB",        "sector": "utilities"},
 
    # Conglomerates (Colombia)
    {"name": "Sura Ord vs Pfd",       "a": "GRUPSURA.CL","b": "PFGRUPSURA.CL", "a_name": "Sura Ord",    "b_name": "Sura Pfd",   "sector": "conglomerates"},
    {"name": "Sura vs Aval",          "a": "GRUPSURA.CL","b": "AVAL",          "a_name": "Grupo Sura",  "b_name": "Grupo Aval", "sector": "conglomerates"},
 
    # Materials (Colombia)
    {"name": "Cemargos vs Tecnoglass","a": "CEMARGOS.CL","b": "TGLS",          "a_name": "Cementos Argos","b_name": "Tecnoglass","sector": "materials"},
 
    # Latin America ETFs
    {"name": "Brazil vs Mexico",      "a": "EWZ",        "b": "EWW",           "a_name": "Brazil ETF",  "b_name": "Mexico ETF", "sector": "latam"},
    {"name": "Brazil vs Chile",       "a": "EWZ",        "b": "ECH",           "a_name": "Brazil ETF",  "b_name": "Chile ETF",  "sector": "latam"},
    {"name": "Peru vs Chile",         "a": "EPU",        "b": "ECH",           "a_name": "Peru ETF",    "b_name": "Chile ETF",  "sector": "latam"},
    {"name": "Mexico vs Peru",        "a": "EWW",        "b": "EPU",           "a_name": "Mexico ETF",  "b_name": "Peru ETF",   "sector": "latam"},
 
    # Africa ETFs
    {"name": "South Africa vs Nigeria","a": "EZA",       "b": "NGE",           "a_name": "S.Africa ETF","b_name": "Nigeria ETF","sector": "africa"},
 
    # Southeast Asia ETFs
    {"name": "Korea vs Taiwan",       "a": "EWY",        "b": "EWT",           "a_name": "Korea ETF",   "b_name": "Taiwan ETF", "sector": "asia"},
    {"name": "Indonesia vs Thailand", "a": "EIDO",       "b": "THD",           "a_name": "Indonesia ETF","b_name": "Thailand ETF","sector": "asia"},
    {"name": "Korea vs Indonesia",    "a": "EWY",        "b": "EIDO",          "a_name": "Korea ETF",   "b_name": "Indonesia ETF","sector": "asia"},
]
 
SEARCH_TERMS = {
    # Colombia stocks
    "EC":            ["Ecopetrol", "EC stock", "Ecopetrol oil"],
    "CNEC.CN":       ["Canacol Energy", "Canacol gas Colombia"],
    "GPRK":          ["GeoPark", "GPRK stock", "GeoPark oil"],
    "CIB":           ["Bancolombia", "CIB stock", "Grupo Cibest"],
    "PFBCOLOM.CL":   ["Davivienda", "Davivienda banco"],
    "AVAL":          ["Grupo Aval", "AVAL stock", "Aval acciones"],
    "CIBEST.CL":     ["Bancolombia BVC", "CIBEST", "Bancolombia accion"],
    "PFCIBEST.CL":   ["Bancolombia preferencial", "PFCIBEST"],
    "ISA.CL":        ["Interconexion Electrica", "ISA Colombia", "ISA energia"],
    "GEB.CL":        ["Grupo Energia Bogota", "GEB Colombia", "energia bogota"],
    "GRUPSURA.CL":   ["Grupo Sura", "GRUPSURA", "Suramericana inversiones"],
    "PFGRUPSURA.CL": ["Grupo Sura preferencial", "PFGRUPSURA"],
    "CEMARGOS.CL":   ["Cementos Argos", "CEMARGOS", "Argos cemento"],
    "TGLS":          ["Tecnoglass", "TGLS stock", "Tecnoglass Colombia"],
 
    # Latin America ETFs
    "EWZ":           ["EWZ ETF", "Brazil stocks", "iShares Brazil", "Brazil market"],
    "EWW":           ["EWW ETF", "Mexico stocks", "iShares Mexico", "Mexico market"],
    "ECH":           ["ECH ETF", "Chile stocks", "iShares Chile", "Chile market"],
    "EPU":           ["EPU ETF", "Peru stocks", "iShares Peru", "Peru market"],
 
    # Africa ETFs
    "EZA":           ["EZA ETF", "South Africa stocks", "iShares South Africa"],
    "NGE":           ["NGE ETF", "Nigeria stocks", "Nigeria market", "Global X Nigeria"],
 
    # Southeast Asia ETFs
    "EWY":           ["EWY ETF", "Korea stocks", "iShares Korea", "South Korea market"],
    "EWT":           ["EWT ETF", "Taiwan stocks", "iShares Taiwan", "Taiwan market"],
    "EIDO":          ["EIDO ETF", "Indonesia stocks", "iShares Indonesia"],
    "THD":           ["THD ETF", "Thailand stocks", "iShares Thailand"],
}
 
TICKERS = list(SEARCH_TERMS.keys())
 
YAHOO_MAP = {
    # Colombia stocks
    "EC":            "EC",
    "CNEC.CN":       "CNE.TO",
    "GPRK":          "GPRK",
    "CIB":           "CIB",
    "PFBCOLOM.CL":   "PFBCOLOM.CL",
    "AVAL":          "AVAL",
    "CIBEST.CL":     "CIBEST.CL",
    "PFCIBEST.CL":   "PFCIBEST.CL",
    "ISA.CL":        "ISA.CL",
    "GEB.CL":        "GEB.CL",
    "GRUPSURA.CL":   "GRUPSURA.CL",
    "PFGRUPSURA.CL": "PFGRUPSURA.CL",
    "CEMARGOS.CL":   "CEMARGOS.CL",
    "TGLS":          "TGLS",
 
    # Latin America ETFs
    "EWZ":           "EWZ",
    "EWW":           "EWW",
    "ECH":           "ECH",
    "EPU":           "EPU",
 
    # Africa ETFs
    "EZA":           "EZA",
    "NGE":           "NGE",
 
    # Southeast Asia ETFs
    "EWY":           "EWY",
    "EWT":           "EWT",
    "EIDO":          "EIDO",
    "THD":           "THD",
}