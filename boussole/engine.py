"""Orchestration : analyse du jour et backtest annuel (EXG-P-01, EXG-R-01)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

from . import data, indicators as ti, rules
from .config import Regles
from .portfolio import OperationRefusee, Portefeuille, allouer


def indicateurs(cours: pd.DataFrame, regles: Regles) -> dict[str, pd.DataFrame]:
    return {tk: ti.calculer(cours[tk], regles.mm_courte, regles.mm_longue) for tk in cours.columns}


def scores_fondamentaux(cours: pd.DataFrame, t: int, source: str) -> dict[str, dict]:
    out = {}
    for tk in cours.columns:
        f = data.fondamentaux(tk, float(cours[tk].iloc[t]), source)
        f["score"], f["criteres"] = data.score_fondamental(f)
        out[tk] = f
    return out


def analyser(cours: pd.DataFrame, inds: dict[str, pd.DataFrame], pf: Portefeuille, t: int, t0: int,
             regles: Regles, fonds: dict[str, dict]) -> tuple[rules.RisqueGlobal, dict[str, rules.Recommandation]]:
    """Recommandations pour chaque action à la séance t."""
    risque = rules.risque_global(pf.perf_hebdo(cours, t, t0), regles)
    pos = pf.positions(t, cours)
    cash = pf.liquidites(t)
    recs = {}
    for tk in cours.columns:
        rec = rules.recommander(inds[tk].iloc[: t + 1], regles, position=pos.get(tk),
                                score_fond=fonds[tk]["score"], liquidites=cash, risque=risque)
        vol = volatilite(cours[tk], t)
        if rec.code == rules.ACHETER and vol is not None and vol > regles.vol_max:   # adéquation au profil
            rec = rules.Recommandation(rules.RESTER, [("PROFIL", f"Achat déconseillé pour votre profil : ce titre varie "
                                                      f"d'environ {vol * 100:.0f} % par an, au-delà des "
                                                      f"{regles.vol_max * 100:.0f} % que vous acceptez.")]
                                       + rec.raisons, rec.alerte)
        recs[tk] = rec
    return risque, recs


def volatilite(serie: pd.Series, t: int, fenetre: int = 60) -> float | None:
    """Volatilité annualisée sur les `fenetre` dernières séances."""
    r = serie.iloc[max(0, t - fenetre): t + 1].pct_change().dropna()
    return float(r.std() * 252 ** .5) if len(r) >= 10 else None


def executer(pf: Portefeuille, recs: dict[str, rules.Recommandation], cours: pd.DataFrame, t: int,
             regles: Regles, allocation: dict[str, float], capital: float) -> list[dict]:
    """Exécute les recommandations du jour (pilote automatique et backtest)."""
    faites = []
    date = cours.index[t]
    for tk, rec in recs.items():
        prix = float(cours[tk].iloc[t])
        try:
            if rec.code == rules.VENDRE:
                faites.append(pf.vendre(t, date, tk, prix, motif=rec.raisons[0][0]))
            elif rec.code == rules.ACHETER:
                deja = pf.positions(t).get(tk, {}).get("quantite", 0) * prix
                cible = allocation.get(tk, capital / len(cours.columns)) or capital / len(cours.columns)
                plafond = pf.valeur(t, cours) * regles.poids_max_ligne - deja   # concentration (profil)
                montant = min(pf.liquidites(t) * regles.part_achat, cible - deja, plafond)
                if montant >= regles.montant_achat_min:
                    faites.append(pf.acheter(t, date, tk, prix, montant=montant, motif=rec.raisons[0][0]))
        except OperationRefusee:
            pass
    return faites


@dataclass
class ResultatBacktest:
    valeurs: pd.Series
    reference: pd.Series          # achat-conservation de l'allocation initiale
    portefeuille: Portefeuille
    duree_s: float

    @property
    def rendement(self) -> float:
        return self.valeurs.iloc[-1] / self.valeurs.iloc[0] - 1

    @property
    def rendement_reference(self) -> float:
        return self.reference.iloc[-1] / self.reference.iloc[0] - 1

    @property
    def drawdown_max(self) -> float:
        return float((self.valeurs / self.valeurs.cummax() - 1).min())

    def hebdo(self) -> pd.Series:
        return self.valeurs.resample("W-FRI").last().pct_change().dropna()


def backtest(cours: pd.DataFrame, allocation: dict[str, float], regles: Regles, t0: int,
             capital: float, source: str = "Démonstration", fonds: dict | None = None) -> ResultatBacktest:
    """Applique automatiquement les recommandations, séance après séance, sur l'année."""
    debut = time.perf_counter()
    inds = indicateurs(cours, regles)
    dates = cours.index
    pf = allouer(capital, allocation, cours, t0, dates[t0])
    ref = allouer(capital, allocation, cours, t0, dates[t0])
    fonds = fonds or scores_fondamentaux(cours, t0, source)
    for t in range(t0 + 1, len(cours)):
        _, recs = analyser(cours, inds, pf, t, t0, regles, fonds)
        executer(pf, recs, cours, t, regles, allocation, capital)
    return ResultatBacktest(pf.historique(cours, t0, len(cours) - 1),
                            ref.historique(cours, t0, len(cours) - 1), pf, time.perf_counter() - debut)
