"""Indicateurs techniques (EXG-F-06) : moyennes mobiles et RSI."""
from __future__ import annotations

import numpy as np
import pandas as pd


def moyenne_mobile(cours: pd.Series, n: int) -> pd.Series:
    return cours.rolling(n, min_periods=n).mean()


def rsi(cours: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder (lissage exponentiel alpha = 1/n)."""
    delta = cours.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    perte = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / perte.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(perte != 0, 100.0)
    return out.where(gain.notna())


def calculer(cours: pd.Series, mm_courte: int = 20, mm_longue: int = 50) -> pd.DataFrame:
    df = pd.DataFrame({"cours": cours})
    df["mm_courte"] = moyenne_mobile(cours, mm_courte)
    df["mm_longue"] = moyenne_mobile(cours, mm_longue)
    df["rsi"] = rsi(cours)
    ecart_type = cours.rolling(20, min_periods=20).std()
    base = moyenne_mobile(cours, 20)
    df["bb_haut"] = base + 2 * ecart_type      # Bollinger (2 sigma)
    df["bb_bas"] = base - 2 * ecart_type
    ema12 = cours.ewm(span=12, adjust=False).mean()
    ema26 = cours.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["support"] = cours.rolling(60, min_periods=20).min()
    df["resistance"] = cours.rolling(60, min_periods=20).max()
    df["volatilite"] = cours.pct_change().rolling(20, min_periods=10).std() * np.sqrt(252)
    return df


# ----------------------------------------------------------------- signaux --
def croisement_haussier(ind: pd.DataFrame, fenetre: int = 3) -> bool:
    """MM courte passée au-dessus de la MM longue lors des `fenetre` dernières séances."""
    ecart = (ind["mm_courte"] - ind["mm_longue"]).dropna()
    if len(ecart) < 2:
        return False
    recent = ecart.tail(fenetre + 1)
    return bool(recent.iloc[-1] > 0 and (recent.iloc[:-1] <= 0).any())


def croisement_baissier(ind: pd.DataFrame, fenetre: int = 3) -> bool:
    ecart = (ind["mm_courte"] - ind["mm_longue"]).dropna()
    if len(ecart) < 2:
        return False
    recent = ecart.tail(fenetre + 1)
    return bool(recent.iloc[-1] < 0 and (recent.iloc[:-1] >= 0).any())


def rebond_confirme(ind: pd.DataFrame, seuil: float = 30, fenetre: int = 5) -> bool:
    """RSI passé sous `seuil` récemment puis deux hausses consécutives du cours."""
    if len(ind) < 3 or ind["rsi"].tail(fenetre).isna().all():
        return False
    c = ind["cours"].values
    r = ind["rsi"].values
    return bool(np.nanmin(r[-fenetre:]) < seuil and c[-1] > c[-2] > c[-3] and r[-1] > r[-2])


def retournement_baissier(ind: pd.DataFrame, seuil: float = 70, fenetre: int = 5) -> bool:
    """RSI passé au-dessus de `seuil` récemment puis deux baisses consécutives du cours."""
    if len(ind) < 3 or ind["rsi"].tail(fenetre).isna().all():
        return False
    c = ind["cours"].values
    r = ind["rsi"].values
    return bool(np.nanmax(r[-fenetre:]) > seuil and c[-1] < c[-2] < c[-3] and r[-1] < r[-2])


def etat_technique(ind: pd.DataFrame, rsi_bas: float = 30, rsi_haut: float = 70) -> str:
    """'favorable', 'defavorable' ou 'neutre' à la dernière séance."""
    d = ind.iloc[-1]
    if pd.isna(d["mm_longue"]) or pd.isna(d["rsi"]):
        return "neutre"
    hausse = d["mm_courte"] > d["mm_longue"] and d["cours"] > d["mm_longue"]
    baisse = d["mm_courte"] < d["mm_longue"] and d["cours"] < d["mm_longue"]
    if hausse and rsi_bas + 10 <= d["rsi"] <= rsi_haut:
        return "favorable"
    if baisse:
        return "defavorable"
    return "neutre"
