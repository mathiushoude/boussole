"""Jauge de décision (charte v3) : score de −100 à +100, confiance et six piliers.

La décision (Acheter / Attendre / Vendre) vient toujours du moteur de règles
(`rules.py`) ; le score la situe dans sa zone de la jauge :
Vendre de −100 à −34, Attendre de −33 à +33, Acheter de +34 à +100.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Regles
from .rules import ACHETER, VENDRE, Recommandation

PILIERS = ["Actualités", "Analyse financière", "Hasard (risque)", "Graphique", "Indicateurs", "Ratios"]
REGLES_PROTECTION = {"EXG-F-12", "EXG-F-13", "EXG-F-14", "EXG-F-15", "EXG-F-23", "EXG-F-24"}


def _borne(x: float) -> int:
    return int(round(float(np.clip(np.nan_to_num(x), -100, 100))))


def _eur(v: float) -> str:
    return f"{v:,.2f}".replace(",", "\u202f").replace(".", ",") + "\u202f€"


def _pc(v: float) -> str:
    return f"{v * 100:+.1f}".replace(".", ",").replace("-", "−") + "\u202f%"


@dataclass
class Signal:
    code: int
    score: int
    confiance: int
    piliers: dict[str, int]
    raisons: list[tuple[str, str]]
    stop_loss: str


def piliers(ind: pd.DataFrame, fond: dict, actus: list[dict]) -> dict[str, int]:
    d = ind.iloc[-1]
    cours = float(d["cours"])
    # Actualités : tonalité moyenne, les plus récentes pèsent davantage.
    tons = [n.get("tonalite", 0) for n in actus]
    poids = np.linspace(1.0, 0.4, len(tons)) if tons else []
    act = 100 * float(np.dot(tons, poids) / np.sum(poids)) * 0.8 if tons else 0
    # Analyse financière : part des critères fondamentaux favorables.
    fin = fond.get("score", 0.5) * 200 - 100
    # Hasard : volatilité annualisée sur 20 séances (faible = favorable).
    vol = d.get("volatilite", np.nan)
    hasard = (0.25 - vol) / 0.15 * 100 if pd.notna(vol) else 0
    # Graphique : écart entre moyennes mobiles et position du cours.
    graph = 0
    if pd.notna(d["mm_longue"]):
        graph = (d["mm_courte"] / d["mm_longue"] - 1) * 1500 + (cours / d["mm_longue"] - 1) * 600
    # Indicateurs : RSI (élan, pénalisé en surachat) et histogramme MACD.
    rsi = d["rsi"]
    if pd.isna(rsi):
        r = 0
    elif rsi > 70:
        r = -50
    elif rsi < 30:
        r = 50
    else:
        r = (rsi - 50) * 2.5
    m = d["macd_hist"] / cours * 20000 if pd.notna(d.get("macd_hist")) else 0
    indic = (r + np.clip(m, -100, 100)) / 2
    # Ratios : PER et rendement du dividende.
    parts = []
    if fond.get("per") is not None:
        parts.append(np.clip((20 - fond["per"]) * 6, -100, 100))
    if fond.get("rendement") is not None:
        parts.append(np.clip((fond["rendement"] - 0.02) * 4000, -100, 100))
    ratios = float(np.mean(parts)) if parts else 0
    return dict(zip(PILIERS, map(_borne, [act, fin, hasard, graph, indic, ratios])))


def signal(rec: Recommandation, ind: pd.DataFrame, fond: dict, actus: list[dict], regles: Regles,
           position: dict | None = None) -> Signal:
    p = piliers(ind, fond, actus)
    c = float(np.mean(list(p.values())))            # avis composite, de −100 à +100
    k = (c + 100) / 200                              # 0..1
    if rec.code == ACHETER:
        score = 34 + k * 66
    elif rec.code == VENDRE:
        score = -100 + k * 66
    else:
        score = -33 + k * 66
    signe = 1 if rec.code == ACHETER else -1 if rec.code == VENDRE else 0
    if rec.code != 0 and any(r in REGLES_PROTECTION for r, _ in rec.raisons):
        confiance = 85                               # règle de protection explicite
    elif signe:
        accord = np.mean([np.sign(v) == signe for v in p.values()])
        confiance = 35 + 45 * accord + 0.15 * abs(c)
    else:
        confiance = 70 - 0.4 * abs(c) - 5 * len([v for v in p.values() if abs(v) > 60])
    cours = float(ind["cours"].iloc[-1])
    if position and position.get("quantite", 0) > 0:
        niveau = position["pru"] * (1 - regles.stop_loss)
        ecart = niveau / cours - 1
        stop = (f"Stop-loss : {_eur(niveau)} ({_pc(ecart)})" if niveau < cours
                else f"Stop-loss : {_eur(niveau)}, déjà franchi")
    elif rec.code == ACHETER:
        niveau = cours * (1 - regles.stop_loss)
        stop = f"Stop-loss : {_eur(niveau)} ({_pc(-regles.stop_loss)})"
    else:
        stop = "Pas d'action conseillée" if rec.code == 0 else "Sortie conseillée"
    return Signal(rec.code, int(round(score)), int(np.clip(round(confiance), 5, 95)), p, rec.raisons[:3], stop)


def signal_global(signaux: list[Signal], suspendre: bool = False) -> tuple[int, int, int]:
    """Signal global du portefeuille : (code, score, confiance)."""
    if not signaux:
        return 0, 0, 0
    score = int(round(np.mean([s.score for s in signaux])))
    confiance = int(round(np.mean([s.confiance for s in signaux])))
    code = ACHETER if score >= 34 else VENDRE if score <= -34 else 0
    if suspendre and code == ACHETER:
        code, score = 0, min(score, 33)
    return code, score, confiance
