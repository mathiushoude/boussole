"""Accès aux données de marché : Yahoo Finance (yfinance) par défaut.

- Les cours réels sont mis en cache localement (data/cache). Si Yahoo Finance est
  injoignable, l'application réutilise les derniers cours réels enregistrés et l'indique
  (« hors ligne, dernière mise à jour à ... »). Sans cache, elle affiche une erreur claire
  avec un bouton « Réessayer » : aucune donnée fictive n'est présentée comme réelle.
- Le mode « Démonstration » (données fictives, graine fixe) n'existe que sur demande
  explicite ; il sert aussi aux tests automatisés (EXG-R-01).
- Usage personnel, conformément aux conditions d'utilisation de Yahoo (EXG-D-01).
"""
from __future__ import annotations

import datetime as dt
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import JOURS_HISTORIQUE, JOURS_PAR_AN, PARIS, SEED, UNIVERS, aujourdhui, maintenant

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
YAHOO, DEMO = "Yahoo Finance", "Démonstration"
SOURCES = [YAHOO, DEMO]
MIN_SEANCES = 80


class DonneesIndisponibles(RuntimeError):
    """Yahoo Finance est injoignable et aucun cours réel n'est en cache."""


@dataclass
class Cours:
    prix: pd.DataFrame            # clôtures ajustées, une colonne par titre
    source: str                   # YAHOO ou DEMO
    maj: dt.datetime              # heure de la dernière mise à jour réussie
    hors_ligne: bool = False      # True si l'on réutilise le cache faute de réseau
    message: str = ""
    devises: dict | None = None   # devise de cotation d'origine par titre (cours convertis en euros)


def _graine(ticker: str) -> int:
    return SEED + zlib.crc32(ticker.encode()) % 100_000


def info_titre(ticker: str) -> dict:
    from .catalogue import CATALOGUE
    meta = UNIVERS.get(ticker)
    if meta:
        return meta
    cat = CATALOGUE.get(ticker) or {}
    return dict(nom=cat.get("nom", ticker), secteur=cat.get("secteur", "—"),
                prix0=100, vol=0.25, drift=0.05, ca=None, dpa=None, per=None, marge=None)


# --------------------------------------------------------------------------- #
# Mode démonstration (fictif, reproductible)
# --------------------------------------------------------------------------- #
def calendrier(fin: dt.date | None = None, n: int = JOURS_PAR_AN + JOURS_HISTORIQUE) -> pd.DatetimeIndex:
    return pd.bdate_range(end=pd.Timestamp(fin or aujourdhui()).normalize(), periods=n)


def simuler_cours(ticker: str, dates: pd.DatetimeIndex) -> pd.Series:
    meta = info_titre(ticker)
    rng = np.random.default_rng(_graine(ticker))
    n = len(dates)
    vol_j = meta["vol"] / np.sqrt(252)
    tendance = np.zeros(n)
    for i in range(1, n):
        tendance[i] = 0.95 * tendance[i - 1] + rng.normal(0, 0.0008)
    chocs = rng.random(n) < 0.012
    rendements = meta["drift"] / 252 + tendance + rng.normal(0, vol_j, n) + rng.normal(0, 4 * vol_j, n) * chocs
    rendements[0] = 0.0
    return pd.Series(np.round(meta["prix0"] * np.exp(np.cumsum(rendements)), 2), index=dates, name=ticker)


def cours_simules(tickers: list[str], fin: dt.date | None = None) -> pd.DataFrame:
    dates = calendrier(fin)
    return pd.concat([simuler_cours(t, dates) for t in tickers], axis=1)


# --------------------------------------------------------------------------- #
# Yahoo Finance
# --------------------------------------------------------------------------- #
def _fichier_cache(tickers: list[str]) -> Path:
    return CACHE_DIR / f"cours_{'_'.join(sorted(tickers)).replace('^', '')}.csv"


def _cloture(brut: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    close = brut["Close"] if isinstance(brut.columns, pd.MultiIndex) else brut[["Close"]]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    if list(close.columns) == ["Close"]:
        close.columns = tickers[:1]
    return close


def devise_titre(ticker: str) -> str:
    """Devise de cotation (EUR, USD, GBp...) : Yahoo d'abord, puis la devise habituelle de la place."""
    from .config import place
    defaut = place(ticker)[3] or "EUR"
    if defaut == "EUR":
        return "EUR"
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        dev = t.fast_info.get("currency") if hasattr(t, "fast_info") else None
        return dev or (t.info or {}).get("currency") or defaut
    except Exception:
        return defaut


def convertir_en_euros(close: pd.DataFrame, devises: dict[str, str], taux) -> pd.DataFrame:
    """Convertit chaque colonne en euros. `taux(devise)` renvoie la série « 1 devise = x EUR »."""
    out = close.copy()
    for tk, dev in devises.items():
        if dev in (None, "", "EUR"):
            continue
        base, facteur = _base_devise(dev)   # cotations en centimes : GBp, ZAc…
        serie = taux(base)
        if serie is None or serie.dropna().empty:
            raise DonneesIndisponibles(f"Taux de change {base}/EUR introuvable pour convertir {tk} en euros.")
        serie = serie.reindex(out.index).ffill().bfill()
        out[tk] = out[tk] * serie * facteur
    return out


def _base_devise(dev: str) -> tuple[str, float]:
    """Devise de base et facteur (cotations en centimes : GBp, ZAc, ILA)."""
    facteur = 0.01 if dev in ("GBp", "GBX", "ZAc", "ILA") else 1.0
    return {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}.get(dev, dev), facteur


def marche_ouvert(ticker: str, maintenant: dt.datetime | None = None) -> bool:
    """Séance en cours sur la place du titre (horaires réguliers, du lundi au vendredi)."""
    from zoneinfo import ZoneInfo
    from .config import horaires
    tz, o, f = horaires(ticker)
    loc = (maintenant or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(tz))
    if loc.weekday() >= 5:
        return False
    hm = loc.strftime("%H:%M")
    return o <= hm < f


def cotations(tickers: list[str], devises: dict[str, str]) -> dict[str, dict]:
    """Dernier cours Yahoo Finance minute par minute (en euros) pour chaque titre.
    Renvoie {ticker: {prix, natif, devise, heure (Paris), jour (date locale de la place), ouvert, retard (min)}}.
    Lève DonneesIndisponibles si Yahoo ne répond pas."""
    import yfinance as yf
    from zoneinfo import ZoneInfo
    from .config import horaires
    from .config import place
    tickers = list(tickers)
    devises = {t: (devises.get(t) or place(t)[3] or "EUR") for t in tickers}
    paires = sorted({_base_devise(d)[0] for d in devises.values() if d and d != "EUR"})
    symboles = tickers + [f"{p}EUR=X" for p in paires]
    brut = yf.download(symboles, period="5d", interval="1m", auto_adjust=True, progress=False,
                       threads=True, timeout=10)
    if brut is None or brut.empty:
        raise DonneesIndisponibles("Yahoo Finance n'a renvoyé aucune cotation en direct.")
    close = _cloture(brut, symboles)
    idx = pd.to_datetime(close.index)
    close.index = idx.tz_localize("UTC") if idx.tz is None else idx
    fx = {}
    for p in paires:
        col = f"{p}EUR=X"
        serie = close[col].dropna() if col in close else pd.Series(dtype=float)
        fx[p] = float(serie.iloc[-1]) if len(serie) else None
    maintenant = dt.datetime.now(dt.timezone.utc)
    out = {}
    for t in tickers:
        if t not in close:
            continue
        serie = close[t].dropna()
        if serie.empty:
            continue
        ts, natif = serie.index[-1], float(serie.iloc[-1])
        dev = devises.get(t) or "EUR"
        prix = natif
        if dev != "EUR":
            base, facteur = _base_devise(dev)
            if not fx.get(base):
                continue
            prix = natif * fx[base] * facteur
        heure = (ts + pd.Timedelta(minutes=1)).tz_convert("Europe/Paris")     # fin de la bougie d'une minute
        out[t] = dict(prix=prix, natif=natif, devise=dev, heure=heure.to_pydatetime(),
                      jour=ts.tz_convert(ZoneInfo(horaires(t)[0])).date(),
                      ouvert=marche_ouvert(t, maintenant),
                      retard=max(0.0, (maintenant - heure.to_pydatetime()).total_seconds() / 60))
    return out


def indices_direct(symboles: list[str]) -> dict[str, dict]:
    """Niveau des indices minute par minute et variation depuis la clôture de la veille ; {} si indisponible."""
    import yfinance as yf
    symboles = list(symboles)
    if not symboles:
        return {}
    brut = yf.download(symboles, period="5d", interval="1m", auto_adjust=False, progress=False,
                       threads=True, timeout=10)
    if brut is None or brut.empty:
        return {}
    close = _cloture(brut, symboles)
    idx = pd.to_datetime(close.index)
    close.index = idx.tz_localize("UTC") if idx.tz is None else idx
    out = {}
    for s in symboles:
        if s not in close:
            continue
        x = close[s].dropna()
        if x.empty:
            continue
        jours = x.index.tz_convert("Europe/Paris").normalize()
        avant = x[jours < jours[-1]]
        prec = float(avant.iloc[-1]) if len(avant) else None
        out[s] = dict(niveau=float(x.iloc[-1]), variation=(float(x.iloc[-1]) / prec - 1) if prec else None,
                      heure=(x.index[-1] + pd.Timedelta(minutes=1)).tz_convert("Europe/Paris").to_pydatetime())
    return out


def appliquer_cotations(prix: pd.DataFrame, cot: dict[str, dict]) -> pd.DataFrame:
    """Remplace la clôture du jour par le dernier cours en direct (ou ajoute la séance du jour si
    l'historique quotidien ne la contient pas encore). Les jours antérieurs ne sont jamais modifiés."""
    if not cot:
        return prix
    out = prix.copy()
    for t, c in cot.items():
        if t not in out.columns:
            continue
        jour = pd.Timestamp(c["jour"])
        if jour < out.index[-1]:
            continue
        if jour not in out.index:
            out.loc[jour] = np.nan
            out = out.sort_index().ffill()
        out.loc[jour, t] = round(c["prix"], 4)
    return out


def _taux_yahoo(devise: str) -> pd.Series | None:
    import yfinance as yf
    brut = yf.download(f"{devise}EUR=X", period="5y", interval="1d", auto_adjust=True, progress=False, timeout=15)
    if brut is None or brut.empty:
        return None
    s = _cloture(brut, [f"{devise}EUR=X"]).iloc[:, 0].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s


def telecharger_yahoo(tickers: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    import yfinance as yf

    brut = yf.download(tickers, period="5y", interval="1d", auto_adjust=True, progress=False,
                       threads=True, timeout=15)
    if brut is None or brut.empty:
        raise DonneesIndisponibles("Yahoo Finance n'a renvoyé aucune donnée (connexion bloquée, service momentanément "
                                  "indisponible ou trop de requêtes).")
    close = _cloture(brut, tickers)
    manquants = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
    if manquants:
        raise DonneesIndisponibles(f"Aucun cours trouvé pour : {', '.join(manquants)}. "
                                   f"Vérifiez le symbole (ex. MC.PA pour LVMH sur Euronext Paris).")
    close = close[tickers].ffill().dropna()
    if len(close) < MIN_SEANCES:
        raise DonneesIndisponibles("Historique trop court pour calculer les indicateurs (moins de 80 séances).")
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    devises = {t: devise_titre(t) for t in tickers}
    close = convertir_en_euros(close, devises, _taux_yahoo)
    return close.tail(JOURS_PAR_AN + JOURS_HISTORIQUE).round(4), devises


def intraday(ticker: str, devise: str = "EUR") -> pd.Series | None:
    """Cours toutes les 5 minutes sur les 5 dernières séances (heure de Paris, en euros) ; None si indisponible."""
    try:
        import yfinance as yf
        brut = yf.download(ticker, period="5d", interval="5m", auto_adjust=True, progress=False, timeout=15)
        if brut is None or brut.empty:
            return None
        s = _cloture(brut, [ticker]).iloc[:, 0].dropna()
        idx = pd.to_datetime(s.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx
        s.index = idx.tz_convert("Europe/Paris").tz_localize(None)
        if devise not in (None, "", "EUR"):
            facteur = 0.01 if devise in ("GBp", "GBX", "ZAc", "ILA") else 1.0
            base = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}.get(devise, devise)
            taux = _taux_yahoo(base)
            if taux is None:
                return None
            s = s * float(taux.iloc[-1]) * facteur
        return s
    except Exception:
        return None


def rechercher_titres(requete: str, n: int = 8) -> list[dict]:
    """Recherche Yahoo Finance par nom ou symbole : actions et ETF de toutes les places de cotation."""
    requete = (requete or "").strip()
    if len(requete) < 2:
        return []
    quotes: list[dict] = []
    try:
        import yfinance as yf
        if hasattr(yf, "Search"):
            quotes = yf.Search(requete, max_results=n * 2, news_count=0).quotes or []
    except Exception:
        quotes = []
    if not quotes:
        try:
            import urllib.parse
            import urllib.request
            url = ("https://query2.finance.yahoo.com/v1/finance/search?"
                   + urllib.parse.urlencode({"q": requete, "quotesCount": n * 2, "newsCount": 0, "lang": "fr-FR"}))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Boussole; usage personnel)"})
            with urllib.request.urlopen(req, timeout=8) as r:
                quotes = json.loads(r.read().decode("utf-8")).get("quotes", [])
        except Exception:
            return []
    return lire_recherche(quotes)[:n]


def lire_recherche(quotes: list[dict]) -> list[dict]:
    out, vus = [], set()
    for q in quotes:
        sym, typ = q.get("symbol"), (q.get("quoteType") or "").upper()
        if not sym or typ not in ("EQUITY", "ETF") or sym in vus:
            continue
        vus.add(sym)
        out.append(dict(symbole=sym, nom=q.get("longname") or q.get("shortname") or sym,
                        bourse=q.get("exchDisp") or q.get("exchange") or "",
                        type="ETF" if typ == "ETF" else "Action", secteur=q.get("sectorDisp") or q.get("sector") or ""))
    return out


def charger_cours(tickers: list[str], source: str = YAHOO, fin: dt.date | None = None) -> Cours:
    tickers = list(tickers)
    if source == DEMO:
        return Cours(cours_simules(tickers, fin), DEMO, maintenant(),
                     message="Mode démonstration : cours fictifs, à ne pas utiliser pour décider.")
    fichier = _fichier_cache(tickers)
    try:
        prix, devises = telecharger_yahoo(tickers)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        prix.to_csv(fichier)
        maj = maintenant()
        fichier.with_suffix(".json").write_text(json.dumps({"maj": maj.isoformat(), "devises": devises}),
                                                encoding="utf-8")
        conv = [t for t, d in devises.items() if d not in ("EUR", None, "")]
        return Cours(prix, YAHOO, maj, devises=devises,
                     message="Cours Yahoo Finance (clôtures ajustées)."
                             + (f" Convertis en euros : {', '.join(conv)}." if conv else ""))
    except Exception as exc:
        if fichier.exists():
            prix = pd.read_csv(fichier, index_col=0, parse_dates=True)[tickers]
            devises = {}
            try:
                meta = json.loads(fichier.with_suffix(".json").read_text())
                maj = dt.datetime.fromisoformat(meta["maj"])
                devises = meta.get("devises") or {}
            except (OSError, ValueError, KeyError):
                maj = dt.datetime.fromtimestamp(fichier.stat().st_mtime, PARIS).replace(tzinfo=None)
            raison = str(exc) if isinstance(exc, DonneesIndisponibles) else type(exc).__name__
            return Cours(prix, YAHOO, maj, hors_ligne=True, devises=devises,
                         message=f"Yahoo Finance injoignable ({raison}) : derniers cours réels enregistrés "
                                 f"le {maj:%d/%m/%Y à %H:%M}.")
        if isinstance(exc, DonneesIndisponibles):
            raise
        raise DonneesIndisponibles(f"Connexion à Yahoo Finance impossible ({type(exc).__name__}).") from exc


def indices_pour(tickers: list[str]) -> list[tuple[str, str]]:
    """Indices de référence des places où sont cotées les valeurs choisies (symbole, nom), sans doublon."""
    from .config import place
    vus, out = set(), []
    for t in tickers:
        _, sym, nom, _ = place(t)
        if sym and sym not in vus:
            vus.add(sym)
            out.append((sym, nom))
            if sym == "^GSPC":
                vus.add("^IXIC")
                out.append(("^IXIC", "Nasdaq"))
    return out


def indice_marche(symbole: str = "^FCHI") -> dict | None:
    """Dernier niveau et variation de l'indice (CAC 40 par défaut) ; None si indisponible."""
    try:
        import yfinance as yf
        h = yf.Ticker(symbole).history(period="5d", interval="1d", auto_adjust=False)["Close"].dropna()
        if len(h) < 2:
            return None
        return dict(niveau=float(h.iloc[-1]), variation=float(h.iloc[-1] / h.iloc[-2] - 1),
                    date=pd.Timestamp(h.index[-1]).tz_localize(None))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Fondamentaux (EXG-F-05)
# --------------------------------------------------------------------------- #
INDICATEURS_FONDAMENTAUX = {
    "ca": "Chiffre d'affaires", "dpa": "Dividende par action", "rendement": "Rendement du dividende",
    "per": "PER (cours / bénéfice)", "marge": "Marge nette",
}


def fondamentaux_yahoo(ticker: str) -> dict:
    """Fondamentaux Yahoo Finance, mis en cache 24 h sur disque."""
    fichier = CACHE_DIR / f"fond_{ticker.replace('^', '')}.json"
    if fichier.exists() and (dt.datetime.now().timestamp() - fichier.stat().st_mtime) < 86400:
        return json.loads(fichier.read_text(encoding="utf-8"))
    import yfinance as yf
    info = yf.Ticker(ticker).info or {}
    res = dict(
        ca=info.get("totalRevenue"),
        dpa=info.get("dividendRate") or info.get("trailingAnnualDividendRate"),
        per=info.get("trailingPE"),
        marge=info.get("profitMargins"),
        nom=info.get("longName") or info.get("shortName"),
        secteur=info.get("sector"),
        devise=info.get("currency") or "EUR",
        prix_natif=info.get("currentPrice") or info.get("regularMarketPrice"),
        bourse=info.get("fullExchangeName") or info.get("exchange"),
        source="Yahoo Finance",
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(res), encoding="utf-8")
    return res


def fondamentaux(ticker: str, cours: float, source: str = YAHOO) -> dict:
    meta = info_titre(ticker)
    if source == DEMO:
        res = dict(ca=meta["ca"], dpa=meta["dpa"], per=meta["per"], marge=meta["marge"],
                   source="Valeurs indicatives (mode démonstration)", devise="EUR")
    else:
        try:
            res = fondamentaux_yahoo(ticker)
        except Exception:
            res = dict(ca=None, dpa=None, per=None, marge=None, source="Yahoo Finance indisponible", devise="EUR")
    res = dict(res)
    res["rendement"] = (res["dpa"] / cours) if (res.get("dpa") and cours) else (0.0 if res.get("dpa") == 0 else None)
    return res


def score_fondamental(f: dict) -> tuple[float, list[str]]:
    """Part des critères favorables, calculée sur les indicateurs disponibles."""
    criteres = [
        ("ca", lambda v: v >= 1e9, "CA supérieur à 1 Md"),
        ("dpa", lambda v: v > 0, "Dividende versé"),
        ("rendement", lambda v: v >= 0.02, "Rendement ≥ 2 %"),
        ("per", lambda v: 0 < v <= 25, "PER ≤ 25"),
        ("marge", lambda v: v >= 0.10, "Marge nette ≥ 10 %"),
    ]
    dispo = [(cle, test, txt) for cle, test, txt in criteres if f.get(cle) is not None]
    if not dispo:
        return 0.5, []
    ok = [txt for cle, test, txt in dispo if test(f[cle])]
    return len(ok) / len(dispo), ok


# --------------------------------------------------------------------------- #
# Actualités du mode démonstration (fictives, déduites des variations)
# --------------------------------------------------------------------------- #
_MODELES_HAUSSE = ["{nom} : les analystes relèvent leur objectif de cours",
                   "{nom} publie des ventes supérieures aux attentes",
                   "Le secteur {secteur} porté par une demande solide, {nom} en hausse",
                   "{nom} annonce un programme de rachat d'actions"]
_MODELES_BAISSE = ["{nom} recule après un avertissement sur les marges",
                   "Pression sur le secteur {secteur} : {nom} en baisse",
                   "{nom} : un courtier abaisse sa recommandation",
                   "Inquiétudes réglementaires autour de {nom}, le titre recule"]


def actualites_demo(ticker: str, cours: pd.Series, jusqu_a: int, n: int = 6) -> list[dict]:
    meta = info_titre(ticker)
    rdt = cours.iloc[: jusqu_a + 1].pct_change().dropna().tail(90)
    if rdt.empty:
        return []
    rng = np.random.default_rng(_graine(ticker) + 7)
    items = []
    for d in sorted(rdt.abs().sort_values(ascending=False).head(n).index, reverse=True):
        r = rdt.loc[d]
        modeles = _MODELES_HAUSSE if r > 0 else _MODELES_BAISSE
        items.append(dict(titre=modeles[int(rng.integers(len(modeles)))].format(**meta),
                          source="Démonstration (fictif)",
                          date=pd.Timestamp(d).tz_localize("Europe/Paris").to_pydatetime().replace(hour=9),
                          lien="", tonalite=1 if r > 0 else -1, variation=float(r)))
    return items
