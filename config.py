PAIRS = [
    # Oil & Gas
    {"name": "Oil Integrated vs Gas", "a": "EC",        "b": "CNEC.CN",       "a_name": "Ecopetrol",   "b_name": "Canacol",    "sector": "oil_gas"},
    {"name": "Oil Integrated vs E&P", "a": "EC",        "b": "GPRK",          "a_name": "Ecopetrol",   "b_name": "GeoPark",    "sector": "oil_gas"},
    {"name": "E&P Oil vs Gas",        "a": "GPRK",      "b": "CNEC.CN",       "a_name": "GeoPark",     "b_name": "Canacol",    "sector": "oil_gas"},

    # Banking & Finance
    {"name": "Bancolombia vs Davivienda", "a": "CIB",      "b": "PFBCOLOM.CL",   "a_name": "Bancolombia", "b_name": "Davivienda", "sector": "banking"},
    {"name": "Aval vs Bancolombia",       "a": "AVAL",     "b": "CIB",           "a_name": "Grupo Aval",  "b_name": "Bancolombia","sector": "banking"},
    {"name": "CIB Ord vs Pfd",            "a": "CIBEST.CL","b": "PFCIBEST.CL",   "a_name": "CIB Ord",     "b_name": "CIB Pfd",    "sector": "banking"},

    # Utilities
    {"name": "ISA vs GEB",            "a": "ISA.CL",    "b": "GEB.CL",        "a_name": "ISA",         "b_name": "GEB",        "sector": "utilities"},

    # Conglomerates
    {"name": "Sura Ord vs Pfd",       "a": "GRUPSURA.CL","b": "PFGRUPSURA.CL","a_name": "Sura Ord",    "b_name": "Sura Pfd",   "sector": "conglomerates"},
    {"name": "Sura vs Aval",          "a": "GRUPSURA.CL","b": "AVAL",         "a_name": "Grupo Sura",  "b_name": "Grupo Aval", "sector": "conglomerates"},

    # Materials
    {"name": "Cemargos vs Tecnoglass","a": "CEMARGOS.CL","b": "TGLS",         "a_name": "Cementos Argos","b_name": "Tecnoglass","sector": "materials"},
]

SEARCH_TERMS = {
    "EC":           ["Ecopetrol", "EC stock", "Ecopetrol oil"],
    "CNEC.CN":      ["Canacol Energy", "Canacol gas Colombia"],
    "GPRK":         ["GeoPark", "GPRK stock", "GeoPark oil"],
    "CIB":          ["Bancolombia", "CIB stock", "Grupo Cibest"],
    "PFBCOLOM.CL":  ["Davivienda", "Davivienda banco"],
    "AVAL":         ["Grupo Aval", "AVAL stock", "Aval acciones"],
    "CIBEST.CL":    ["Bancolombia BVC", "CIBEST", "Bancolombia accion"],
    "PFCIBEST.CL":  ["Bancolombia preferencial", "PFCIBEST"],
    "ISA.CL":       ["Interconexion Electrica", "ISA Colombia", "ISA energia"],
    "GEB.CL":       ["Grupo Energia Bogota", "GEB Colombia", "energia bogota"],
    "GRUPSURA.CL":  ["Grupo Sura", "GRUPSURA", "Suramericana inversiones"],
    "PFGRUPSURA.CL":["Grupo Sura preferencial", "PFGRUPSURA"],
    "CEMARGOS.CL":  ["Cementos Argos", "CEMARGOS", "Argos cemento"],
    "TGLS":         ["Tecnoglass", "TGLS stock", "Tecnoglass Colombia"],
}

TICKERS = list(SEARCH_TERMS.keys())

# Yahoo Finance symbol mapping (for technicals + similarity bootstrap)
YAHOO_MAP = {
    "EC":           "EC",
    "CNEC.CN":      "CNE.TO",
    "GPRK":         "GPRK",
    "CIB":          "CIB",
    "PFBCOLOM.CL":  "PFBCOLOM.CL",
    "AVAL":         "AVAL",
    "CIBEST.CL":    "CIBEST.CL",
    "PFCIBEST.CL":  "PFCIBEST.CL",
    "ISA.CL":       "ISA.CL",
    "GEB.CL":       "GEB.CL",
    "GRUPSURA.CL":  "GRUPSURA.CL",
    "PFGRUPSURA.CL":"PFGRUPSURA.CL",
    "CEMARGOS.CL":  "CEMARGOS.CL",
    "TGLS":         "TGLS",
}