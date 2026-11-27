"""Profil de risque de l'investisseur (questionnaire inspiré des pratiques MIF II).

Le questionnaire mesure la capacité à supporter des pertes (situation, horizon, épargne de précaution),
la tolérance psychologique au risque et l'expérience. Le résultat (Prudent, Équilibré, Dynamique)
adapte les règles de décision, la taille des positions et l'adéquation des valeurs conseillées.
Il se refait à tout moment : chaque évaluation est conservée dans l'historique du profil.
"""
from __future__ import annotations

import datetime as dt

from .config import aujourdhui

from .config import Regles

PROFILS = ["Prudent", "Équilibré", "Dynamique"]

# (clé, question, [(réponse, points 0 à 4)], aide)
QUESTIONS: list[tuple[str, str, list[tuple[str, int]], str]] = [
    ("horizon", "Dans combien de temps pourriez-vous avoir besoin de cet argent ?",
     [("Moins d'un an", 0), ("1 à 3 ans", 1), ("3 à 5 ans", 3), ("Plus de 5 ans", 4)],
     "Plus l'horizon est long, plus les baisses passagères ont le temps de se résorber."),
    ("precaution", "Disposez-vous d'une épargne de précaution disponible (au moins 6 mois de dépenses) ?",
     [("Non", 0), ("Partiellement", 2), ("Oui", 4)], ""),
    ("part", "Quelle part de votre patrimoine financier ce capital représente-t-il ?",
     [("Plus de 75 %", 0), ("50 à 75 %", 1), ("25 à 50 %", 3), ("Moins de 25 %", 4)], ""),
    ("revenus", "Comment évoluent vos revenus dans les prochaines années ?",
     [("En baisse ou incertains", 0), ("Stables", 2), ("En hausse", 3), ("Stables et confortables", 4)],
     "Retraite, changement d'emploi, projet immobilier : tout changement de situation compte."),
    ("objectif", "Quel est votre objectif principal ?",
     [("Préserver mon capital", 0), ("Un revenu régulier (dividendes)", 1),
      ("Faire croître mon capital", 3), ("Rechercher une performance élevée", 4)], ""),
    ("perte", "Quelle baisse maximale de votre portefeuille sur un an accepteriez-vous ?",
     [("5 %", 0), ("10 %", 1), ("20 %", 3), ("30 % ou plus", 4)], ""),
    ("reaction", "Votre portefeuille perd 20 % en un mois. Que faites-vous ?",
     [("Je vends tout", 0), ("Je vends une partie", 1), ("J'attends", 3), ("J'en profite pour acheter", 4)], ""),
    ("experience", "Quelle est votre expérience des marchés d'actions ?",
     [("Aucune", 0), ("J'ai déjà acheté quelques actions", 2), ("J'investis régulièrement", 3),
      ("Expérience professionnelle ou très régulière", 4)], ""),
]

# Questions de capacité : une réponse à 0 plafonne le profil, quelle que soit l'appétence au risque.
PLAFONNANTES = ("horizon", "precaution", "perte")

REGLAGES: dict[str, dict] = {
    "Prudent": dict(stop_loss=.03, take_profit=.06, trailing_declenchement=.03, trailing_repli=.02,
                    rsi_surachat=65.0, rsi_survente=30.0, alerte_perte_hebdo=.03, suspension_perte_hebdo=.05,
                    securisation_gain_hebdo=.05, objectif_hebdo=.03, tolerance_hebdo=.05, part_achat=.25,
                    poids_max_ligne=.25, vol_max=.25),
    "Équilibré": dict(stop_loss=.04, take_profit=.08, trailing_declenchement=.04, trailing_repli=.03,
                      rsi_surachat=70.0, rsi_survente=30.0, alerte_perte_hebdo=.04, suspension_perte_hebdo=.07,
                      securisation_gain_hebdo=.07, objectif_hebdo=.05, tolerance_hebdo=.07, part_achat=.35,
                      poids_max_ligne=.35, vol_max=.35),
    "Dynamique": dict(stop_loss=.05, take_profit=.10, trailing_declenchement=.05, trailing_repli=.03,
                      rsi_surachat=70.0, rsi_survente=30.0, alerte_perte_hebdo=.05, suspension_perte_hebdo=.10,
                      securisation_gain_hebdo=.10, objectif_hebdo=.10, tolerance_hebdo=.10, part_achat=.5,
                      poids_max_ligne=.5, vol_max=.50),
}

DESCRIPTIONS = {
    "Prudent": "Vous privilégiez la sécurité du capital. Boussole coupe les pertes plus tôt, sécurise les gains "
               "plus vite, engage moins de liquidités par achat et limite chaque valeur à 25 % du portefeuille.",
    "Équilibré": "Vous acceptez des variations modérées pour faire progresser votre capital. Seuils intermédiaires "
                 "et chaque valeur limitée à 35 % du portefeuille.",
    "Dynamique": "Vous acceptez de fortes variations pour viser une performance élevée : objectif de +10 % et "
                 "perte maximale de −10 % par semaine, comme prévu au cahier des charges.",
}


def evaluer(reponses: dict[str, int]) -> tuple[int, str, list[str]]:
    """Score 0-100, profil et motifs de plafonnement éventuels. `reponses` : indice de réponse par question."""
    total, maxi, plafonds = 0, 0, []
    for cle, question, options, _ in QUESTIONS:
        i = reponses.get(cle)
        maxi += 4
        if i is None or not 0 <= i < len(options):
            continue
        pts = options[i][1]
        total += pts
        if cle in PLAFONNANTES and pts == 0:
            plafonds.append(f"{question} → « {options[i][0]} »")
    score = round(100 * total / maxi) if maxi else 0
    profil = "Prudent" if score < 40 else "Équilibré" if score < 70 else "Dynamique"
    if plafonds and profil != "Prudent":
        profil = "Prudent" if len(plafonds) > 1 else ("Équilibré" if profil == "Dynamique" else profil)
    return score, profil, plafonds


def regles_pour(profil: str, base: Regles | None = None) -> Regles:
    """Règles adaptées au profil ; les autres réglages (moyennes mobiles, montant minimum) sont conservés."""
    r = Regles.from_dict((base or Regles()).to_dict())
    for k, v in REGLAGES.get(profil, {}).items():
        if hasattr(r, k):
            setattr(r, k, type(getattr(r, k))(v))
    return r


def adequation(volatilite: float | None, profil: str) -> tuple[str, str]:
    """Adéquation d'une valeur au profil à partir de sa volatilité annualisée : (niveau, texte)."""
    if volatilite is None or volatilite != volatilite:
        return "neutre", "Volatilité inconnue"
    plafond = REGLAGES.get(profil, REGLAGES["Dynamique"])["vol_max"]
    v = f"{volatilite * 100:.0f}".replace(".", ",")
    if volatilite <= plafond * .8:
        return "ok", f"Adaptée à un profil {profil.lower()} (volatilité {v} %)"
    if volatilite <= plafond:
        return "limite", f"À la limite d'un profil {profil.lower()} (volatilité {v} %)"
    return "risque", f"Trop volatile pour un profil {profil.lower()} (volatilité {v} % > {plafond * 100:.0f} %)"


def entree_historique(score: int, profil: str, motif: str) -> dict:
    return dict(date=aujourdhui().isoformat(), score=int(score), profil=profil, motif=motif)


def a_revoir(historique: list[dict], mois: int = 12) -> bool:
    """Vrai si le profil n'a jamais été évalué ou date de plus de `mois` mois."""
    if not historique:
        return True
    try:
        der = dt.date.fromisoformat(historique[-1]["date"])
    except (KeyError, ValueError):
        return True
    return (aujourdhui() - der).days > mois * 30
