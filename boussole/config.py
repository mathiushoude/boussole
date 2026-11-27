"""Paramètres par défaut et univers d'actions de Boussole."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

SEED = 42  # graine aléatoire fixe (EXG-R-01)


# Heure de référence de l'application : la France (UTC+1 en hiver, UTC+2 en été), quel que soit l'ordinateur.
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    PARIS = _ZoneInfo("Europe/Paris")
except Exception:                      # Windows sans le paquet tzdata : repli sur dateutil (fourni avec pandas)
    from dateutil import tz as _tz
    PARIS = _tz.gettz("Europe/Paris")


def maintenant():
    """Date et heure actuelles à Paris (sans fuseau attaché, pour l'affichage et l'enregistrement)."""
    import datetime as _dt
    return _dt.datetime.now(PARIS).replace(tzinfo=None)


def aujourdhui():
    return maintenant().date()
CAPITAL_INITIAL = 500_000.0
JOURS_PAR_AN = 252
JOURS_HISTORIQUE = 520  # historique avant le début de l'année (MM50, RSI et graphiques sur 2 ans)
MAX_ACTIONS = 10       # nombre maximal de valeurs suivies

# Univers proposé : grandes capitalisations européennes (tickers Yahoo Finance).
# "prix0", "vol", "drift" et les fondamentaux ne servent qu'au mode démonstration
# (valeurs indicatives, arrondies, à ne pas utiliser comme données de référence).
UNIVERS: dict[str, dict] = {
    "RMS.PA": dict(nom="Hermès", secteur="Luxe", prix0=2100, vol=0.25, drift=0.08,
                   ca=15.2e9, dpa=16.0, per=48.0, marge=0.31),
    "DSY.PA": dict(nom="Dassault Systèmes", secteur="Technologie", prix0=33, vol=0.28, drift=0.05,
                   ca=6.2e9, dpa=0.26, per=30.0, marge=0.19),
    "CAP.PA": dict(nom="Capgemini", secteur="Technologie", prix0=170, vol=0.27, drift=0.04,
                   ca=22.1e9, dpa=3.4, per=16.0, marge=0.07),
    "MC.PA": dict(nom="LVMH", secteur="Luxe", prix0=690, vol=0.27, drift=0.06,
                  ca=84.7e9, dpa=13.0, per=24.0, marge=0.15),
    "TTE.PA": dict(nom="TotalEnergies", secteur="Énergie", prix0=58, vol=0.22, drift=0.05,
                   ca=195e9, dpa=3.2, per=8.5, marge=0.08),
    "SAN.PA": dict(nom="Sanofi", secteur="Santé", prix0=92, vol=0.19, drift=0.04,
                   ca=43e9, dpa=3.9, per=15.0, marge=0.13),
    "AIR.PA": dict(nom="Airbus", secteur="Aéronautique", prix0=150, vol=0.28, drift=0.09,
                   ca=69e9, dpa=2.0, per=27.0, marge=0.06),
    "OR.PA": dict(nom="L'Oréal", secteur="Cosmétiques", prix0=380, vol=0.21, drift=0.05,
                  ca=43e9, dpa=7.0, per=30.0, marge=0.14),
    "BNP.PA": dict(nom="BNP Paribas", secteur="Banque", prix0=64, vol=0.26, drift=0.06,
                   ca=48e9, dpa=4.8, per=7.0, marge=0.24),
    "SU.PA": dict(nom="Schneider Electric", secteur="Industrie", prix0=230, vol=0.25, drift=0.10,
                  ca=38e9, dpa=3.9, per=29.0, marge=0.11),
    "AI.PA": dict(nom="Air Liquide", secteur="Chimie", prix0=170, vol=0.17, drift=0.06,
                  ca=27e9, dpa=3.3, per=27.0, marge=0.12),
    "BN.PA": dict(nom="Danone", secteur="Agroalimentaire", prix0=66, vol=0.16, drift=0.03,
                  ca=27.4e9, dpa=2.15, per=20.0, marge=0.07),
    "ORA.PA": dict(nom="Orange", secteur="Télécoms", prix0=11, vol=0.17, drift=0.02,
                   ca=40e9, dpa=0.75, per=13.0, marge=0.06),
    # Grandes valeurs mondiales (suggestions ; toute autre valeur se trouve par la recherche)
    "AAPL": dict(nom="Apple", secteur="Technologie", prix0=190, vol=0.26, drift=0.10,
                 ca=390e9, dpa=1.0, per=31.0, marge=0.24),
    "MSFT": dict(nom="Microsoft", secteur="Logiciels", prix0=380, vol=0.24, drift=0.11,
                 ca=245e9, dpa=3.0, per=35.0, marge=0.36),
    "NVDA": dict(nom="NVIDIA", secteur="Semi-conducteurs", prix0=110, vol=0.48, drift=0.20,
                 ca=130e9, dpa=0.04, per=45.0, marge=0.55),
    "AMZN": dict(nom="Amazon", secteur="Distribution en ligne", prix0=170, vol=0.32, drift=0.10,
                 ca=640e9, dpa=0.0, per=38.0, marge=0.09),
    "SAP.DE": dict(nom="SAP", secteur="Logiciels", prix0=210, vol=0.25, drift=0.10,
                   ca=34e9, dpa=2.35, per=40.0, marge=0.10),
    "SIE.DE": dict(nom="Siemens", secteur="Industrie", prix0=170, vol=0.24, drift=0.07,
                   ca=76e9, dpa=5.2, per=18.0, marge=0.11),
    "ASML.AS": dict(nom="ASML", secteur="Semi-conducteurs", prix0=650, vol=0.35, drift=0.10,
                    ca=28e9, dpa=6.4, per=33.0, marge=0.27),
    "NESN.SW": dict(nom="Nestlé", secteur="Agroalimentaire", prix0=90, vol=0.15, drift=0.02,
                    ca=91e9, dpa=3.0, per=19.0, marge=0.12),
    "SHEL.L": dict(nom="Shell", secteur="Énergie", prix0=28, vol=0.23, drift=0.05,
                   ca=290e9, dpa=1.3, per=12.0, marge=0.06),
    "AZN.L": dict(nom="AstraZeneca", secteur="Santé", prix0=125, vol=0.21, drift=0.07,
                  ca=54e9, dpa=2.8, per=30.0, marge=0.13),
    "7203.T": dict(nom="Toyota", secteur="Automobile", prix0=17, vol=0.27, drift=0.06,
                   ca=290e9, dpa=0.5, per=9.0, marge=0.10),
    "0700.HK": dict(nom="Tencent", secteur="Internet", prix0=45, vol=0.33, drift=0.08,
                    ca=85e9, dpa=0.45, per=22.0, marge=0.29),
}

# Places de cotation : suffixe Yahoo → (bourse, indice de référence, nom de l'indice, devise par défaut)
PLACES: dict[str, tuple[str, str, str, str]] = {
    ".PA": ("Euronext Paris", "^FCHI", "CAC 40", "EUR"),
    ".AS": ("Euronext Amsterdam", "^AEX", "AEX", "EUR"),
    ".BR": ("Euronext Bruxelles", "^BFX", "BEL 20", "EUR"),
    ".LS": ("Euronext Lisbonne", "PSI20.LS", "PSI", "EUR"),
    ".MI": ("Borsa Italiana", "FTSEMIB.MI", "FTSE MIB", "EUR"),
    ".MC": ("Bourse de Madrid", "^IBEX", "IBEX 35", "EUR"),
    ".DE": ("Xetra Francfort", "^GDAXI", "DAX", "EUR"),
    ".F": ("Bourse de Francfort", "^GDAXI", "DAX", "EUR"),
    ".L": ("Bourse de Londres", "^FTSE", "FTSE 100", "GBp"),
    ".SW": ("SIX Zurich", "^SSMI", "SMI", "CHF"),
    ".ST": ("Nasdaq Stockholm", "^OMX", "OMXS30", "SEK"),
    ".CO": ("Nasdaq Copenhague", "^OMXC25", "OMXC25", "DKK"),
    ".OL": ("Bourse d'Oslo", "OBX.OL", "OBX", "NOK"),
    ".HE": ("Nasdaq Helsinki", "^OMXH25", "OMXH25", "EUR"),
    ".TW": ("Bourse de Taïwan", "^TWII", "TAIEX", "TWD"),
    ".T": ("Bourse de Tokyo", "^N225", "Nikkei 225", "JPY"),
    ".HK": ("Bourse de Hong Kong", "^HSI", "Hang Seng", "HKD"),
    ".SS": ("Bourse de Shanghai", "000001.SS", "SSE Composite", "CNY"),
    ".SZ": ("Bourse de Shenzhen", "399001.SZ", "SZSE Component", "CNY"),
    ".KS": ("Bourse de Corée", "^KS11", "KOSPI", "KRW"),
    ".NS": ("NSE Inde", "^NSEI", "Nifty 50", "INR"),
    ".BO": ("BSE Inde", "^BSESN", "Sensex", "INR"),
    ".TO": ("Bourse de Toronto", "^GSPTSE", "S&P/TSX", "CAD"),
    ".AX": ("ASX Sydney", "^AXJO", "S&P/ASX 200", "AUD"),
    ".SA": ("B3 São Paulo", "^BVSP", "Ibovespa", "BRL"),
    ".MX": ("Bourse de Mexico", "^MXX", "IPC", "MXN"),
    ".JO": ("Bourse de Johannesburg", "^J203.JO", "JSE All Share", "ZAc"),
    "": ("New York (NYSE / Nasdaq)", "^GSPC", "S&P 500", "USD"),
}


def place(ticker: str) -> tuple[str, str, str, str]:
    """Bourse, indice, nom de l'indice et devise probable d'un symbole Yahoo."""
    t = ticker.upper()
    if "." in t:
        suffixe = "." + t.rsplit(".", 1)[1]
        if suffixe in PLACES:
            return PLACES[suffixe]
        return ("Autre place", "", "", "")
    return PLACES[""]

# Horaires de séance (fuseau, ouverture, fermeture), heure locale de la place. Jours fériés non gérés :
# si aucun cours n'arrive pendant une séance supposée ouverte, l'interface l'indique.
HORAIRES: dict[str, tuple[str, str, str]] = {
    ".PA": ("Europe/Paris", "09:00", "17:30"), ".AS": ("Europe/Amsterdam", "09:00", "17:30"),
    ".BR": ("Europe/Brussels", "09:00", "17:30"), ".LS": ("Europe/Lisbon", "08:00", "16:30"),
    ".MI": ("Europe/Rome", "09:00", "17:30"), ".MC": ("Europe/Madrid", "09:00", "17:30"),
    ".DE": ("Europe/Berlin", "09:00", "17:30"), ".F": ("Europe/Berlin", "08:00", "20:00"),
    ".L": ("Europe/London", "08:00", "16:30"), ".SW": ("Europe/Zurich", "09:00", "17:30"),
    ".ST": ("Europe/Stockholm", "09:00", "17:30"), ".CO": ("Europe/Copenhagen", "09:00", "17:00"),
    ".OL": ("Europe/Oslo", "09:00", "16:20"), ".HE": ("Europe/Helsinki", "10:00", "18:30"),
    ".TW": ("Asia/Taipei", "09:00", "13:30"), ".T": ("Asia/Tokyo", "09:00", "15:30"),
    ".HK": ("Asia/Hong_Kong", "09:30", "16:00"), ".SS": ("Asia/Shanghai", "09:30", "15:00"),
    ".SZ": ("Asia/Shanghai", "09:30", "15:00"), ".KS": ("Asia/Seoul", "09:00", "15:30"),
    ".NS": ("Asia/Kolkata", "09:15", "15:30"), ".BO": ("Asia/Kolkata", "09:15", "15:30"),
    ".TO": ("America/Toronto", "09:30", "16:00"), ".AX": ("Australia/Sydney", "10:00", "16:00"),
    ".SA": ("America/Sao_Paulo", "10:00", "17:00"), ".MX": ("America/Mexico_City", "08:30", "15:00"),
    ".JO": ("Africa/Johannesburg", "09:00", "17:00"), "": ("America/New_York", "09:30", "16:00"),
}


def horaires(ticker: str) -> tuple[str, str, str]:
    t = ticker.upper()
    suffixe = "." + t.rsplit(".", 1)[1] if "." in t else ""
    return HORAIRES.get(suffixe, HORAIRES[".PA"] if suffixe else HORAIRES[""])


ACTIONS_PAR_DEFAUT = ["RMS.PA", "DSY.PA", "CAP.PA", "TTE.PA", "AI.PA"]   # Hermès, Dassault Systèmes, Capgemini, TotalEnergies, Air Liquide


@dataclass
class Regles:
    """Seuils de décision, modifiables dans l'onglet « Budget et règles »."""
    stop_loss: float = 0.05            # EXG-F-12
    take_profit: float = 0.10          # EXG-F-13
    trailing_declenchement: float = 0.05  # EXG-F-14 (gain atteint)
    trailing_repli: float = 0.03       # EXG-F-14 (baisse depuis le plus haut)
    rsi_surachat: float = 70.0         # EXG-F-15
    rsi_survente: float = 30.0         # EXG-F-18
    mm_courte: int = 20                # EXG-F-17
    mm_longue: int = 50
    alerte_perte_hebdo: float = 0.05   # EXG-F-22
    suspension_perte_hebdo: float = 0.10  # EXG-F-23
    securisation_gain_hebdo: float = 0.10  # EXG-F-24
    objectif_hebdo: float = 0.10
    tolerance_hebdo: float = 0.10
    montant_achat_min: float = 1_000.0  # EXG-F-19
    part_achat: float = 0.5            # part des liquidités engagée par signal d'achat
    poids_max_ligne: float = 0.5       # poids maximal d'une valeur dans le portefeuille (profil de risque)
    vol_max: float = 0.5               # volatilité annuelle maximale pour un achat (profil de risque)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Regles":
        r = cls()
        for k, v in (d or {}).items():
            if hasattr(r, k):
                setattr(r, k, type(getattr(r, k))(v))
        return r


@dataclass
class Profil:
    """Préférences du client (aucune donnée personnelle sensible n'est stockée)."""
    nom_affiche: str = "Monsieur Dupont"   # « Prénom Nom »
    prenom: str = ""
    profil_risque: str = "Dynamique"
    horizon: str = "1 an"
    source_donnees: str = "Yahoo Finance"   # Yahoo Finance | Démonstration (données fictives)
    animations: bool = True
    mode: str = "Sombre"           # Sombre | Clair
    preferences: list = field(default_factory=lambda: ["Dividendes", "Grandes capitalisations"])
    questionnaire: dict = field(default_factory=dict)   # réponses au questionnaire de profil de risque
    historique: list = field(default_factory=list)      # évaluations successives (date, score, profil, motif)
    regles_auto: bool = True                            # règles calées sur le profil de risque
    aides: bool = True                                  # encadrés « comment lire cette page »
