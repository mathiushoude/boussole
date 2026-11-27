"""Actualités financières en temps réel, issues de sources reconnues.

Deux canaux sont combinés puis dédoublonnés et triés du plus récent au plus ancien :
  1. le fil Yahoo Finance de la valeur (bibliothèque yfinance) ;
  2. la recherche Google Actualités (flux RSS public, édition française), filtrée sur une
     liste blanche de médias financiers (Les Echos, Boursorama, Zonebourse, Reuters...).
Chaque article garde sa source, son heure de publication et le lien vers l'original.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCES_FIABLES = [
    "Les Echos", "Investir", "Boursorama", "Zonebourse", "MarketScreener", "Reuters", "Bloomberg", "AFP",
    "BFM", "Le Figaro", "La Tribune", "L'Agefi", "Agefi", "Capital", "Boursier.com", "Cercle Finance",
    "ABC Bourse", "Le Revenu", "Le Monde", "Challenges", "L'Usine Nouvelle", "Mieux Vivre Votre Argent",
    "Financial Times", "Wall Street Journal", "WSJ", "CNBC", "MarketWatch", "Barron's", "Morningstar",
    "Yahoo Finance", "Associated Press", "The Economist", "Franceinfo", "Les Echos Investir", "Option Finance",
]

_HAUSSE = ["hausse", "bondit", "grimpe", "progresse", "record", "relève", "rehausse", "dépasse", "solide",
           "surperforme", "rachat d'actions", "acquisition", "croissance", "bénéfice en hausse", "relevé",
           "beats", "surge", "jumps", "rises", "upgrade", "record high", "raises", "soars", "gains", "rally"]
_BAISSE = ["baisse", "recule", "chute", "plonge", "abaisse", "avertissement", "dégrade", "décroche", "perte",
           "sanction", "enquête", "amende", "grève", "ralentit", "déçoit", "repli", "cède", "s'effondre",
           "misses", "falls", "drops", "slumps", "downgrade", "cuts", "warning", "plunges", "probe", "lawsuit"]


def source_fiable(nom: str) -> bool:
    n = (nom or "").lower()
    return any(s.lower() in n for s in SOURCES_FIABLES)


def tonalite(titre: str) -> int:
    """Estimation automatique et prudente du ton d'un titre : +1, 0 ou −1."""
    t = (titre or "").lower()
    p = sum(m in t for m in _HAUSSE)
    n = sum(m in t for m in _BAISSE)
    return 1 if p > n else -1 if n > p else 0


def _get(url: str, timeout: float = 8.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Boussole; usage personnel)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (URL construite ici)
        return r.read()


def lire_rss_google(xml: bytes) -> list[dict]:
    """Analyse un flux RSS Google Actualités."""
    items = []
    racine = ET.fromstring(xml)
    for it in racine.iter("item"):
        titre = (it.findtext("title") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        if source and titre.endswith(" - " + source):
            titre = titre[: -len(source) - 3].strip()
        try:
            date = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=dt.timezone.utc)
        items.append(dict(titre=titre, source=source, date=date, lien=(it.findtext("link") or "").strip()))
    return items


def google_actualites(requete: str, jours: int = 7) -> list[dict]:
    q = urllib.parse.quote(f"{requete} when:{jours}d")
    url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=FR&ceid=FR:fr"
    return lire_rss_google(_get(url))


def lire_yahoo(brut: list) -> list[dict]:
    """Convertit le fil `yfinance.Ticker.news` (ancien et nouveau format)."""
    items = []
    for it in brut or []:
        c = it.get("content", it)
        titre = c.get("title") or ""
        prov = c.get("provider") or {}
        source = prov.get("displayName") if isinstance(prov, dict) else None
        source = source or c.get("publisher") or "Yahoo Finance"
        if c.get("pubDate"):
            date = dt.datetime.fromisoformat(str(c["pubDate"]).replace("Z", "+00:00"))
        elif c.get("providerPublishTime"):
            date = dt.datetime.fromtimestamp(int(c["providerPublishTime"]), tz=dt.timezone.utc)
        else:
            continue
        lien = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
                or c.get("link") or "")
        if titre:
            items.append(dict(titre=titre, source=source, date=date, lien=lien))
    return items


def _cle(titre: str) -> str:
    return re.sub(r"[^a-z0-9]", "", titre.lower())[:60]


def fusionner(*listes: list[dict], n: int = 10, fiables_seulement: bool = True) -> list[dict]:
    vus, out = set(), []
    for it in sorted((x for lst in listes for x in lst), key=lambda x: x["date"], reverse=True):
        if fiables_seulement and not source_fiable(it["source"]):
            continue
        k = _cle(it["titre"])
        if k in vus:
            continue
        vus.add(k)
        out.append(dict(it, tonalite=tonalite(it["titre"])))
        if len(out) >= n:
            break
    return out


def actualites(ticker: str, nom: str, n: int = 10) -> tuple[list[dict], list[str]]:
    """Actualités récentes d'une valeur. Retourne (articles, erreurs rencontrées)."""
    erreurs, yahoo, google = [], [], []
    try:
        import yfinance as yf
        yahoo = lire_yahoo(yf.Ticker(ticker).news)
    except Exception as exc:  # réseau, quota...
        erreurs.append(f"Yahoo Finance : {type(exc).__name__}")
    try:
        google = google_actualites(f'"{nom}" bourse OR action OR résultats')
    except Exception as exc:
        erreurs.append(f"Google Actualités : {type(exc).__name__}")
    return fusionner(yahoo, google, n=n), erreurs


def il_y_a(date: dt.datetime, maintenant: dt.datetime | None = None) -> str:
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    s = (maintenant - date).total_seconds()
    if s < 60:
        return "à l'instant"
    if s < 3600:
        return f"il y a {int(s // 60)} min"
    if s < 86400:
        return f"il y a {int(s // 3600)} h"
    if s < 2 * 86400:
        return "hier"
    if s < 7 * 86400:
        return f"il y a {int(s // 86400)} jours"
    return date.astimezone().strftime("%d/%m/%Y")
