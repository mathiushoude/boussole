"""Moteur de recommandation : Acheter (+1), Rester (0), Vendre (−1) — EXG-F-08 à F-25.

Ordre de priorité (EXG-F-25) :
  1. gestion du risque global (sécurisation des gains, suspension des achats) ;
  2. signaux de vente sur une position détenue (stop-loss, take-profit, trailing stop, RSI) ;
  3. signaux d'achat (fondamental + technique, croisement MM, rebond RSI), sous réserve
     de liquidités suffisantes ;
  4. conservation (indicateurs contradictoires ou absence de signal).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import indicators as ti
from .config import Regles

ACHETER, RESTER, VENDRE = 1, 0, -1
LIBELLES = {ACHETER: "Acheter", RESTER: "Attendre", VENDRE: "Vendre"}  # « Attendre » = Rester (0)


@dataclass
class Recommandation:
    code: int
    raisons: list[tuple[str, str]] = field(default_factory=list)  # (id exigence, explication)
    alerte: str | None = None

    @property
    def libelle(self) -> str:
        return LIBELLES[self.code]


@dataclass
class RisqueGlobal:
    perf_hebdo: float
    niveau: str            # "normal" | "alerte" | "critique" | "objectif"
    suspendre_achats: bool
    securiser_gains: bool
    message: str


def _p(x: float, signe: bool = False) -> str:
    return (f"{x:+.1%}" if signe else f"{x:.1%}").replace(".", ",").replace("%", "\u202f%").replace("-", "−")


def _e(x: float) -> str:
    return f"{x:,.2f}".replace(",", "\u202f").replace(".", ",") + "\u202f€"


def risque_global(perf_hebdo: float, regles: Regles) -> RisqueGlobal:
    """EXG-F-22, F-23, F-24."""
    if perf_hebdo <= -regles.suspension_perte_hebdo:
        return RisqueGlobal(perf_hebdo, "critique", True, False,
                            f"Perte de {_p(perf_hebdo)} sur la semaine : les nouveaux achats sont suspendus.")
    if perf_hebdo <= -regles.alerte_perte_hebdo:
        return RisqueGlobal(perf_hebdo, "alerte", False, False,
                            f"Le portefeuille a perdu {_p(perf_hebdo)} sur la semaine. Restez attentif.")
    if perf_hebdo >= regles.securisation_gain_hebdo:
        return RisqueGlobal(perf_hebdo, "objectif", False, True,
                            f"Le portefeuille a gagné {_p(perf_hebdo, True)} sur la semaine : il peut être "
                            f"utile de sécuriser une partie des gains.")
    return RisqueGlobal(perf_hebdo, "normal", False, False,
                        f"Rendement sur la semaine : {_p(perf_hebdo, True)}. Aucun seuil de risque atteint.")


PRIORITE = "Les règles de protection du capital passent avant les autres signaux."


def recommander(ind: pd.DataFrame, regles: Regles, *, position: dict | None = None,
                score_fond: float = 0.5, liquidites: float = 0.0,
                risque: RisqueGlobal | None = None) -> Recommandation:
    """Recommandation pour une action à la dernière ligne de `ind`.

    position : {"quantite", "pru", "plus_haut"} si l'action est détenue.
    score_fond : score fondamental entre 0 et 1.
    """
    cours = float(ind["cours"].iloc[-1])
    rsi = ind["rsi"].iloc[-1]
    risque = risque or risque_global(0.0, regles)
    alerte = risque.message if risque.niveau in ("alerte", "critique") else None
    detenue = bool(position and position.get("quantite", 0) > 0)

    # 1. Risque global prioritaire -------------------------------------------
    if detenue and risque.securiser_gains and cours > position["pru"]:
        return Recommandation(VENDRE, [("EXG-F-24", risque.message), ("EXG-F-25", PRIORITE)], alerte)

    # 2. Signaux de vente -------------------------------------------------------
    if detenue:
        pru = position["pru"]
        perf = cours / pru - 1
        plus_haut = max(position.get("plus_haut", cours), cours)
        gain_max = plus_haut / pru - 1
        repli = cours / plus_haut - 1
        if perf <= -regles.stop_loss:
            return Recommandation(VENDRE, [("EXG-F-12", f"Le titre a perdu {_p(perf, True)} depuis l'achat "
                                            f"({_e(pru)} → {_e(cours)}) : le seuil de protection est atteint.")],
                                  alerte)
        if perf >= regles.take_profit:
            return Recommandation(VENDRE, [("EXG-F-13", f"Objectif de gain atteint : {_p(perf, True)} depuis "
                                            f"l'achat ({_e(pru)} → {_e(cours)}).")], alerte)
        if gain_max >= regles.trailing_declenchement and repli <= -regles.trailing_repli:
            return Recommandation(VENDRE, [("EXG-F-14", f"Après un gain de {_p(gain_max, True)}, le titre recule "
                                            f"de {_p(repli, True)} depuis son plus haut ({_e(plus_haut)} → "
                                            f"{_e(cours)}).")], alerte)
        if ti.retournement_baissier(ind, regles.rsi_surachat):
            return Recommandation(VENDRE, [("EXG-F-15", "Le titre a très fortement monté ces dernières semaines et "
                                            "recule depuis deux séances : la hausse s'essouffle.")], alerte)

    # 3. Signaux d'achat --------------------------------------------------------
    tech = ti.etat_technique(ind, regles.rsi_survente, regles.rsi_surachat)
    fond = "favorable" if score_fond >= 0.6 else ("defavorable" if score_fond <= 0.4 else "neutre")
    achats: list[tuple[str, str]] = []
    if fond == "favorable" and tech == "favorable":
        achats.append(("EXG-F-16", f"L'entreprise est solide ({score_fond * 100:.0f} % de ses indicateurs financiers sont "
                                   f"bons) et son cours progresse."))
    if ti.croisement_haussier(ind):
        achats.append(("EXG-F-17", "Le cours des dernières semaines repasse au-dessus de sa moyenne des derniers "
                                   "mois : la tendance repart à la hausse."))
    if ti.rebond_confirme(ind, regles.rsi_survente):
        achats.append(("EXG-F-18", "Après une forte baisse, le titre remonte depuis deux séances."))
    if achats and fond == "defavorable":
        return Recommandation(RESTER, achats + [("EXG-F-21", "Le graphique est encourageant mais les comptes de "
                                                 "l'entreprise sont fragiles : mieux vaut attendre.")], alerte)
    if achats:
        if risque.suspendre_achats:
            return Recommandation(RESTER, achats + [("EXG-F-23", risque.message), ("EXG-F-25", PRIORITE)], alerte)
        if liquidites < regles.montant_achat_min:
            return Recommandation(RESTER, achats + [("EXG-F-19", f"Signal favorable, mais les liquidités sont "
                                                     f"insuffisantes ({_e(liquidites)} disponibles).")], alerte)
        return Recommandation(ACHETER, achats, alerte)

    # 4. Conservation ------------------------------------------------------------
    if {fond, tech} == {"favorable", "defavorable"}:
        txt_f = "favorables" if fond == "favorable" else "fragiles"
        txt_t = "haussière" if tech == "favorable" else "baissière"
        return Recommandation(RESTER, [("EXG-F-21", f"Les comptes de l'entreprise sont {txt_f} mais la "
                                        f"tendance du cours est {txt_t} : mieux vaut attendre et surveiller.")], alerte)
    return Recommandation(RESTER, [("EXG-F-20", "Rien de décisif pour l'instant : ni raison d'acheter, ni raison de vendre.")], alerte)
