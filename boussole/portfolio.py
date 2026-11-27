"""Gestion du portefeuille simulé (EXG-F-01 à F-04)."""
from __future__ import annotations

import datetime as dt
import math

import pandas as pd

from .config import CAPITAL_INITIAL


class OperationRefusee(ValueError):
    """Opération impossible (liquidités ou titres insuffisants...)."""


class Portefeuille:
    def __init__(self, capital: float = CAPITAL_INITIAL, transactions: list[dict] | None = None):
        self.capital = float(capital)
        self.transactions: list[dict] = list(transactions or [])
        self.horodatage = False    # True pour le portefeuille réel : heure d'enregistrement de chaque opération

    # ------------------------------------------------------------ sérialisation
    def to_dict(self) -> dict:
        return {"capital": self.capital, "transactions": self.transactions}

    @classmethod
    def from_dict(cls, d: dict) -> "Portefeuille":
        return cls(d.get("capital", CAPITAL_INITIAL), d.get("transactions", []))

    # ------------------------------------------------------------------ calculs
    def _jusqua(self, t: int | None):
        return [x for x in self.transactions if t is None or x["t"] <= t]

    def liquidites(self, t: int | None = None) -> float:
        cash = self.capital
        for x in self._jusqua(t):
            cash += -x["montant"] if x["sens"] in ("Achat", "Retrait") else x["montant"]
        return round(cash, 2)

    def apports(self, t: int | None = None) -> float:
        """Capital investi : capital de départ + apports − retraits."""
        return self.capital + sum(x["montant"] if x["sens"] == "Apport" else -x["montant"]
                                  for x in self._jusqua(t) if x["sens"] in ("Apport", "Retrait"))

    def recaler(self, dates: pd.DatetimeIndex) -> None:
        """Recalcule l'indice de séance de chaque opération à partir de sa date (les cours avancent chaque jour)."""
        for x in self.transactions:
            i = int(dates.searchsorted(pd.Timestamp(x["date"]), side="right")) - 1
            x["t"] = max(i, 0)

    def mouvement(self, t: int, date, sens: str, montant: float) -> dict:
        """Apport ou retrait de liquidités."""
        montant = round(float(montant), 2)
        if montant <= 0:
            raise OperationRefusee("Indiquez un montant positif.")
        if sens == "Retrait" and montant > self.liquidites(t) + 1e-6:
            raise OperationRefusee(f"Retrait impossible : {self.liquidites(t):,.2f} € de liquidités disponibles.")
        return self._ajouter(t, date, "—", sens, 0, 0.0, montant, "Manuel")

    def positions(self, t: int | None = None, cours: pd.DataFrame | None = None) -> dict[str, dict]:
        """Positions ouvertes : quantité, PRU, plus-value réalisée, plus haut depuis l'ouverture."""
        pos: dict[str, dict] = {}
        for x in self._jusqua(t):
            if x["sens"] not in ("Achat", "Vente"):
                continue
            p = pos.setdefault(x["ticker"], dict(quantite=0, pru=0.0, realise=0.0, ouverture_t=x["t"]))
            if x["sens"] == "Achat":
                if p["quantite"] == 0:
                    p["ouverture_t"] = x["t"]
                total = p["pru"] * p["quantite"] + x["montant"]
                p["quantite"] += x["quantite"]
                p["pru"] = total / p["quantite"]
            else:
                p["realise"] += (x["prix"] - p["pru"]) * x["quantite"]
                p["quantite"] -= x["quantite"]
        if cours is not None and t is not None:
            for tk, p in pos.items():
                if p["quantite"] > 0 and tk in cours:
                    p["plus_haut"] = float(cours[tk].iloc[p["ouverture_t"]: t + 1].max())
        return pos

    def valeur(self, t: int, cours: pd.DataFrame) -> float:
        v = self.liquidites(t)
        for tk, p in self.positions(t).items():
            if p["quantite"] > 0 and tk in cours:
                v += p["quantite"] * float(cours[tk].iloc[t])
        return v

    def historique(self, cours: pd.DataFrame, t0: int, t1: int) -> pd.Series:
        """Valeur quotidienne du portefeuille entre t0 et t1 (inclus), calcul incrémental."""
        tx = sorted(self.transactions, key=lambda x: x["t"])
        cash, qte, valeurs, i = self.capital, {}, [], 0
        for t in range(t0, t1 + 1):
            while i < len(tx) and tx[i]["t"] <= t:
                x = tx[i]
                if x["sens"] in ("Apport", "Retrait"):
                    cash += x["montant"] if x["sens"] == "Apport" else -x["montant"]
                else:
                    signe = 1 if x["sens"] == "Achat" else -1
                    cash -= signe * x["montant"]
                    qte[x["ticker"]] = qte.get(x["ticker"], 0) + signe * x["quantite"]
                i += 1
            valeurs.append(cash + sum(q * float(cours[tk].iloc[t]) for tk, q in qte.items() if q and tk in cours))
        return pd.Series(valeurs, index=cours.index[t0: t1 + 1], name="valeur")

    def perf_hebdo(self, cours: pd.DataFrame, t: int, t0: int) -> float:
        """Rendement sur les 5 dernières séances (ou depuis le début si moins), hors apports et retraits."""
        d = max(t0, t - 5)
        v0 = self.valeur(d, cours)
        flux = sum(x["montant"] if x["sens"] == "Apport" else -x["montant"] for x in self.transactions
                   if x["sens"] in ("Apport", "Retrait") and d < x["t"] <= t)
        return (self.valeur(t, cours) - flux) / v0 - 1 if v0 else 0.0

    def tableau(self, t: int, cours: pd.DataFrame, noms: dict[str, str] | None = None) -> pd.DataFrame:
        """Gains et pertes par action (EXG-F-04)."""
        lignes = []
        for tk, p in self.positions(t).items():
            c = float(cours[tk].iloc[t]) if tk in cours else float("nan")
            valeur = p["quantite"] * c
            latente = (c - p["pru"]) * p["quantite"] if p["quantite"] else 0.0
            lignes.append(dict(
                ticker=tk, nom=(noms or {}).get(tk, tk), quantite=p["quantite"],
                pru=p["pru"] if p["quantite"] else 0.0, cours=c, valeur=valeur,
                pv_latente=latente, pv_realisee=p["realise"],
                perf=(c / p["pru"] - 1) if p["quantite"] and p["pru"] else 0.0))
        return pd.DataFrame(lignes)

    # --------------------------------------------------------------- opérations
    def acheter(self, t: int, date, ticker: str, prix: float, *, montant: float | None = None,
                quantite: int | None = None, motif: str = "Manuel") -> dict:
        if quantite is None:
            quantite = math.floor((montant or 0) / prix)
        if quantite <= 0:
            raise OperationRefusee("Montant trop faible pour acheter au moins une action.")
        cout = round(quantite * prix, 2)
        dispo = self.liquidites(t)
        if cout > dispo + 1e-6:  # EXG-F-19 / EXG-F-02
            raise OperationRefusee(f"Liquidités insuffisantes : {cout:,.2f} € demandés, {dispo:,.2f} € disponibles.")
        return self._ajouter(t, date, ticker, "Achat", quantite, prix, cout, motif)

    def vendre(self, t: int, date, ticker: str, prix: float, *, quantite: int | None = None,
               motif: str = "Manuel") -> dict:
        detenu = self.positions(t).get(ticker, {}).get("quantite", 0)
        quantite = detenu if quantite is None else quantite
        if quantite <= 0 or quantite > detenu:
            raise OperationRefusee(f"Quantité invalide : {detenu} titre(s) détenu(s).")
        return self._ajouter(t, date, ticker, "Vente", quantite, prix, round(quantite * prix, 2), motif)

    def _ajouter(self, t, date, ticker, sens, quantite, prix, montant, motif) -> dict:
        if self.transactions and t < max(x["t"] for x in self.transactions):
            raise OperationRefusee("Impossible d'enregistrer une opération antérieure à la dernière opération.")
        x = dict(t=int(t), date=pd.Timestamp(date).strftime("%Y-%m-%d"), ticker=ticker, sens=sens,
                 quantite=int(quantite), prix=round(float(prix), 2), montant=float(montant), motif=motif)
        if self.horodatage:
            x["enregistre"] = dt.datetime.now().isoformat(timespec="seconds")
        self.transactions.append(x)
        return x


def allouer(capital: float, allocation: dict[str, float], cours: pd.DataFrame, t: int, date,
            motif: str = "Allocation initiale") -> Portefeuille:
    """Crée un portefeuille et répartit le capital (montants en €) — EXG-F-02."""
    total = sum(allocation.values())
    if total > capital + 1e-6:
        raise OperationRefusee(f"L'allocation ({total:,.0f} €) dépasse le capital ({capital:,.0f} €).")
    pf = Portefeuille(capital)
    for tk, montant in allocation.items():
        if montant > 0:
            try:
                pf.acheter(t, date, tk, float(cours[tk].iloc[t]), montant=montant, motif=motif)
            except OperationRefusee:
                pass
    return pf
