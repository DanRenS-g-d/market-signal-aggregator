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
 
    # Risk-On vs Risk-Off (Stocks vs Bonds)
    {"name": "Brazil vs Long Bonds",  "a": "EWZ",        "b": "TLT",           "a_name": "Brazil ETF",  "b_name": "US Long Bonds","sector": "risk"},
    {"name": "Korea vs Long Bonds",   "a": "EWY",        "b": "TLT",           "a_name": "Korea ETF",   "b_name": "US Long Bonds","sector": "risk"},
    {"name": "EM vs US Bonds",        "a": "EWZ",        "b": "IEF",           "a_name": "Brazil ETF",  "b_name": "US Mid Bonds", "sector": "risk"},
    {"name": "HY vs IG Bonds",        "a": "HYG",        "b": "IEF",           "a_name": "High Yield",  "b_name": "Investment Grade","sector": "credit"},
    {"name": "EM Bonds vs US Bonds",  "a": "EMB",        "b": "TLT",           "a_name": "EM Bonds",    "b_name": "US Long Bonds","sector": "credit"},
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
    "NGE":  ["NGE ETF", "Nigeria stocks", "Dangote", "GTBank",
             "Zenith Bank", "Access Bank", "NNPC oil", "Airtel Nigeria",
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
 
    # Bond ETFs
    "TLT":           "TLT",
    "IEF":           "IEF",
    "HYG":           "HYG",
    "EMB":           "EMB",
}