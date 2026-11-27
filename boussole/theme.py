"""Jetons de design de la charte graphique Boussole v3 (rôles de couleur clair / sombre).

Les écrans ne lisent que des rôles : changer de mode ne change que ces valeurs.
"""
from __future__ import annotations

CLAIR = {
    "bg": "#F7F8FA", "surface": "#FFFFFF", "text": "#0F172A", "muted": "#5B6B82", "border": "#E2E6EC",
    "accent": "#3B5BDB", "buy": "#0B7D55", "sell": "#CF2A30", "wait": "#9A6208", "ontint": "#FFFFFF",
}
SOMBRE = {
    "bg": "#0B1220", "surface": "#141C2E", "text": "#F1F5F9", "muted": "#94A3B8", "border": "#243049",
    "accent": "#7C93FF", "buy": "#34D399", "sell": "#FF6B6B", "wait": "#F5B83D", "ontint": "#0B1220",
}

MODES = ["Sombre", "Clair"]


def jetons(mode: str, systeme: str | None = None) -> dict:
    """Jetons du mode demandé ; « Automatique » suit le réglage du navigateur / système."""
    if mode == "Clair":
        return dict(CLAIR, nom="clair")
    if mode == "Sombre":
        return dict(SOMBRE, nom="sombre")
    return dict(CLAIR, nom="clair") if systeme == "light" else dict(SOMBRE, nom="sombre")


def rgba(hexa: str, a: float) -> str:
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


def _options(t: dict) -> dict:
    return {"primaryColor": t["accent"], "backgroundColor": t["bg"], "secondaryBackgroundColor": t["surface"],
            "textColor": t["text"], "borderColor": t["border"], "linkColor": t["accent"],
            "redColor": t["sell"], "greenColor": t["buy"]}


def appliquer_streamlit(t: dict, automatique: bool = False) -> bool:
    """Aligne le thème des widgets Streamlit sur les rôles du mode courant.

    Le navigateur peut choisir la variante claire ou sombre de Streamlit selon le système : en mode forcé,
    les deux variantes reçoivent donc la même palette, sinon chacune reçoit la sienne (Automatique)."""
    from streamlit import config as _cfg
    valeurs: dict = {}
    if automatique:
        valeurs["theme.base"] = None
        for k in _options(CLAIR):
            valeurs[f"theme.{k}"] = None
        for k, v in _options(CLAIR).items():
            valeurs[f"theme.light.{k}"] = v
        for k, v in _options(SOMBRE).items():
            valeurs[f"theme.dark.{k}"] = v
    else:
        valeurs["theme.base"] = "dark" if t["nom"] == "sombre" else "light"
        for k, v in _options(t).items():
            valeurs[f"theme.{k}"] = v
            valeurs[f"theme.light.{k}"] = v
            valeurs[f"theme.dark.{k}"] = v
    change = False
    for cle, v in valeurs.items():
        try:
            if _cfg.get_option(cle) != v:
                _cfg.set_option(cle, v)
                change = True
        except Exception:  # option absente dans une ancienne version de Streamlit
            pass
    return change  # le nouveau thème est transmis au navigateur à l'exécution suivante
