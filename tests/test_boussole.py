"""Tests automatisés de Boussole (EXG-M-01) : règles de décision, portefeuille, reproductibilité."""
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from boussole import data, engine, indicators as ti, news, rules, score as sc  # noqa: E402
from boussole.config import ACTIONS_PAR_DEFAUT, CAPITAL_INITIAL, JOURS_PAR_AN, Regles  # noqa: E402
from boussole.portfolio import OperationRefusee, Portefeuille, allouer  # noqa: E402

R = Regles()


def serie(valeurs):
    idx = pd.bdate_range("2025-01-01", periods=len(valeurs))
    return ti.calculer(pd.Series(valeurs, index=idx, dtype=float))


def plat(n=80, prix=100.0):
    return [prix] * n


# ------------------------------------------------------------------ ventes --
def test_stop_loss_exg_f_12():
    rec = rules.recommander(serie(plat(79) + [94.0]), R, position=dict(quantite=10, pru=100.0, plus_haut=100.0))
    assert rec.code == rules.VENDRE and rec.raisons[0][0] == "EXG-F-12"


def test_take_profit_exg_f_13():
    rec = rules.recommander(serie(plat(79) + [111.0]), R, position=dict(quantite=10, pru=100.0, plus_haut=111.0))
    assert rec.code == rules.VENDRE and rec.raisons[0][0] == "EXG-F-13"


def test_trailing_stop_exg_f_14():
    # plus haut à 108 (+8 %), cours à 104 (−3,7 % depuis le plus haut)
    rec = rules.recommander(serie(plat(79) + [104.0]), R, position=dict(quantite=10, pru=100.0, plus_haut=108.0))
    assert rec.code == rules.VENDRE and rec.raisons[0][0] == "EXG-F-14"


def test_rsi_retournement_exg_f_15():
    hausse = list(np.linspace(80, 99.5, 60)) + [100, 101, 102, 103, 104, 105, 106]
    ind = serie(hausse + [105.6, 105.3])          # RSI > 70 puis deux baisses
    assert ind["rsi"].iloc[-3] > 70
    rec = rules.recommander(ind, R, position=dict(quantite=10, pru=104.0, plus_haut=106.0))
    assert rec.code == rules.VENDRE and rec.raisons[0][0] == "EXG-F-15"


# ------------------------------------------------------------------ achats --
def test_croisement_haussier_exg_f_17():
    baisse = list(np.linspace(120, 100, 50))
    reprise = list(np.linspace(100, 112, 30))
    ind = None
    for k in range(len(reprise)):
        cand = serie(baisse + reprise[: k + 1])
        if ti.croisement_haussier(cand):
            ind = cand
            break
    assert ind is not None
    rec = rules.recommander(ind, R, score_fond=0.6, liquidites=100_000)
    assert rec.code == rules.ACHETER and "EXG-F-17" in [r for r, _ in rec.raisons]


def test_rebond_rsi_exg_f_18():
    ind = serie(list(np.linspace(130, 100, 70)) + [100.5, 101.2])
    assert ti.rebond_confirme(ind)
    rec = rules.recommander(ind, R, score_fond=0.6, liquidites=100_000)
    assert rec.code == rules.ACHETER and "EXG-F-18" in [r for r, _ in rec.raisons]


def test_liquidites_insuffisantes_exg_f_19():
    ind = serie(list(np.linspace(130, 100, 70)) + [100.5, 101.2])
    rec = rules.recommander(ind, R, score_fond=0.6, liquidites=10)
    assert rec.code == rules.RESTER and rec.raisons[-1][0] == "EXG-F-19"


def test_stable_rester_exg_f_20():
    rec = rules.recommander(serie(plat()), R, score_fond=0.5, liquidites=100_000)
    assert rec.code == rules.RESTER and rec.raisons[0][0] == "EXG-F-20"


def test_contradiction_exg_f_21():
    ind = serie(list(np.linspace(120, 95, 80)))        # tendance baissière
    rec = rules.recommander(ind, R, score_fond=1.0, liquidites=100_000)
    assert rec.code == rules.RESTER and rec.raisons[0][0] == "EXG-F-21"


# ---------------------------------------------------------- risque global --
@pytest.mark.parametrize("perf,niveau", [(-0.05, "alerte"), (-0.10, "critique"), (0.10, "objectif"), (0.0, "normal")])
def test_risque_global_exg_f_22_23_24(perf, niveau):
    assert rules.risque_global(perf, R).niveau == niveau


def test_priorite_risque_exg_f_25():
    ind = serie(list(np.linspace(130, 100, 70)) + [100.5, 101.2])   # signal d'achat...
    rec = rules.recommander(ind, R, score_fond=0.6, liquidites=100_000,
                            risque=rules.risque_global(-0.12, R))  # ... et perte de 12 %
    assert rec.code == rules.RESTER and "EXG-F-25" in [r for r, _ in rec.raisons]


def test_securiser_gains_exg_f_24():
    rec = rules.recommander(serie(plat(79) + [103.0]), R, position=dict(quantite=10, pru=100.0, plus_haut=103.0),
                            risque=rules.risque_global(0.11, R))
    assert rec.code == rules.VENDRE and rec.raisons[0][0] == "EXG-F-24"


# -------------------------------------------------------------- portefeuille --
def test_allocation_maximale_exg_f_02():
    c = data.cours_simules(ACTIONS_PAR_DEFAUT, dt.date(2026, 11, 26))
    with pytest.raises(OperationRefusee):
        allouer(CAPITAL_INITIAL, {t: 120_000 for t in ACTIONS_PAR_DEFAUT}, c, 130, c.index[130])
    pf = allouer(CAPITAL_INITIAL, {t: 100_000 for t in ACTIONS_PAR_DEFAUT}, c, 130, c.index[130])
    assert 0 <= pf.liquidites() < 5_000


def test_gains_pertes_calcul_manuel_exg_f_04():
    idx = pd.bdate_range("2026-01-01", periods=3)
    c = pd.DataFrame({"A": [100.0, 110.0, 90.0]}, index=idx)
    pf = Portefeuille(10_000)
    pf.acheter(0, idx[0], "A", 100.0, quantite=50)     # 5 000 €
    pf.vendre(1, idx[1], "A", 110.0, quantite=20)      # +200 € réalisés
    tab = pf.tableau(2, c)
    assert tab.loc[0, "pv_realisee"] == pytest.approx(200)
    assert tab.loc[0, "pv_latente"] == pytest.approx(30 * (90 - 100))
    assert pf.valeur(2, c) == pytest.approx(10_000 - 5_000 + 2_200 + 30 * 90)
    with pytest.raises(OperationRefusee):
        pf.acheter(2, idx[2], "A", 90.0, quantite=1000)   # EXG-F-19


# ----------------------------------------------------------- non fonctionnel --
def test_backtest_rapide_et_reproductible_exg_p_01_r_01():
    c = data.cours_simules(ACTIONS_PAR_DEFAUT, dt.date(2026, 11, 26))
    t0 = len(c) - JOURS_PAR_AN
    alloc = {t: 100_000 for t in ACTIONS_PAR_DEFAUT}
    debut = time.perf_counter()
    a = engine.backtest(c, alloc, R, t0, CAPITAL_INITIAL)
    assert time.perf_counter() - debut < 300
    b = engine.backtest(c, alloc, R, t0, CAPITAL_INITIAL)
    pd.testing.assert_series_equal(a.valeurs, b.valeurs)
    assert a.portefeuille.transactions == b.portefeuille.transactions


def test_donnees_simulees_identiques():
    a = data.cours_simules(["MC.PA"], dt.date(2026, 1, 5))
    b = data.cours_simules(["MC.PA"], dt.date(2026, 1, 5))
    pd.testing.assert_frame_equal(a, b)


# ------------------------------------------------------------- jauge (charte) --
@pytest.mark.parametrize("code,lo,hi", [(1, 34, 100), (0, -33, 33), (-1, -100, -34)])
def test_score_dans_sa_zone(code, lo, hi):
    ind = serie(list(np.linspace(90, 110, 80)))
    fond = dict(score=.8, per=15, rendement=.03)
    s = sc.signal(rules.Recommandation(code, [("EXG-F-20", "test")]), ind, fond, [], R)
    assert lo <= s.score <= hi and 5 <= s.confiance <= 95 and len(s.piliers) == 6


# ------------------------------------------------------------ données réelles --
def test_yahoo_cache_puis_hors_ligne(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    reels = data.cours_simules(["MC.PA", "OR.PA"], dt.date(2026, 11, 20))
    monkeypatch.setattr(data, "telecharger_yahoo", lambda t: (reels[t], {x: "EUR" for x in t}))
    ok = data.charger_cours(["MC.PA", "OR.PA"])
    assert ok.source == data.YAHOO and not ok.hors_ligne

    def panne(t):
        raise ConnectionError("réseau coupé")
    monkeypatch.setattr(data, "telecharger_yahoo", panne)
    hl = data.charger_cours(["MC.PA", "OR.PA"])          # réutilise les derniers cours réels
    assert hl.hors_ligne and hl.source == data.YAHOO
    pd.testing.assert_frame_equal(hl.prix, ok.prix, check_freq=False, check_exact=False)
    with pytest.raises(data.DonneesIndisponibles):        # jamais de bascule silencieuse vers du fictif
        data.charger_cours(["AIR.PA"])


def test_fondamentaux_manquants_non_inventes():
    f = dict(ca=None, dpa=None, per=12.0, marge=None, rendement=None)
    score, ok = data.score_fondamental(f)
    assert score == 1.0 and ok == ["PER ≤ 25"]


# ------------------------------------------------------------------ actualités --
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>LVMH : les ventes progressent au troisième trimestre - Les Echos</title>
<link>https://www.lesechos.fr/a</link><pubDate>Wed, 26 Nov 2026 09:15:00 GMT</pubDate>
<source url="https://www.lesechos.fr">Les Echos</source></item>
<item><title>LVMH recule après un avertissement - Blog anonyme</title>
<link>https://exemple.org/b</link><pubDate>Wed, 26 Nov 2026 10:00:00 GMT</pubDate>
<source url="https://exemple.org">Blog anonyme</source></item>
</channel></rss>""".encode("utf-8")


def test_rss_et_liste_blanche():
    items = news.lire_rss_google(RSS)
    assert items[0]["titre"].startswith("LVMH : les ventes") and items[0]["source"] == "Les Echos"
    fus = news.fusionner(items)
    assert [x["source"] for x in fus] == ["Les Echos"]          # source non reconnue écartée
    assert fus[0]["tonalite"] == 1


def test_fil_yahoo_et_dedoublonnage():
    brut = [{"content": {"title": "LVMH : les ventes progressent au troisième trimestre",
                         "pubDate": "2026-11-26T11:00:00Z", "provider": {"displayName": "Reuters"},
                         "canonicalUrl": {"url": "https://reuters.com/x"}}}]
    y = news.lire_yahoo(brut)
    fus = news.fusionner(y, news.lire_rss_google(RSS))
    assert len(fus) == 1 and fus[0]["source"] == "Reuters"       # même titre : gardé une fois, le plus récent
    assert news.tonalite("Airbus chute après un avertissement") == -1


def test_conversion_en_euros_et_pence():
    idx = pd.bdate_range("2026-01-05", periods=3)
    close = pd.DataFrame({"AAPL": [100.0, 110.0, 120.0], "SHEL.L": [2500.0, 2500.0, 2500.0], "MC.PA": [600.0] * 3},
                         index=idx)
    taux = {"USD": pd.Series([0.9, 0.9, 0.95], index=idx), "GBP": pd.Series([1.2, 1.2, 1.2], index=idx)}
    eur = data.convertir_en_euros(close, {"AAPL": "USD", "SHEL.L": "GBp", "MC.PA": "EUR"}, taux.get)
    assert list(eur["AAPL"].round(2)) == [90.0, 99.0, 114.0]
    assert list(eur["SHEL.L"].round(2)) == [30.0, 30.0, 30.0]          # 2 500 pence = 25 £ = 30 €
    assert list(eur["MC.PA"]) == [600.0] * 3
    with pytest.raises(data.DonneesIndisponibles):
        data.convertir_en_euros(close, {"AAPL": "JPY"}, lambda d: None)


def test_recherche_titres_filtre_actions_et_etf():
    quotes = [dict(symbol="AAPL", quoteType="EQUITY", longname="Apple Inc.", exchDisp="NASDAQ"),
              dict(symbol="AAPL", quoteType="EQUITY", shortname="Apple"),
              dict(symbol="CW8.PA", quoteType="ETF", shortname="Amundi MSCI World", exchDisp="Paris"),
              dict(symbol="AAPL250117C00150000", quoteType="OPTION"),
              dict(symbol="BTC-USD", quoteType="CRYPTOCURRENCY")]
    res = data.lire_recherche(quotes)
    assert [r["symbole"] for r in res] == ["AAPL", "CW8.PA"]
    assert res[0]["nom"] == "Apple Inc." and res[1]["type"] == "ETF"


# ------------------------------------------------------------ profil de risque --
from boussole import profil_risque as pr  # noqa: E402


def test_questionnaire_profils_et_plafond():
    tout = lambda i: {c: min(i, len(o) - 1) for c, _, o, _ in pr.QUESTIONS}
    assert pr.evaluer(tout(0))[1] == "Prudent"
    assert pr.evaluer(tout(3))[1] == "Dynamique"
    rep = tout(3)
    rep["precaution"] = 0                         # pas d'épargne de précaution : profil plafonné
    score, profil, plafonds = pr.evaluer(rep)
    assert score >= 70 and profil == "Équilibré" and len(plafonds) == 1


def test_regles_selon_profil_et_achat_ecarte():
    prudent = pr.regles_pour("Prudent", Regles(mm_courte=10))
    assert prudent.stop_loss == .03 and prudent.poids_max_ligne == .25 and prudent.mm_courte == 10
    assert pr.regles_pour("Dynamique").tolerance_hebdo == Regles().tolerance_hebdo
    assert pr.adequation(.45, "Prudent")[0] == "risque" and pr.adequation(.15, "Prudent")[0] == "ok"
    assert pr.a_revoir([]) and not pr.a_revoir([pr.entree_historique(50, "Équilibré", "test")])


# ------------------------------------------------------------ comptes et suivi réel --
from boussole import comptes  # noqa: E402
from boussole.portfolio import Portefeuille  # noqa: E402


def test_comptes_locaux_mot_de_passe_chiffre(tmp_path, monkeypatch):
    monkeypatch.setattr(comptes, "DOSSIER", tmp_path)
    with pytest.raises(comptes.ErreurCompte):
        comptes.creer_compte("dupont@exemple.fr", "M. Dupont", "court")
    uid = comptes.creer_compte("Dupont@Exemple.fr", "M. Dupont", "boussole2026")
    assert "boussole2026" not in (tmp_path / "comptes.json").read_text()          # jamais en clair
    assert comptes.connecter("dupont@exemple.fr", "boussole2026") == uid
    with pytest.raises(comptes.ErreurCompte):
        comptes.connecter("dupont@exemple.fr", "mauvais123")
    with pytest.raises(comptes.ErreurCompte):
        comptes.creer_compte("dupont@exemple.fr", "Autre", "autre2026x")         # pas de doublon
    jeton = comptes.ouvrir_session(uid)
    assert comptes.session_uid(jeton) == uid
    comptes.fermer_session(jeton)
    assert comptes.session_uid(jeton) is None


def test_apports_retraits_et_recalage_des_dates():
    c = pd.DataFrame({"X": [100.0, 100, 110, 120]}, index=pd.bdate_range("2026-03-02", periods=4))
    pf = Portefeuille(1_000)
    pf.acheter(1, c.index[1], "X", 100, quantite=5)
    pf.mouvement(2, c.index[2], "Apport", 500)
    assert pf.liquidites(2) == 1_000 and pf.apports() == 1_500
    with pytest.raises(OperationRefusee):
        pf.mouvement(3, c.index[3], "Retrait", 5_000)
    assert pf.valeur(3, c) == 1_000 + 5 * 120
    plus_long = pd.bdate_range(c.index[0] - pd.Timedelta(days=7), c.index[-1])   # nouvelles séances en tête
    pf.recaler(plus_long)
    assert [x["t"] for x in pf.transactions] == [6, 7]


def test_cotations_en_direct_remplacent_le_jour():
    import datetime as dt
    import pandas as pd
    from boussole import data
    p = pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0]}, index=pd.to_datetime(["2026-11-25", "2026-11-26"]))
    out = data.appliquer_cotations(p, {"A": dict(prix=9.0, jour=dt.date(2026, 11, 26))})
    assert out.loc["2026-11-26", "A"] == 9.0 and out.loc["2026-11-25", "A"] == 1.0
    out = data.appliquer_cotations(p, {"A": dict(prix=9.0, jour=dt.date(2026, 11, 27))})
    assert len(out) == 3 and out.iloc[-1]["B"] == 4.0
    assert data.appliquer_cotations(p, {"A": dict(prix=9.0, jour=dt.date(2026, 11, 20))}).equals(p)


def test_horaires_de_marche():
    import datetime as dt
    from boussole import data
    utc = dt.timezone.utc
    assert data.marche_ouvert("MC.PA", dt.datetime(2026, 11, 26, 10, 0, tzinfo=utc))       # 11 h à Paris
    assert not data.marche_ouvert("MC.PA", dt.datetime(2026, 11, 28, 10, 0, tzinfo=utc))   # samedi
    assert not data.marche_ouvert("AAPL", dt.datetime(2026, 11, 26, 10, 0, tzinfo=utc))    # 5 h à New York
    assert data.marche_ouvert("AAPL", dt.datetime(2026, 11, 26, 15, 0, tzinfo=utc))


def test_inscription_prenom_nom(tmp_path, monkeypatch):
    import pytest
    from boussole import comptes
    monkeypatch.setattr(comptes, "DOSSIER", tmp_path)
    with pytest.raises(comptes.ErreurCompte):
        comptes.creer_compte("a@b.fr", "Martin", "boussole2026", prenom=" ")
    uid = comptes.creer_compte("a@b.fr", "Martin", "boussole2026", prenom="Camille")
    c = comptes.compte_par_uid(uid)
    assert (c["prenom"], c["nom"]) == ("Camille", "Martin")
