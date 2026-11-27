"""Catalogue intégré : grandes valeurs et ETF des principales bourses mondiales (symboles Yahoo Finance).

Disponible hors connexion, dès la création du compte. La recherche Yahoo reste possible pour tout autre titre.
Format d'une ligne : SYMBOLE|Nom|Secteur
"""
from __future__ import annotations

_BRUT = """
AC.PA|Accor|Hôtellerie
AI.PA|Air Liquide|Chimie
AIR.PA|Airbus|Aéronautique
ALO.PA|Alstom|Industrie
AMUN.PA|Amundi|Finance
ADP.PA|Aéroports de Paris|Transport
AF.PA|Air France-KLM|Transport
AM.PA|Dassault Aviation|Aéronautique
BIM.PA|bioMérieux|Santé
BNP.PA|BNP Paribas|Banque
BOL.PA|Bolloré|Médias
BN.PA|Danone|Alimentation
BVI.PA|Bureau Veritas|Services
CA.PA|Carrefour|Distribution
CAP.PA|Capgemini|Technologie
ACA.PA|Crédit Agricole|Banque
CS.PA|AXA|Assurance
DG.PA|Vinci|Construction
DIM.PA|Sartorius Stedim Biotech|Santé
DSY.PA|Dassault Systèmes|Technologie
EDEN.PA|Edenred|Services
EL.PA|EssilorLuxottica|Santé
ELIS.PA|Elis|Services
EN.PA|Bouygues|Construction
ENGI.PA|Engie|Énergie
ERA.PA|Eramet|Matériaux
ERF.PA|Eurofins Scientific|Santé
FGR.PA|Eiffage|Construction
FDJ.PA|FDJ United|Loisirs
GET.PA|Getlink|Transport
GLE.PA|Société Générale|Banque
GTT.PA|GTT|Énergie
HO.PA|Thales|Défense
IPN.PA|Ipsen|Santé
KER.PA|Kering|Luxe
LR.PA|Legrand|Industrie
MC.PA|LVMH|Luxe
ML.PA|Michelin|Automobile
NEX.PA|Nexans|Industrie
NK.PA|Imerys|Matériaux
OR.PA|L'Oréal|Cosmétique
ORA.PA|Orange|Télécoms
PUB.PA|Publicis|Médias
RCO.PA|Rémy Cointreau|Boissons
RF.PA|Eurazeo|Finance
RI.PA|Pernod Ricard|Boissons
RMS.PA|Hermès|Luxe
RNO.PA|Renault|Automobile
RXL.PA|Rexel|Industrie
SAF.PA|Safran|Aéronautique
SAN.PA|Sanofi|Santé
SCR.PA|SCOR|Assurance
SGO.PA|Saint-Gobain|Construction
SK.PA|SEB|Consommation
SOI.PA|Soitec|Semi-conducteurs
SPIE.PA|Spie|Services
STLAP.PA|Stellantis|Automobile
STMPA.PA|STMicroelectronics|Semi-conducteurs
SU.PA|Schneider Electric|Industrie
SW.PA|Sodexo|Services
TEP.PA|Teleperformance|Services
TFI.PA|TF1|Médias
TTE.PA|TotalEnergies|Énergie
UBI.PA|Ubisoft|Jeux vidéo
URW.PA|Unibail-Rodamco-Westfield|Immobilier
VIE.PA|Veolia|Services collectifs
VIV.PA|Vivendi|Médias
VK.PA|Vallourec|Industrie
WLN.PA|Worldline|Paiement
ADS.DE|Adidas|Consommation
ALV.DE|Allianz|Assurance
BAS.DE|BASF|Chimie
BAYN.DE|Bayer|Santé
BEI.DE|Beiersdorf|Cosmétique
BMW.DE|BMW|Automobile
CBK.DE|Commerzbank|Banque
CON.DE|Continental|Automobile
DB1.DE|Deutsche Börse|Finance
DBK.DE|Deutsche Bank|Banque
DHL.DE|DHL Group|Transport
DTE.DE|Deutsche Telekom|Télécoms
DTG.DE|Daimler Truck|Automobile
ENR.DE|Siemens Energy|Énergie
EOAN.DE|E.ON|Services collectifs
FRE.DE|Fresenius|Santé
HEI.DE|Heidelberg Materials|Matériaux
HEN3.DE|Henkel|Consommation
HNR1.DE|Hannover Re|Assurance
IFX.DE|Infineon|Semi-conducteurs
MBG.DE|Mercedes-Benz|Automobile
MRK.DE|Merck KGaA|Santé
MTX.DE|MTU Aero Engines|Aéronautique
MUV2.DE|Munich Re|Assurance
P911.DE|Porsche|Automobile
PUM.DE|Puma|Consommation
QIA.DE|Qiagen|Santé
RHM.DE|Rheinmetall|Défense
RWE.DE|RWE|Services collectifs
SAP.DE|SAP|Technologie
SHL.DE|Siemens Healthineers|Santé
SIE.DE|Siemens|Industrie
SY1.DE|Symrise|Chimie
VNA.DE|Vonovia|Immobilier
VOW3.DE|Volkswagen|Automobile
ZAL.DE|Zalando|Distribution
AD.AS|Ahold Delhaize|Distribution
ADYEN.AS|Adyen|Paiement
AKZA.AS|AkzoNobel|Chimie
ASM.AS|ASM International|Semi-conducteurs
ASML.AS|ASML|Semi-conducteurs
BESI.AS|BE Semiconductor|Semi-conducteurs
HEIA.AS|Heineken|Boissons
INGA.AS|ING|Banque
KPN.AS|KPN|Télécoms
MT.AS|ArcelorMittal|Matériaux
PHIA.AS|Philips|Santé
PRX.AS|Prosus|Technologie
RAND.AS|Randstad|Services
WKL.AS|Wolters Kluwer|Médias
ABI.BR|AB InBev|Boissons
AGS.BR|Ageas|Assurance
KBC.BR|KBC|Banque
SOLB.BR|Solvay|Chimie
UCB.BR|UCB|Santé
ENEL.MI|Enel|Services collectifs
ENI.MI|Eni|Énergie
G.MI|Generali|Assurance
ISP.MI|Intesa Sanpaolo|Banque
LDO.MI|Leonardo|Défense
MONC.MI|Moncler|Luxe
PRY.MI|Prysmian|Industrie
RACE.MI|Ferrari|Automobile
UCG.MI|UniCredit|Banque
AENA.MC|Aena|Transport
AMS.MC|Amadeus|Technologie
BBVA.MC|BBVA|Banque
CABK.MC|CaixaBank|Banque
IBE.MC|Iberdrola|Services collectifs
ITX.MC|Inditex|Distribution
REP.MC|Repsol|Énergie
SAN.MC|Banco Santander|Banque
TEF.MC|Telefónica|Télécoms
EDP.LS|EDP|Services collectifs
GALP.LS|Galp|Énergie
JMT.LS|Jerónimo Martins|Distribution
ABBN.SW|ABB|Industrie
ALC.SW|Alcon|Santé
CFR.SW|Richemont|Luxe
GIVN.SW|Givaudan|Chimie
HOLN.SW|Holcim|Construction
LOGN.SW|Logitech|Technologie
LONN.SW|Lonza|Santé
NESN.SW|Nestlé|Alimentation
NOVN.SW|Novartis|Santé
ROG.SW|Roche|Santé
SIKA.SW|Sika|Construction
SREN.SW|Swiss Re|Assurance
UBSG.SW|UBS|Banque
ZURN.SW|Zurich Insurance|Assurance
AAL.L|Anglo American|Matériaux
AZN.L|AstraZeneca|Santé
BA.L|BAE Systems|Défense
BARC.L|Barclays|Banque
BATS.L|British American Tobacco|Tabac
BP.L|BP|Énergie
CPG.L|Compass Group|Services
DGE.L|Diageo|Boissons
EXPN.L|Experian|Services
GLEN.L|Glencore|Matériaux
GSK.L|GSK|Santé
HSBA.L|HSBC|Banque
IMB.L|Imperial Brands|Tabac
LLOY.L|Lloyds|Banque
LSEG.L|London Stock Exchange Group|Finance
NG.L|National Grid|Services collectifs
NWG.L|NatWest|Banque
PRU.L|Prudential|Assurance
REL.L|RELX|Médias
RIO.L|Rio Tinto|Matériaux
RR.L|Rolls-Royce|Aéronautique
SHEL.L|Shell|Énergie
TSCO.L|Tesco|Distribution
ULVR.L|Unilever|Consommation
VOD.L|Vodafone|Télécoms
CARL-B.CO|Carlsberg|Boissons
DSV.CO|DSV|Transport
MAERSK-B.CO|Maersk|Transport
NOVO-B.CO|Novo Nordisk|Santé
ORSTED.CO|Ørsted|Énergie
ATCO-A.ST|Atlas Copco|Industrie
ERIC-B.ST|Ericsson|Télécoms
HM-B.ST|H&M|Distribution
INVE-B.ST|Investor AB|Finance
VOLV-B.ST|Volvo|Automobile
DNB.OL|DNB|Banque
EQNR.OL|Equinor|Énergie
NHY.OL|Norsk Hydro|Matériaux
TEL.OL|Telenor|Télécoms
NOKIA.HE|Nokia|Télécoms
NESTE.HE|Neste|Énergie
AAPL|Apple|Technologie
ABBV|AbbVie|Santé
ABNB|Airbnb|Loisirs
ABT|Abbott|Santé
ADBE|Adobe|Technologie
AMAT|Applied Materials|Semi-conducteurs
AMD|AMD|Semi-conducteurs
AMGN|Amgen|Santé
AMZN|Amazon|Distribution
AVGO|Broadcom|Semi-conducteurs
AXP|American Express|Finance
BA|Boeing|Aéronautique
BAC|Bank of America|Banque
BKNG|Booking Holdings|Loisirs
BLK|BlackRock|Finance
BMY|Bristol-Myers Squibb|Santé
BRK-B|Berkshire Hathaway|Finance
C|Citigroup|Banque
CAT|Caterpillar|Industrie
CMCSA|Comcast|Médias
COIN|Coinbase|Finance
COST|Costco|Distribution
CRM|Salesforce|Technologie
CSCO|Cisco|Technologie
CVS|CVS Health|Santé
CVX|Chevron|Énergie
DE|Deere|Industrie
DIS|Disney|Médias
F|Ford|Automobile
FDX|FedEx|Transport
GE|GE Aerospace|Aéronautique
GILD|Gilead|Santé
GM|General Motors|Automobile
GOOGL|Alphabet (Google)|Technologie
GS|Goldman Sachs|Banque
HD|Home Depot|Distribution
HON|Honeywell|Industrie
IBM|IBM|Technologie
INTC|Intel|Semi-conducteurs
INTU|Intuit|Technologie
JNJ|Johnson & Johnson|Santé
JPM|JPMorgan Chase|Banque
KO|Coca-Cola|Boissons
LLY|Eli Lilly|Santé
LMT|Lockheed Martin|Défense
LOW|Lowe's|Distribution
LRCX|Lam Research|Semi-conducteurs
MA|Mastercard|Paiement
MCD|McDonald's|Restauration
MDT|Medtronic|Santé
META|Meta (Facebook)|Technologie
MRK|Merck & Co|Santé
MS|Morgan Stanley|Banque
MSFT|Microsoft|Technologie
MU|Micron|Semi-conducteurs
NFLX|Netflix|Médias
NKE|Nike|Consommation
NOW|ServiceNow|Technologie
NVDA|Nvidia|Semi-conducteurs
ORCL|Oracle|Technologie
PEP|PepsiCo|Boissons
PFE|Pfizer|Santé
PG|Procter & Gamble|Consommation
PLTR|Palantir|Technologie
PYPL|PayPal|Paiement
QCOM|Qualcomm|Semi-conducteurs
RTX|RTX|Défense
SBUX|Starbucks|Restauration
SHOP|Shopify|Technologie
SNOW|Snowflake|Technologie
SPOT|Spotify|Médias
T|AT&T|Télécoms
TGT|Target|Distribution
TMO|Thermo Fisher|Santé
TSLA|Tesla|Automobile
TSM|TSMC (ADR)|Semi-conducteurs
TXN|Texas Instruments|Semi-conducteurs
UBER|Uber|Transport
UNH|UnitedHealth|Santé
UPS|UPS|Transport
V|Visa|Paiement
VZ|Verizon|Télécoms
WFC|Wells Fargo|Banque
WMT|Walmart|Distribution
XOM|ExxonMobil|Énergie
BABA|Alibaba (ADR)|Distribution
BMO.TO|Banque de Montréal|Banque
BNS.TO|Banque Scotia|Banque
CNR.TO|Canadien National|Transport
CP.TO|Canadien Pacifique Kansas City|Transport
ENB.TO|Enbridge|Énergie
RY.TO|Banque Royale du Canada|Banque
SHOP.TO|Shopify (Toronto)|Technologie
SU.TO|Suncor|Énergie
TD.TO|Banque TD|Banque
4063.T|Shin-Etsu Chemical|Chimie
4502.T|Takeda|Santé
6098.T|Recruit|Services
6501.T|Hitachi|Industrie
6758.T|Sony|Électronique
6861.T|Keyence|Électronique
6902.T|Denso|Automobile
7203.T|Toyota|Automobile
7267.T|Honda|Automobile
7751.T|Canon|Électronique
7974.T|Nintendo|Jeux vidéo
8035.T|Tokyo Electron|Semi-conducteurs
8306.T|Mitsubishi UFJ|Banque
9432.T|NTT|Télécoms
9983.T|Fast Retailing (Uniqlo)|Distribution
9984.T|SoftBank Group|Technologie
0005.HK|HSBC (Hong Kong)|Banque
0388.HK|Hong Kong Exchanges|Finance
0700.HK|Tencent|Technologie
0883.HK|CNOOC|Énergie
0941.HK|China Mobile|Télécoms
1211.HK|BYD|Automobile
1299.HK|AIA|Assurance
1810.HK|Xiaomi|Électronique
2318.HK|Ping An|Assurance
3690.HK|Meituan|Technologie
9618.HK|JD.com|Distribution
9988.HK|Alibaba (Hong Kong)|Distribution
600519.SS|Kweichow Moutai|Boissons
600036.SS|China Merchants Bank|Banque
300750.SZ|CATL|Industrie
2330.TW|TSMC|Semi-conducteurs
2317.TW|Hon Hai (Foxconn)|Électronique
005930.KS|Samsung Electronics|Électronique
000660.KS|SK Hynix|Semi-conducteurs
005380.KS|Hyundai Motor|Automobile
035420.KS|Naver|Technologie
BHARTIARTL.NS|Bharti Airtel|Télécoms
HDFCBANK.NS|HDFC Bank|Banque
ICICIBANK.NS|ICICI Bank|Banque
INFY.NS|Infosys|Technologie
ITC.NS|ITC|Consommation
LT.NS|Larsen & Toubro|Construction
RELIANCE.NS|Reliance Industries|Énergie
SBIN.NS|State Bank of India|Banque
TCS.NS|Tata Consultancy Services|Technologie
ANZ.AX|ANZ|Banque
BHP.AX|BHP|Matériaux
CBA.AX|Commonwealth Bank|Banque
CSL.AX|CSL|Santé
FMG.AX|Fortescue|Matériaux
MQG.AX|Macquarie|Finance
NAB.AX|National Australia Bank|Banque
WBC.AX|Westpac|Banque
WDS.AX|Woodside Energy|Énergie
WES.AX|Wesfarmers|Distribution
ABEV3.SA|Ambev|Boissons
ITUB4.SA|Itaú Unibanco|Banque
PETR4.SA|Petrobras|Énergie
VALE3.SA|Vale|Matériaux
WEGE3.SA|WEG|Industrie
WALMEX.MX|Walmart de México|Distribution
MTN.JO|MTN Group|Télécoms
NPN.JO|Naspers|Technologie
CW8.PA|Amundi MSCI World (ETF)|ETF
C40.PA|Amundi CAC 40 (ETF)|ETF
PANX.PA|Amundi Nasdaq-100 PEA (ETF)|ETF
ESE.PA|BNP Paribas Easy S&P 500 (ETF)|ETF
IWDA.AS|iShares Core MSCI World (ETF)|ETF
VWCE.DE|Vanguard FTSE All-World (ETF)|ETF
SPY|SPDR S&P 500 (ETF)|ETF
QQQ|Invesco QQQ Nasdaq-100 (ETF)|ETF
VT|Vanguard Total World (ETF)|ETF
"""

CATALOGUE: dict[str, dict] = {}
for _ligne in _BRUT.strip().splitlines():
    _sym, _nom, _secteur = _ligne.split("|")
    CATALOGUE[_sym] = dict(nom=_nom, secteur=_secteur)
