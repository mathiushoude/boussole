"""Boussole — conseiller de portefeuille d'actions (comptes locaux, données Yahoo Finance).

Lancement :  streamlit run app.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from boussole import comptes, profil_risque as pr
from boussole.catalogue import CATALOGUE
from boussole import data, engine, news as nw, rules, score as sc, theme, ui
from boussole.config import (PARIS, aujourdhui, maintenant, ACTIONS_PAR_DEFAUT, CAPITAL_INITIAL, JOURS_PAR_AN, MAX_ACTIONS, UNIVERS, Profil,
                             Regles, place)
from boussole.portfolio import OperationRefusee, Portefeuille, allouer

st.set_page_config(page_title="Boussole", page_icon=str(Path(__file__).parent / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="auto")

ss = st.session_state
H = ui.html_bloc


# =========================================================================== #
# Compte et état de l'utilisateur (fichiers locaux, aucun envoi externe)
# =========================================================================== #
def etat_vierge() -> dict:
    return {}


def sauver() -> None:
    if not ss.get("uid"):
        return
    fichier = comptes.fichier_etat(ss.uid)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    sim = ss.get("sim") or {}
    etat = dict(tickers=ss.tickers, allocation=ss.allocation, capital=ss.capital, noms=ss.noms_perso,
                regles=ss.regles.to_dict(), profil=asdict(ss.profil), pilote=ss.pilote, configure=ss.configure,
                suivi=ss.suivi, guide=ss.guide,
                portefeuille=ss.pf.to_dict() if ss.pf else None,
                portefeuille_demo=ss.pf_demo.to_dict() if ss.get("pf_demo") else None,
                simulation=dict(jour=sim.get("jour", 0), t0=sim.get("t0"),
                                portefeuille=sim["pf"].to_dict() if sim.get("pf") else None))
    tmp = fichier.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(fichier)


def initialiser(uid: str) -> None:
    if ss.get("init") == uid:
        return
    etat = {}
    fichier = comptes.fichier_etat(uid)
    if fichier.exists():
        try:
            etat = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            etat = {}
    compte = comptes.compte_par_uid(uid) or {}
    ss.tickers = etat.get("tickers") or list(ACTIONS_PAR_DEFAUT)
    ss.capital = float(etat.get("capital") or CAPITAL_INITIAL)
    ss.noms_perso = etat.get("noms") or {}          # noms et places de cotation trouvés par la recherche
    ss.allocation = etat.get("allocation") or {t: ss.capital / len(ss.tickers) for t in ss.tickers}
    ss.regles = Regles.from_dict(etat.get("regles"))
    ss.profil = Profil(**{k: v for k, v in (etat.get("profil") or {}).items() if k in Profil.__dataclass_fields__})
    if not etat.get("profil"):
        ss.profil.prenom = compte.get("prenom") or ""
        ss.profil.nom_affiche = " ".join(x for x in (ss.profil.prenom, compte.get("nom")) if x) or ss.profil.nom_affiche
        ss.profil.mode = ss.get("mode_pre", ss.profil.mode)
    if ss.profil.source_donnees not in data.SOURCES:        # anciennes valeurs « Auto » / « Simulée »
        ss.profil.source_donnees = data.DEMO if ss.profil.source_donnees == "Simulée" else data.YAHOO
    ss.pilote = bool(etat.get("pilote", False))
    ss.configure = bool(etat.get("configure", False))
    ss.suivi = etat.get("suivi") or "reel"            # « reel » : mon portefeuille · « simulation » : année passée
    ss.guide = etat.get("guide") or dict(masque=False, pourquoi=False)
    ss.pf = Portefeuille.from_dict(etat["portefeuille"]) if etat.get("portefeuille") else None
    ss.pf_demo = Portefeuille.from_dict(etat["portefeuille_demo"]) if etat.get("portefeuille_demo") else None
    sim = etat.get("simulation") or {}
    ss.sim = dict(jour=int(sim.get("jour", 0)), t0=sim.get("t0"),
                  pf=Portefeuille.from_dict(sim["portefeuille"]) if sim.get("portefeuille") else None)
    ss.lecture = False
    ss.backtest = None
    ss.precedent = {}
    ss.init = uid


def deconnecter() -> None:
    comptes.fermer_session(ss.get("jeton"))
    st.query_params.clear()
    mode = ss.profil.mode if "profil" in ss else "Sombre"
    for cle in list(ss.keys()):
        del ss[cle]
    ss.mode_pre = mode
    st.query_params["theme"] = mode
    st.rerun()


def utilisateur() -> str | None:
    if ss.get("uid"):
        return ss.uid
    jeton = st.query_params.get("s")
    uid = comptes.session_uid(jeton)
    if uid:
        ss.uid, ss.jeton = uid, jeton
    return uid


UID = utilisateur()
if UID:
    initialiser(UID)          # le profil (donc le thème choisi) est connu avant le premier affichage
if "theme" in st.query_params and st.query_params["theme"] in theme.MODES and "mode_pre" not in ss:
    ss.mode_pre = st.query_params["theme"]   # thème choisi sur la page de connexion, conservé au rechargement

# Mode clair / sombre (charte : seuls les rôles de couleur changent)
if UID and "profil" in ss and ss.profil.mode not in theme.MODES:     # ancien réglage « Automatique »
    ss.profil.mode = "Clair" if getattr(st.context.theme, "type", None) == "light" else "Sombre"
if ss.get("mode_pre") not in theme.MODES:
    ss.mode_pre = "Sombre"
_mode = ss.profil.mode if (UID and "profil" in ss) else ss.mode_pre
TK = theme.jetons(_mode, getattr(st.context.theme, "type", None))
if theme.appliquer_streamlit(TK):
    st.rerun()
ui.injecter_style(TK, ss.profil.animations if (UID and "profil" in ss) else True,
                 ouverture=not ss.get("_ouvert"))
ss["_ouvert"] = True


# =========================================================================== #
# Page de connexion / inscription
# =========================================================================== #
def page_connexion() -> None:
    H(ui.CSS_PLEINE_PAGE + ui.ecran("connexion"))
    st.write("")
    g, _, d = st.columns([1.1, .12, 1], vertical_alignment="center")
    with g:
        H(f"""<div class="accroche"><div class="bs-zone">{ui.rose(210)}
          <div><div class="titre-xl">Boussole</div>
          <div class="petit" style="font-size:17px;line-height:26px;margin:.4rem 0 .8rem">
          Orienter vos décisions d'investissement, sans jargon.</div>
          <div id="bs-msg" class="bs-msg">Le nord, toujours. Cliquez sur la boussole pour jouer à « Trouvez le nord ».</div>
          <div id="bs-record" class="bs-record"></div></div></div>
          {ui.atout("1", "Vos actions du monde entier", "Cours Yahoo Finance réels, convertis en euros, et actualités de médias reconnus.")}
          {ui.atout("2", "Un conseil à votre mesure", "Un questionnaire de 2 minutes définit votre profil de risque : chaque recommandation en tient compte.")}
          {ui.atout("3", "Vous gardez la main", "Acheter, attendre ou vendre : Boussole explique chaque signal, vous décidez.")}
          </div>""")
    with d:
        _, cm = st.columns([1, 1])
        m = cm.segmented_control("Thème", theme.MODES, default=ss.mode_pre, key="theme_connexion",
                                 label_visibility="collapsed")
        if m and m != ss.mode_pre:
            ss.mode_pre = m; st.query_params["theme"] = m; st.rerun()
        H(ui.etapes(0))
        choix = st.segmented_control("Accès", ["Se connecter", "Créer un compte"], default=ss.get("acces", "Se connecter"),
                                     key="acces", label_visibility="collapsed") or "Se connecter"
        if choix == "Se connecter":
            with st.form("form_connexion", border=True):
                H('<div class="titre" style="font-size:24px">Bon retour parmi nous</div>'
                  '<div class="petit" style="margin-bottom:.6rem">Connectez-vous pour retrouver votre portefeuille.</div>')
                email = st.text_input("Adresse e-mail", placeholder="vous@exemple.fr", autocomplete="username")
                mdp = st.text_input("Mot de passe", type="password", autocomplete="current-password")
                ok = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
            if ok:
                try:
                    ouvrir(comptes.connecter(email, mdp))
                except comptes.ErreurCompte as exc:
                    st.error(str(exc))
        else:
            with st.form("form_inscription", border=True):
                H('<div class="titre" style="font-size:24px">Créer votre compte</div>'
                  '')
                c1, c2 = st.columns(2)
                prenom = c1.text_input("Prénom", placeholder="Camille", autocomplete="given-name")
                nom = c2.text_input("Nom", placeholder="Dupont", autocomplete="family-name")
                email = st.text_input("Adresse e-mail", placeholder="vous@exemple.fr", autocomplete="email",
                                      help="Sert uniquement d'identifiant sur cet ordinateur : rien n'est envoyé.")
                mdp = st.text_input("Mot de passe", type="password", autocomplete="new-password",
                                    help="Au moins 8 caractères, dont une lettre et un chiffre.")
                mdp2 = st.text_input("Confirmer le mot de passe", type="password", autocomplete="new-password")
                cgu = st.checkbox("J'ai compris que Boussole est un outil d'aide à la décision et non un conseil en "
                                  "investissement personnalisé.")
                ok = st.form_submit_button("Créer mon compte", type="primary", use_container_width=True)
            if ok:
                if mdp != mdp2:
                    st.error("Les deux mots de passe ne correspondent pas.")
                elif not cgu:
                    st.error("Merci de cocher la case d'information pour continuer.")
                else:
                    try:
                        ouvrir(comptes.creer_compte(email, nom, mdp, prenom=prenom))
                    except comptes.ErreurCompte as exc:
                        st.error(str(exc))
        H('<div class="legende" style="margin-top:.8rem">Compte local, mot de passe chiffré. Rien n\'est envoyé.</div>')
    st.write("")
    H(ui.avertissement())
    st.stop()


def ouvrir(uid: str) -> None:
    ss.uid = uid
    ss.jeton = comptes.ouvrir_session(uid)
    st.query_params["s"] = ss.jeton
    st.rerun()


if not UID:
    page_connexion()
initialiser(UID)
CAPITAL: float = ss.capital


def questionnaire(onboarding: bool) -> None:
    """Questionnaire de profil de risque (étape obligatoire de l'inscription, puis onglet « Mon profil »)."""
    p = ss.profil
    if pr.a_revoir(p.historique) and not onboarding:
        H(
          f'<div class="petit" style="margin-bottom:.8rem">'
          f'{"Vous n&#39;avez pas encore rempli le questionnaire." if not p.historique else "Votre dernière évaluation date de plus d&#39;un an."} '
          f'</div>')
    q_g, q_d = st.columns([1.5, 1], gap="medium")
    with q_g:
        with st.form("form_questionnaire"):
            reponses = {}
            for cle, question, options, aide in pr.QUESTIONS:
                libelles = [o[0] for o in options]
                idx = p.questionnaire.get(cle)
                reponses[cle] = st.radio(question, range(len(options)), format_func=lambda i, l=libelles: l[i],
                                         index=idx if idx is not None else None, horizontal=True,
                                         key=f"q_{cle}", help=aide or None)
            motifs = ["Première évaluation", "Mise à jour périodique", "Changement de situation professionnelle",
                      "Départ à la retraite", "Projet ou dépense importante à venir", "Héritage ou rentrée d'argent",
                      "Changement de situation familiale"]
            if onboarding:
                motif, auto = "Première évaluation", True
            else:
                motif = st.selectbox("Pourquoi faites-vous ce questionnaire ?",
                                     motifs, index=0 if not p.historique else 1)
                auto = st.toggle("Adapter automatiquement mes règles de décision à ce profil", value=p.regles_auto)
            valider = st.form_submit_button("Valider mon profil et continuer" if onboarding else "Calculer mon profil",
                                            type="primary", use_container_width=onboarding)
        if valider:
            manquantes = [q for c, q, _, _ in pr.QUESTIONS if reponses.get(c) is None]
            if manquantes:
                st.warning(f"Il reste {len(manquantes)} question(s) sans réponse.")
            else:
                score_r, profil_r, _ = pr.evaluer(reponses)
                ancien = p.profil_risque
                p.questionnaire = {k: int(v) for k, v in reponses.items()}
                p.profil_risque = profil_r
                p.historique = (p.historique + [pr.entree_historique(score_r, profil_r, motif)])[-20:]
                p.regles_auto = auto
                if auto:
                    ss.regles = pr.regles_pour(profil_r, ss.regles)
                    ss.backtest = None
                sauver()
                st.toast(f"Profil {profil_r.lower()}" + (f" (auparavant {ancien.lower()})" if ancien != profil_r
                                                          else " confirmé") + ".")
                st.rerun()
    with q_d:
        rep_courantes = {c: ss.get(f"q_{c}") for c, *_ in pr.QUESTIONS}
        complet = all(v is not None for v in rep_courantes.values())
        score_v, profil_v, plafonds = pr.evaluer(rep_courantes if complet else p.questionnaire)
        if not complet and not p.questionnaire:
            H(ui.carte(f'<div class="label">Votre profil</div><div class="titre" style="font-size:24px;margin:.3rem 0">'
                       f'Trois profils possibles</div>'
                       + "".join(f'<div class="raison"><b style="flex:none;min-width:84px">{k}</b>'
                                 f'<span class="petit">{ui.e(v)}</span></div>' for k, v in pr.DESCRIPTIONS.items()), 2))
            return
        role_v = {"Prudent": "buy", "Équilibré": "accent", "Dynamique": "wait"}[profil_v]
        reg = pr.REGLAGES[profil_v]
        lignes_r = "".join(
            f'<div class="raison"><span style="flex:1">{lab}</span><span class="mono">{val}</span></div>'
            for lab, val in [("Stop-loss", ui.pct(-reg["stop_loss"], 0)), ("Prise de bénéfices", ui.pct(reg["take_profit"], 0)),
                             ("Objectif hebdomadaire", ui.pct(reg["objectif_hebdo"], 0)),
                             ("Perte maximale par semaine", ui.pct(-reg["tolerance_hebdo"], 0)),
                             ("Liquidités engagées par achat", ui.pct(reg["part_achat"], 0, False)),
                             ("Poids maximal d'une valeur", ui.pct(reg["poids_max_ligne"], 0, False)),
                             ("Volatilité maximale à l'achat", ui.pct(reg["vol_max"], 0, False))])
        alerte_p = ("".join(f'<div class="petit neg" style="margin-top:.4rem">Profil plafonné : {ui.e(x)}</div>'
                            for x in plafonds))
        H(ui.carte(f'<div class="label">{"Aperçu de vos réponses" if complet else "Profil retenu"}</div>'
                   f'<div style="font-family:var(--serif);font-size:30px;font-weight:700;margin:.2rem 0" '
                   f'style="color:var(--{role_v})">{profil_v}</div>'
                   f'<div style="margin:.4rem 0">{ui.barre(score_v / 100 if (complet or p.questionnaire) else .75, role_v)}</div>'
                   f'<div class="legende">Score de risque <span class="mono">{score_v if (complet or p.questionnaire) else "—"}</span>/100 · '
                   f'Prudent &lt; 40 · Équilibré 40 à 69 · Dynamique ≥ 70</div>'
                   f'<div class="petit" style="margin:.8rem 0">{pr.DESCRIPTIONS[profil_v]}</div>{alerte_p}'
                   f'<div class="label" style="margin-top:.8rem">Ce que cela change</div>{lignes_r}', 2))
        if p.historique:
            st.write("")
            hist = "".join(
                f'<div class="raison"><span class="mono legende" style="min-width:78px">'
                f'{dt.date.fromisoformat(h["date"]):%d/%m/%Y}</span><span style="flex:1"><b>{ui.e(h["profil"])}</b>'
                f'<span class="legende"> · {ui.e(h["motif"])}</span></span><span class="mono">{h["score"]}</span></div>'
                for h in reversed(p.historique[-8:]))
            H(ui.carte(f'<div class="label">Historique de mon profil</div>{hist}', 3, plat=True))


def page_profil_obligatoire() -> None:
    H(ui.CSS_PLEINE_PAGE)
    H(ui.etapes(1) + ui.ecran("profil"))
    H(f"""<div class="entete-app" style="margin-bottom:.6rem">{ui.logo(44, 120)}<div>
      <div class="surtitre">Étape 2 sur 3</div>
      <div class="titre" style="margin:0">Faisons connaissance, {ui.e(ss.profil.prenom or ss.profil.nom_affiche)}</div></div></div>""")
    H(ui.guide("8 questions, 2 minutes. Pas de bonne ou de mauvaise réponse ; vous pourrez les modifier dans "
               "<b>Mon profil</b>."))
    questionnaire(True)
    c1, _, c3 = st.columns([1, 3, 1])
    if c3.button("Se déconnecter", use_container_width=True):
        deconnecter()
    st.stop()


if not ss.profil.historique:
    page_profil_obligatoire()


# =========================================================================== #
# Données
# =========================================================================== #
@st.cache_data(show_spinner=False, ttl=900)
def cours_cache(tickers: tuple, source: str, jour: dt.date) -> data.Cours:
    return data.charger_cours(list(tickers), source)


@st.cache_data(show_spinner=False, ttl=86400)
def fond_brut(ticker: str, source: str) -> dict:
    return data.fondamentaux(ticker, 1.0, source)


@st.cache_data(show_spinner=False, ttl=600)
def actus_reelles(ticker: str, nom: str) -> tuple[list[dict], list[str], str]:
    items, erreurs = nw.actualites(ticker, nom)
    return items, erreurs, maintenant().strftime("%H:%M")


@st.cache_data(show_spinner=False, ttl=20)
def cotations_cache(tickers: tuple, devises: tuple) -> tuple[dict, str | None]:
    """Derniers cours minute par minute ; au plus une requête Yahoo toutes les 20 s pour toute l'application."""
    try:
        return data.cotations(list(tickers), dict(devises)), None
    except Exception as exc:                      # la cause est affichée dans le bandeau « en direct »
        return {}, (str(exc) if isinstance(exc, data.DonneesIndisponibles) else type(exc).__name__)


@st.cache_data(show_spinner=False, ttl=60)
def intraday_cache(ticker: str, devise: str) -> pd.Series | None:
    return data.intraday(ticker, devise)


@st.cache_data(show_spinner=False, ttl=3600)
def recherche_cache(requete: str) -> list[dict]:
    return data.rechercher_titres(requete)


@st.cache_data(show_spinner=False, ttl=600)
def indice_cache(symbole: str) -> dict | None:
    return data.indice_marche(symbole)


def fondamentaux_du_jour(cours: pd.DataFrame, t: int, source: str) -> dict[str, dict]:
    out = {}
    for tk in cours.columns:
        f = dict(fond_brut(tk, source))
        prix_t = float(cours[tk].iloc[t])
        if f.get("devise", "EUR") not in ("EUR", None) and f.get("dpa"):      # dividende et cours en devise
            prix_t = f.get("prix_natif") or None
        f["rendement"] = (f["dpa"] / prix_t if (f.get("dpa") and prix_t)
                          else (0.0 if f.get("dpa") == 0 else None))
        f["score"], f["criteres"] = data.score_fondamental(f)
        out[tk] = f
    return out


def actus(tk: str) -> tuple[list[dict], list[str], str]:
    if SOURCE == data.DEMO:
        return data.actualites_demo(tk, COURS[tk], T), [], ""
    return actus_reelles(tk, NOMS[tk])


def nom_titre(tk: str) -> str:
    if tk in UNIVERS:
        return UNIVERS[tk]["nom"]
    if tk in CATALOGUE:
        return CATALOGUE[tk]["nom"]
    return (ss.noms_perso.get(tk) or {}).get("nom") or tk


def place_titre(tk: str) -> str:
    connue = place(tk)[0]
    if connue != "Autre place":
        return connue
    return (ss.noms_perso.get(tk) or {}).get("bourse") or ""


def secteur_titre(tk: str) -> str:
    if tk in UNIVERS:
        return UNIVERS[tk]["secteur"]
    if tk in CATALOGUE:
        return CATALOGUE[tk]["secteur"]
    p = ss.noms_perso.get(tk) or {}
    return p.get("secteur") or p.get("type") or "—"


def tout_actualiser() -> None:
    cours_cache.clear(); fond_brut.clear(); actus_reelles.clear(); indice_cache.clear(); intraday_cache.clear()
    for fichier in data.CACHE_DIR.glob("fond_*.json"):
        fichier.unlink(missing_ok=True)


def ecran_erreur(message: str) -> None:
    H(f"""<div class="erreur">{ui.logo(72, 0, True)}
      <div class="titre" style="margin-top:1rem">Impossible de récupérer les cours</div>
      <div class="trait" style="margin:.6rem auto 1rem"></div>
      <div style="font-size:15px;line-height:22px">{ui.e(message)}</div>
      <div class="petit" style="margin-top:1rem">Vérifiez votre connexion puis réessayez.</div></div>""")
    st.write("")
    _, c1, c2, _ = st.columns([1, 1, 1.4, 1])
    if c1.button("Réessayer", type="primary", use_container_width=True):
        tout_actualiser(); st.rerun()
    if c2.button("Explorer en mode démonstration", use_container_width=True,
                 help="Données fictives, clairement signalées, pour découvrir l'application sans connexion"):
        ss.profil.source_donnees = data.DEMO; sauver(); st.rerun()
    _, c, _ = st.columns([1, 2.4, 1])
    with c.expander("Modifier ma sélection d'actions"):
        choix = st.multiselect("Mes actions", list(dict.fromkeys(catalogue_complet() + ss.tickers)), default=ss.tickers,
                               max_selections=MAX_ACTIONS, format_func=lambda x: f"{nom_titre(x)} ({x})")
        if st.button("Enregistrer la sélection", disabled=not choix):
            ss.tickers = choix
            sauver(); st.rerun()
    st.stop()


def _ajout(ajouter, sym: str, r: dict | None) -> None:
    if r:
        ss.noms_perso[sym] = r
    ajouter(sym, r)


def bloc_recherche(dans: list[str], ajouter, cle: str, demo: bool) -> None:
    """Recherche Yahoo Finance (toutes les bourses) avec bouton « Ajouter » pour chaque résultat."""
    requete = st.text_input("Rechercher une action ou un ETF", placeholder="Nom ou symbole : Apple, Toyota, Nestlé, SAP.DE…",
                            key=f"rech_{cle}", label_visibility="collapsed")
    q = requete.strip()
    if not q:
        if cle == "init":          # la liste déroulante juste au-dessus contient déjà tout le catalogue
            return
        cat = [t for t in catalogue_complet() if t not in dans]

        def _choisi() -> None:
            sym = ss.get(f"cat_{cle}")
            if sym:
                ss[f"cat_{cle}"] = None
                _ajout(ajouter, sym, None)
        st.selectbox("Catalogue", cat, index=None, key=f"cat_{cle}", label_visibility="collapsed",
                     placeholder=f"Ou parcourez les {len(cat)} actions et ETF du catalogue…",
                     format_func=libelle_titre, disabled=len(dans) >= MAX_ACTIONS, on_change=_choisi)
        return
    ql = q.lower()
    locaux = [t for t in catalogue_complet() if ql in t.lower() or ql in nom_titre(t).lower()][:6]
    distants = [r_ for r_ in (recherche_cache(q) if len(q) >= 2 and not demo else [])
                if r_["symbole"] not in locaux][:max(0, 8 - len(locaux))]
    resultats = [dict(symbole=t, nom=nom_titre(t), bourse=place(t)[0], type=secteur_titre(t), local=True)
                 for t in locaux] + distants
    if resultats:
        for r_ in resultats:
            deja = r_["symbole"] in dans
            c_t, c_b = st.columns([4, 1.25], vertical_alignment="center")
            c_t.markdown(f'<div class="ligne-recherche"><b>{ui.e(r_["nom"])}</b><div class="legende">'
                         f'<span class="mono">{ui.e(r_["symbole"])}</span> · {ui.e(r_["bourse"] or place(r_["symbole"])[0])}'
                         f' · {ui.e(r_["type"])}</div></div>', unsafe_allow_html=True)
            c_b.button("Ajoutée" if deja else "Ajouter", key=f"aj_{cle}_{r_['symbole']}",
                       disabled=deja or len(dans) >= MAX_ACTIONS, use_container_width=True,
                       on_click=_ajout, args=(ajouter, r_["symbole"], None if r_.get("local") else r_))
    else:
        sym = q.upper().replace(" ", "")
        st.caption("Aucun résultat. Vous pouvez ajouter le symbole tel quel.")
        st.button(f"Ajouter le symbole {sym}", key=f"aj_brut_{cle}", disabled=sym in dans or len(dans) >= MAX_ACTIONS,
                  on_click=_ajout, args=(ajouter, sym, None))


def catalogue_complet() -> list[str]:
    """Toutes les valeurs proposées d'office : catalogue intégré, puis titres trouvés par la recherche."""
    return list(dict.fromkeys(list(CATALOGUE) + list(UNIVERS) + list(ss.noms_perso)))


def libelle_titre(tk: str) -> str:
    return f"{nom_titre(tk)} · {place_titre(tk) or '—'} ({tk})"


def page_portefeuille_initial() -> None:
    H(ui.CSS_PLEINE_PAGE)
    H(ui.etapes(2) + ui.ecran("portefeuille"))
    reg = pr.REGLAGES[ss.profil.profil_risque]
    H(f"""<div class="entete-app" style="margin-bottom:.6rem">{ui.logo(44, 240)}<div>
      <div class="surtitre">Étape 3 sur 3</div>
      <div class="titre" style="margin:0">Composez votre portefeuille</div></div></div>""")
    H(ui.guide(f"Profil <b>{ui.e(ss.profil.profil_risque.lower())}</b> : au plus <b>{reg['poids_max_ligne'] * 100:.0f} %</b> "
               f"du capital par valeur. Tout reste modifiable dans <b>Mes actions</b>."))
    if "choix_init" not in ss:
        ss.choix_init = list(ss.tickers)

    def ajouter(sym, _r):
        ss.choix_init = ss.choix_init + [sym]
        ss[f"rech_init"] = ""

    g, d = st.columns([1, 1], gap="large")
    with g:
        ui.section("1. Le montant à investir")
        capital = float(st.number_input("Capital (€)", min_value=1_000.0, max_value=100_000_000.0, value=float(ss.capital),
                                        step=1_000.0, format="%.0f", key="cap_init",
                                        help="Somme que vous souhaitez confier à Boussole. Vous pourrez ajouter ou "
                                             "retirer des liquidités plus tard."))
        ui.section("3. La répartition")
        mode_r = st.radio("Répartition", ["À parts égales", "Je répartis moi-même"], horizontal=True,
                          label_visibility="collapsed", key="mode_rep")
    with d:
        ui.section("2. Vos actions")
        options = list(dict.fromkeys(catalogue_complet() + ss.choix_init))
        choix = st.multiselect(f"Ma sélection ({len(ss.choix_init)} / {MAX_ACTIONS})", options, key="choix_init",
                               max_selections=MAX_ACTIONS, format_func=libelle_titre,
                               placeholder=f"Tapez un nom parmi {len(options)} actions et ETF…")
        bloc_recherche(choix, ajouter, "init", ss.profil.source_donnees == data.DEMO)
    alloc = {}
    if choix:
        egal = capital / len(choix)
        if mode_r == "À parts égales":
            alloc = {t_: egal for t_ in choix}
        else:
            cols = st.columns(min(len(choix), 5))
            for i, t_ in enumerate(choix):
                with cols[i % len(cols)]:
                    alloc[t_] = float(st.number_input(f"{nom_titre(t_)}", 0.0, capital, float(int(egal)),
                                                      step=1_000.0, format="%.0f", key=f"ini_{t_}"))
        total = sum(alloc.values())
        trop = [nom_titre(t_) for t_, v in alloc.items() if v > capital * reg["poids_max_ligne"] + 1]
        H(ui.carte(f'<div style="display:flex;justify-content:space-between"><span class="label">Total investi</span>'
                   f'<span class="mono {"neg" if total > capital else ""}">{ui.euros(total)} / {ui.euros(capital)}</span>'
                   f'</div><div style="margin:.5rem 0">{ui.barre(min(total / capital, 1), "sell" if total > capital else "accent")}'
                   f'</div><div class="petit">Liquidités conservées : <span class="mono">{ui.euros(max(capital - total, 0))}'
                   f'</span></div>'
                   + (f'<div class="petit" style="color:var(--wait);margin-top:.4rem">Attention : {ui.e(", ".join(trop))} '
                      f'dépasse{"nt" if len(trop) > 1 else ""} {reg["poids_max_ligne"] * 100:.0f} % du capital, la limite '
                      f'conseillée pour votre profil. Ajoutez des valeurs ou réduisez ce montant.</div>' if trop else ""),
                   plat=True))
    st.write("")
    c1, c2, _ = st.columns([1.3, 1, 2])
    if c1.button("Créer mon portefeuille", type="primary", use_container_width=True,
                 disabled=not choix or sum(alloc.values()) > capital + 1):
        ss.tickers, ss.capital, ss.allocation = list(choix), capital, alloc
        ss.configure, ss.pf, ss.suivi = True, None, "reel"
        sauver()
        st.rerun()
    if c2.button("Revenir au profil", use_container_width=True):
        ss.profil.historique = []
        sauver(); st.rerun()
    st.stop()


if not ss.configure:
    page_portefeuille_initial()


try:
    with st.spinner("Récupération des cours sur Yahoo Finance…"):
        DONNEES: data.Cours = cours_cache(tuple(ss.tickers), ss.profil.source_donnees, aujourdhui())
except data.DonneesIndisponibles as exc:
    ecran_erreur(str(exc))
COURS, SOURCE, MSG_SOURCE = DONNEES.prix, DONNEES.source, DONNEES.message
DEMO = SOURCE == data.DEMO
# Cours en direct : le dernier cours Yahoo (minute par minute) remplace la clôture de la séance du jour.
COT, ERR_COT = ({}, None) if DEMO else cotations_cache(tuple(COURS.columns),
                                                        tuple(sorted((DONNEES.devises or {}).items())))
COURS = data.appliquer_cotations(COURS, COT)
ss["cot_page"] = {t_: c_["prix"] for t_, c_ in COT.items()}
ss["maj_page"] = time.time()
HORS_LIGNE = DONNEES.maj.strftime("%d/%m à %H:%M") if DONNEES.hors_ligne else None
N = len(COURS)
DATES = COURS.index
NOMS = {tk: (nom_titre(tk) if (tk in UNIVERS or tk in CATALOGUE or tk in ss.noms_perso or DEMO)
             else (fond_brut(tk, SOURCE).get("nom") or tk)) for tk in COURS.columns}
DEVISES = DONNEES.devises or {}

SIMU = ss.suivi == "simulation"   # simulateur : rejouer l'année passée avec un portefeuille d'entraînement
CLE_PF = "pf_demo" if DEMO else "pf"   # le mode démonstration a son propre portefeuille, fictif
if ss.get(CLE_PF) is None:         # portefeuille réel : constitué au dernier cours connu
    ss[CLE_PF] = allouer(ss.capital, {t_: v for t_, v in ss.allocation.items() if t_ in COURS}, COURS, N - 1,
                         DATES[N - 1], motif="Investissement initial")
    for x in ss[CLE_PF].transactions:
        x["enregistre"] = maintenant().isoformat(timespec="seconds")
    sauver()
ss[CLE_PF].recaler(DATES)
ss[CLE_PF].horodatage = True
if SIMU:
    T0 = max(N - JOURS_PAR_AN, 60)
    sim = ss.sim
    if (sim["pf"] is None or sim["t0"] != T0
            or any(x["t"] >= N or (x["sens"] in ("Achat", "Vente") and x["ticker"] not in COURS)
                   for x in sim["pf"].transactions)):
        sim["pf"] = allouer(CAPITAL, {t_: v for t_, v in ss.allocation.items() if t_ in COURS}, COURS, T0, DATES[T0])
        sim["t0"], sim["jour"] = T0, 0
    sim["jour"] = max(0, min(sim["jour"], N - 1 - T0))
    T = T0 + sim["jour"]
    PF: Portefeuille = sim["pf"]
else:
    T = N - 1
    PF = ss[CLE_PF]
    T0 = min([x["t"] for x in PF.transactions], default=T)
REGLES: Regles = ss.regles
INDS = engine.indicateurs(COURS, REGLES)
FONDS = fondamentaux_du_jour(COURS, T, SOURCE)
DERNIERE = T == N - 1          # séance la plus récente : les actualités du jour s'appliquent au score
RISQUE, RECS = engine.analyser(COURS, INDS, PF, T, T0, REGLES, FONDS)
POS = PF.positions(T, COURS)
ACTUS_BRUT = {tk: actus(tk) for tk in COURS.columns}
ACTUS = {tk: v[0] for tk, v in ACTUS_BRUT.items()}
SIGNAUX = {tk: sc.signal(RECS[tk], INDS[tk].iloc[: T + 1], FONDS[tk], ACTUS[tk] if (DERNIERE or DEMO) else [],
                         REGLES, POS.get(tk))
           for tk in COURS.columns}
G_CODE, G_SCORE, G_CONF = sc.signal_global(list(SIGNAUX.values()), RISQUE.suspendre_achats)

VALEUR = PF.valeur(T, COURS)
LIQ = PF.liquidites(T)
GAIN = VALEUR - PF.apports(T)
PREC = ss.precedent            # valeurs du rendu précédent : les chiffres glissent de l'ancienne à la nouvelle
ss.precedent = dict(valeur=VALEUR, gain=GAIN, liq=LIQ, **{f"c_{tk}": float(COURS[tk].iloc[T]) for tk in COURS})


def aide() -> bool:
    return bool(ss.profil.aides)


def fmt_date(d) -> str:
    return pd.Timestamp(d).strftime("%d/%m/%Y")


def avancer(n: int) -> None:
    """Fait avancer l'horloge ; le pilote automatique applique les recommandations à chaque séance."""
    faites = []
    for _ in range(n):
        if T0 + ss.sim["jour"] >= N - 1:
            break
        ss.sim["jour"] += 1
        if ss.pilote:
            t = T0 + ss.sim["jour"]
            _, recs = engine.analyser(COURS, INDS, PF, t, T0, REGLES, fondamentaux_du_jour(COURS, t, SOURCE))
            faites += engine.executer(PF, recs, COURS, t, REGLES, ss.allocation, CAPITAL)
    sauver()
    if faites:
        st.toast(f"Pilote automatique : {len(faites)} opération(s) exécutée(s).")


# =========================================================================== #
# Barre latérale : identité, horloge de simulation, mode d'affichage
# =========================================================================== #
with st.sidebar:
    H(f"""<div style="display:flex;align-items:center;gap:.8rem;margin:.2rem 0 1rem">
      {ui.logo(48, G_SCORE * .9, bool(HORS_LIGNE))}
      <div style="font-family:var(--serif);font-weight:700;font-size:26px;line-height:30px">Boussole</div></div>""")
    if not SIMU:
        ouverture = fmt_date(DATES[T0]) if PF.transactions else "aujourd'hui"
        H(ui.carte(f"""<div class="label">{"Portefeuille de démonstration" if DEMO else "Mon portefeuille"}</div>
          <div class="valeur" style="font-size:20px">{fmt_date(DATES[T])}</div>
          <div class="petit" style="margin:.1rem 0 .2rem">Ouvert le {ouverture}</div>""", plat=True))
        st.write("")
        if st.button("Simulateur : rejouer l'année passée", use_container_width=True,
                     help="S'entraîner sans toucher à votre portefeuille : un portefeuille d'essai rejoue la dernière "
                          "année de bourse, séance par séance."):
            ss.suivi = "simulation"; sauver(); st.rerun()
    else:
        jours_max = N - 1 - T0
        H(ui.carte(f"""<div class="label">Simulateur · séance du</div>
          <div class="valeur" style="font-size:20px">{fmt_date(DATES[T])}</div>
          <div class="petit" style="margin:.1rem 0 .6rem">Jour {ss.sim["jour"]} sur {jours_max} · portefeuille d'essai</div>
          {ui.barre(ss.sim["jour"] / max(jours_max, 1))}""", plat=True))
        st.write("")
        c1, c2, c3 = st.columns(3)
        if c1.button("+1 J", use_container_width=True, help="Avancer d'une séance"):
            avancer(1); st.rerun()
        if c2.button("+1 S", use_container_width=True, help="Avancer d'une semaine (5 séances)"):
            avancer(5); st.rerun()
        if c3.button("+1 M", use_container_width=True, help="Avancer d'un mois (21 séances)"):
            avancer(21); st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Début", use_container_width=True, help="Revenir au début de l'année (efface les opérations d'essai)"):
            ss.sim["pf"] = None; sauver(); st.rerun()
        if c2.button("Fin", use_container_width=True, disabled=T == N - 1, help="Aller à la dernière séance connue"):
            avancer(N); st.rerun()
        ss.lecture = st.toggle("Lecture automatique", value=ss.lecture, help="Fait défiler les séances une à une")
        pilote = st.toggle("Pilote automatique", value=ss.pilote,
                           help="Applique automatiquement les recommandations à chaque séance du simulateur")
        if pilote != ss.pilote:
            ss.pilote = pilote; sauver()
        if st.button("Revenir à mon portefeuille", type="primary", use_container_width=True):
            ss.suivi = "reel"; ss.lecture = False; sauver(); st.rerun()
    mode = st.segmented_control("Affichage", theme.MODES, default=ss.profil.mode, key="mode_affichage")
    if mode and mode != ss.profil.mode:
        ss.profil.mode = mode; sauver(); st.rerun()
    if not DEMO:
        st.toggle("Cours en direct", value=True, key="direct_auto",
                  help="La page se met à jour d'elle-même quand un cours bouge (toutes les 30 s au plus).")
    H(ui.risque(RISQUE.niveau, RISQUE.message))
    if HORS_LIGNE:
        H(f'<div class="legende">{ui.e(MSG_SOURCE)}</div>')



# =========================================================================== #
# Graphiques (langage des données de la charte)
# =========================================================================== #
PERIODES = {"1J": 1, "2J": 2, "5J": 5, "1M": 21, "3M": 63, "6M": 126, "1A": 252, "2A": 504}
INTRA = {"1J", "2J", "5J"}


def adequation_html(tk: str, court: bool = False) -> str:
    niveau, texte = pr.adequation(engine.volatilite(COURS[tk], T), ss.profil.profil_risque)
    role = {"ok": "buy", "limite": "wait", "risque": "sell"}.get(niveau, "muted")
    if court:
        return (f'<div class="legende" title="{ui.e(texte)}" style="margin-top:.2rem"><span style="display:inline-block;'
                f'width:7px;height:7px;border-radius:50%;background:var(--{role});margin-right:5px"></span>'
                f'{ {"ok": "adaptée à mon profil", "limite": "à la limite de mon profil", "risque": "trop risquée pour mon profil"}.get(niveau, "profil : n.d.") }</div>')
    return (f'<span class="petit" style="display:inline-flex;align-items:center;gap:6px;padding:3px 10px;'
            f'border:1px solid var(--border);border-radius:999px"><span style="width:8px;height:8px;border-radius:50%;'
            f'background:var(--{role})"></span>{ui.e(texte)}</span>')


def conv_note(tk: str) -> str:
    dev = DEVISES.get(tk)
    if dev and dev != "EUR":
        return f'<span class="legende" title="Cours d\'origine en {ui.e(dev)}, convertis au taux du jour">converti depuis {ui.e(dev)}</span>'
    return ""


def serie_intraday(tk: str, jours: int) -> pd.Series | None:
    """Cours à 5 minutes des `jours` dernières séances, si l'on regarde la séance la plus récente en données réelles."""
    if DEMO or not DERNIERE:
        return None
    s = intraday_cache(tk, DEVISES.get(tk, "EUR"))
    if s is None or s.empty:
        return None
    jours_dispo = sorted(set(s.index.normalize()))
    return s[s.index.normalize() >= jours_dispo[-min(jours, len(jours_dispo))]]


def note_intraday(per: str, ok: bool) -> None:
    if per in INTRA and not ok:
        st.caption("Cours minute indisponibles : 10 dernières clôtures affichées.")


def fig_intraday(tk: str, s: pd.Series, hauteur: int) -> go.Figure:
    jour0 = s.index.normalize().min()
    avant = COURS[tk][COURS.index < jour0]
    ref = float(avant.iloc[-1]) if len(avant) else float(s.iloc[0])
    role = "buy" if s.iloc[-1] >= ref else "sell"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s, name="Cours", line=dict(color=TK["accent"], width=1.8),
                             fill="tozeroy", fillcolor=theme.rgba(TK["accent"], .13),
                             hovertemplate="%{y:.2f} €<extra></extra>"))
    fig.add_hline(y=ref, line=dict(color=TK["muted"], dash="dash", width=1),
                  annotation_text=f"Clôture précédente {ui.nombre(ref, 2)}", annotation_position="top left",
                  annotation_font=dict(color=TK["muted"], size=11))
    fig.add_trace(go.Scatter(x=[s.index[-1]], y=[s.iloc[-1]], mode="markers", showlegend=False, hoverinfo="skip",
                             marker=dict(size=9, color=TK[role], line=dict(color=TK["surface"], width=2))))
    lo, hi = min(s.min(), ref), max(s.max(), ref)
    marge = (hi - lo) * .08 or hi * .005
    fig.update_yaxes(range=[lo - marge, hi + marge], ticksuffix=" €")
    h = s.index.hour + s.index.minute / 60
    fin, debut = float(h.max()) + .1, float(h.min())
    breaks = [dict(bounds=["sat", "mon"])]
    if fin - debut < 23:
        breaks.append(dict(bounds=[fin, debut], pattern="hour"))
    var = s.iloc[-1] / ref - 1
    fig.update_layout(title=dict(text=f"{ui.nombre(float(s.iloc[-1]), 2)} € · {ui.pct(var, 2)} "
                                      f"<span style='font-size:12px'>données à 5 min, heure de Paris</span>",
                                 font=dict(size=15)))
    fig = ui.style_fig(fig, hauteur, False)
    fig.update_xaxes(rangebreaks=breaks, tickformat="%d/%m %H:%M" if s.index.normalize().nunique() > 1 else "%H:%M",
                     hoverformat="%d/%m %H:%M")
    return fig


def graphique_cours(tk: str, per: str, hauteur: int, cle: str) -> None:
    s = serie_intraday(tk, PERIODES[per]) if per in INTRA else None
    if s is not None:
        st.plotly_chart(fig_intraday(tk, s, hauteur), use_container_width=True, key=cle)
    else:
        st.plotly_chart(fig_cours(tk, 10 if per in INTRA else PERIODES[per], hauteur), use_container_width=True,
                        key=cle)
    note_intraday(per, s is not None)
SPL = dict(shape="spline", smoothing=.6)


def fig_cours(tk: str, n: int, hauteur: int = 520) -> go.Figure:
    debut = max(0, T - n)
    ind = INDS[tk].iloc[debut: T + 1]
    x = ind.index
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.04, row_heights=[.62, .19, .19])
    # Bollinger : bande remplie à 13 %, bords en pointillé
    fig.add_trace(go.Scatter(x=x, y=ind["bb_haut"], line=dict(color=TK["accent"], width=1, dash="dot", **SPL),
                             name="Bollinger (2σ)", legendgroup="bb", hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["bb_bas"], line=dict(color=TK["accent"], width=1, dash="dot", **SPL),
                             fill="tonexty", fillcolor=theme.rgba(TK["accent"], .13), showlegend=False,
                             legendgroup="bb", hoverinfo="skip"), row=1, col=1)
    sup, res = float(ind["support"].iloc[-1]), float(ind["resistance"].iloc[-1])
    fig.add_hline(y=sup, line=dict(color=TK["buy"], dash="dash", width=1.2), annotation_text="Support",
                  annotation_font=dict(color=TK["buy"], size=11), annotation_position="bottom left", row=1, col=1)
    fig.add_hline(y=res, line=dict(color=TK["sell"], dash="dash", width=1.2), annotation_text="Résistance",
                  annotation_font=dict(color=TK["sell"], size=11), annotation_position="top left", row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["cours"], name="Cours", line=dict(color=TK["text"], width=1.8, **SPL)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["mm_courte"], name=f"Moyenne mobile {REGLES.mm_courte}",
                             line=dict(color=TK["wait"], width=1.4, **SPL)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["mm_longue"], name=f"Moyenne mobile {REGLES.mm_longue}",
                             line=dict(color=TK["muted"], width=1.2, dash="dash", **SPL)), row=1, col=1)
    tx = [o for o in PF.transactions if o["ticker"] == tk and debut <= o["t"] <= T]
    for sens, sym, role in (("Achat", "triangle-up", "buy"), ("Vente", "triangle-down", "sell")):
        pts = [o for o in tx if o["sens"] == sens]
        if pts:
            fig.add_trace(go.Scatter(x=[DATES[o["t"]] for o in pts], y=[o["prix"] for o in pts], mode="markers",
                                     name=sens, marker=dict(symbol=sym, size=12, color=TK[role],
                                                            line=dict(color=TK["surface"], width=1.5)),
                                     text=[f'{sens} · {o["quantite"]} titres · {o["motif"]}' for o in pts],
                                     hovertemplate="%{text}<extra></extra>"), row=1, col=1)
    lo = min(ind["cours"].min(), ind["bb_bas"].min(), sup)
    hi = max(ind["cours"].max(), ind["bb_haut"].max(), res)
    fig.update_yaxes(range=[lo * .985, hi * 1.015], row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["rsi"], name="RSI / MACD", line=dict(color=TK["accent"], width=1.3, **SPL)),
                  row=2, col=1)
    for niv in (REGLES.rsi_survente, REGLES.rsi_surachat):
        fig.add_hline(y=niv, line=dict(color=TK["muted"], dash="dot", width=1), annotation_text=f"RSI {niv:.0f}",
                      annotation_position="top left", annotation_font=dict(color=TK["muted"], size=10), row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1, tickvals=[30, 70])
    h = ind["macd_hist"]
    fig.add_trace(go.Bar(x=x, y=h, marker=dict(color=[TK["buy"] if v >= 0 else TK["sell"] for v in h], cornerradius=2),
                         showlegend=False, name="Histogramme MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["macd"], showlegend=False, name="MACD",
                             line=dict(color=TK["accent"], width=1.3, **SPL)), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["macd_signal"], showlegend=False, name="Signal MACD",
                             line=dict(color=TK["wait"], width=1.2, **SPL)), row=3, col=1)
    fig.update_layout(bargap=.35)
    return ui.style_fig(fig, hauteur)


def valeur_reference() -> pd.Series:
    return allouer(CAPITAL, ss.allocation, COURS, T0, DATES[T0]).historique(COURS, T0, T)


SERIES = [(TK["accent"], "solid"), (TK["text"], "solid"), (TK["muted"], "solid"), (TK["accent"], "dash"),
          (TK["text"], "dot"), (TK["muted"], "dash"), (TK["accent"], "dot"), (TK["text"], "dash"),
          (TK["muted"], "dot"), (TK["accent"], "dashdot")]   # 10 séries sans les couleurs réservées aux signaux


# =========================================================================== #
# Dialogues (validation des opérations simulées par le client)
# =========================================================================== #
@st.dialog("Confirmer l'opération")
def dialogue_operation(op: dict) -> None:
    ss["dlg_t"] = time.time()   # pas d'actualisation automatique pendant une fenêtre ouverte
    sens, tk, qte, prix = op["sens"], op["ticker"], op["quantite"], op["prix"]
    H(ui.carte(f"""<div class="label">{ui.e(sens)} · {ui.e(NOMS[tk])}</div>
      <div class="valeur">{qte} × {ui.euros(prix, 2)}</div>
      <div class="mono" style="font-size:22px;margin:.2rem 0">{ui.euros(qte * prix, 2)}</div>
      <div class="petit">Séance du {fmt_date(DATES[T])} · liquidités après l'opération :
      <span class="mono">{ui.euros(LIQ - qte * prix if sens == "Achat" else LIQ + qte * prix)}</span></div>""",
               plat=True))
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("Confirmer", type="primary", use_container_width=True):
        try:
            if sens == "Achat":
                PF.acheter(T, DATES[T], tk, prix, quantite=qte, motif=op.get("motif", "Manuel"))
            else:
                PF.vendre(T, DATES[T], tk, prix, quantite=qte, motif=op.get("motif", "Manuel"))
            sauver()
            st.toast(f"{sens} de {qte} titres {NOMS[tk]} enregistré.")
            st.rerun()
        except OperationRefusee as exc:
            st.error(str(exc))
    if c2.button("Annuler", use_container_width=True):
        st.rerun()


@st.dialog("Appliquer les recommandations du jour")
def dialogue_appliquer() -> None:
    ss["dlg_t"] = time.time()   # pas d'actualisation automatique pendant une fenêtre ouverte
    actives = {tk: r for tk, r in RECS.items() if r.code != rules.RESTER}
    if not actives:
        st.info("Aucune recommandation d'achat ou de vente pour cette séance.")
        return
    for tk, r in actives.items():
        H(f'<div class="raison"><b style="min-width:130px">{ui.e(NOMS[tk])}</b>{ui.pastille(r.code)}'
          f'<span class="petit">{ui.e(r.raisons[0][1])}</span></div>')
    st.write("")
    if st.button("Tout valider", type="primary", use_container_width=True):
        faites = engine.executer(PF, actives, COURS, T, REGLES, ss.allocation, CAPITAL)
        sauver()
        st.toast(f"{len(faites)} opération(s) enregistrée(s).")
        st.rerun()


@st.dialog("Pourquoi ce signal ?", width="large")
def dialogue_pourquoi(tk: str) -> None:
    ss["dlg_t"] = time.time()   # pas d'actualisation automatique pendant une fenêtre ouverte
    s, rec = SIGNAUX[tk], RECS[tk]
    if not ss.guide.get("pourquoi"):
        ss.guide["pourquoi"] = True
        sauver()
    H(f'<div style="display:flex;align-items:center;gap:.8rem">{ui.pastille(s.code, True)}'
      f'<span class="mono">Score {ui.nombre(s.score, 0, True)} · Confiance {s.confiance}&#8239;%</span></div>')
    ui.section("Les règles appliquées")
    H("".join(ui.raison(r, t) for r, t in rec.raisons))
    if rec.alerte:
        H(ui.risque("alerte", rec.alerte))
    ui.section("Comment lire le score")
    H('<div class="petit">La décision vient des règles ci-dessus, appliquées dans cet ordre : protection du capital, '
      'signaux de vente, signaux d\'achat, puis attente. Le score situe la décision dans sa zone de la jauge '
      '(Vendre de −100 à −34, Attendre de −33 à +33, Acheter de +34 à +100) à partir des six piliers. '
      'La confiance mesure l\'accord entre les piliers : quand elle est faible, mieux vaut attendre.</div>')
    H("".join(ui.pilier(k, v) for k, v in s.piliers.items()))
    H(ui.avertissement())


@st.dialog("Valider la nouvelle sélection")
def dialogue_selection(tickers: list[str], allocation: dict[str, float], capital: float) -> None:
    ss["dlg_t"] = time.time()   # pas d'actualisation automatique pendant une fenêtre ouverte
    st.write("Le simulateur va redémarrer au début de l'année passée avec ce capital d'essai et cette répartition. "
             "Votre portefeuille réel n'est pas modifié.")
    H(f'<div class="raison"><b style="flex:1">Capital investi</b><span class="mono">{ui.euros(capital)}</span></div>')
    for tk in tickers:
        H(f'<div class="raison"><span style="flex:1">{ui.e(nom_titre(tk))} <span class="legende mono">{ui.e(tk)}'
          f'</span></span><span class="mono">{ui.euros(allocation[tk])}</span></div>')
    H(f'<div class="raison"><b style="flex:1">Liquidités</b><span class="mono">'
      f'{ui.euros(capital - sum(allocation.values()))}</span></div>')
    st.write("")
    if st.button("Confirmer et redémarrer", type="primary", use_container_width=True):
        ss.tickers, ss.allocation, ss.capital = list(tickers), dict(allocation), float(capital)
        for cle in [c for c in ss.keys() if str(c).startswith("alloc_") or c in ("capital_saisie", "capital_budget")]:
            del ss[cle]
        ss.sim["pf"], ss.backtest = None, None
        sauver()
        st.rerun()


@st.dialog("Investir selon la nouvelle répartition", width="large")
def dialogue_reequilibrage(cibles: dict[str, float]) -> None:
    ss["dlg_t"] = time.time()   # pas d'actualisation automatique pendant une fenêtre ouverte
    ordres = []
    for tk, cible in cibles.items():
        prix = float(COURS[tk].iloc[T])
        delta = int(cible // prix) - POS.get(tk, {}).get("quantite", 0)
        if delta and (abs(delta) * prix >= REGLES.montant_achat_min or cible == 0):   # pas de micro-ordres
            ordres.append((tk, "Vente" if delta < 0 else "Achat", abs(delta), prix))
    if not ordres:
        st.info("Votre portefeuille correspond déjà à cette répartition.")
        return
    ordres.sort(key=lambda o: o[1] != "Vente")          # les ventes d'abord, pour libérer des liquidités
    ventes = sum(q * p_ for _, sens, q, p_ in ordres if sens == "Vente")
    achats = sum(q * p_ for _, sens, q, p_ in ordres if sens == "Achat")
    apres = LIQ + ventes - achats
    st.write(f"Ordres passés au cours de clôture du {fmt_date(DATES[T])} :")
    H("".join(f'<div class="raison"><span style="flex:1">{ui.pastille(rules.ACHETER if sens == "Achat" else rules.VENDRE)}'
              f' &nbsp;{ui.e(sens)} de <span class="mono">{q}</span> {ui.e(NOMS[tk])}</span>'
              f'<span class="mono">{ui.euros(q * p_, 2)}</span></div>' for tk, sens, q, p_ in ordres))
    H(f'<div class="raison"><b style="flex:1">Liquidités après les ordres</b><span class="mono {"neg" if apres < 0 else ""}">'
      f'{ui.euros(apres)}</span></div>')
    if apres < -0.01:
        st.error("Liquidités insuffisantes : réduisez les montants ou faites un apport.")
        return
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("Confirmer les ordres", type="primary", use_container_width=True):
        for tk, sens, q, p_ in ordres:
            try:
                if sens == "Vente":
                    PF.vendre(T, DATES[T], tk, p_, quantite=q, motif="Rééquilibrage")
                else:
                    PF.acheter(T, DATES[T], tk, p_, quantite=q, motif="Rééquilibrage")
            except OperationRefusee as exc:
                st.error(f"{NOMS[tk]} : {exc}")
                return
        for cle in [c for c in ss.keys() if str(c).startswith("cible_")]:
            del ss[cle]
        sauver()
        st.toast(f"{len(ordres)} ordre(s) enregistré(s) dans l'historique.")
        st.rerun()
    if c2.button("Annuler", use_container_width=True):
        st.rerun()


# =========================================================================== #
# Onglets
# =========================================================================== #
# Bandeau de marché : indice, état de la connexion, actualisation
def bandeau_marche() -> None:
    """Uniquement quand les données ne sont pas en direct : mode démonstration ou Yahoo injoignable."""
    if not (DEMO or HORS_LIGNE):
        return
    g, d = st.columns([6, 1])
    if DEMO:
        g.markdown('<div class="marche"><span class="etat" style="--c:var(--wait)">Mode démonstration</span>'
                   '<span class="demo">données fictives</span></div>', unsafe_allow_html=True)
        if d.button("Données réelles", use_container_width=True, help="Revenir aux cours Yahoo Finance"):
            ss.profil.source_donnees = data.YAHOO; sauver(); st.rerun()
    else:
        g.markdown(f'<div class="marche"><span class="etat" style="--c:var(--wait)">Hors ligne</span>'
                   f'<span class="petit">{ui.e(MSG_SOURCE)}</span></div>', unsafe_allow_html=True)
        if d.button("Réessayer", use_container_width=True):
            tout_actualiser(); st.rerun()


@st.cache_data(show_spinner=False, ttl=20)
def indices_cache(symboles: tuple) -> dict:
    try:
        return data.indices_direct(list(symboles))
    except Exception:
        return {}


def _variation_jour(tk: str, c: dict) -> float | None:
    """Variation depuis la clôture de la séance précédente (historique quotidien réel)."""
    hist = DONNEES.prix[tk].dropna()
    avant = hist[hist.index < pd.Timestamp(c["jour"])]
    return c["prix"] / float(avant.iloc[-1]) - 1 if len(avant) else None


@st.fragment(run_every=dt.timedelta(seconds=30))
def cours_en_direct() -> None:
    """Bandeau des cours en direct : interroge Yahoo toutes les 30 s, fait clignoter les variations et
    actualise toute la page (valeur du portefeuille, signaux) dès qu'un cours a bougé."""
    if DEMO:
        H(ui.guide("<b>Mode démonstration</b> : ces cours sont <b>fictifs</b> et ne bougent pas en temps réel. "
                   "Pour voir les vrais cours Yahoo Finance, cliquez sur <b>Données réelles</b> ci-dessus "
                   "(ou Mon profil → Source des données)."))
        return
    try:
        _direct()
    except Exception as exc:          # le bandeau ne doit jamais bloquer l'actualisation suivante
        H(f'<div class="direct"><span class="etat" style="--c:var(--wait)">Cours en direct indisponibles</span>'
          f'<span class="petit">{ui.e(type(exc).__name__)} · nouvel essai dans 30 s.</span></div>')


def _indices_html() -> str:
    syms = data.indices_pour(list(COURS.columns))[:6]
    vivants = indices_cache(tuple(s_ for s_, _ in syms))
    morceaux = []
    for sym, nom in syms:
        idx = vivants.get(sym) or indice_cache(sym)
        if not idx:
            continue
        var = idx.get("variation")
        morceaux.append(('<span class="sep"></span>' if morceaux else '')
                        + f'<span><b>{ui.e(nom)}</b> {ui.chiffre(idx["niveau"], 0, depuis=ss.get("idx_aff", {}).get(sym))}'
                        + (f' <span class="mono {ui.classe(var)}">{ui.pct(var, 2)}</span>' if var is not None else '')
                        + '</span>')
    ss["idx_aff"] = {s_: v_["niveau"] for s_, v_ in vivants.items()}
    return f'<div class="marche">{"".join(morceaux)}</div>' if morceaux else ""


def _direct() -> None:
    H(_indices_html())
    cot, err = cotations_cache(tuple(COURS.columns), tuple(sorted((DONNEES.devises or {}).items())))
    if not cot:
        H(f'<div class="direct"><span class="etat" style="--c:var(--wait)">Cours en direct indisponibles</span>'
          f'<span class="petit">{ui.e(err or "aucune cotation reçue")} · valorisation à la dernière clôture réelle. '
          f'Nouvel essai automatique dans 30 s.</span></div>')
        return
    prec = ss.get("cot_aff", {})
    items, ouverts = [], 0
    for tk in COURS.columns:
        c = cot.get(tk)
        if not c:
            continue
        ouverts += c["ouvert"]
        var = _variation_jour(tk, c)
        etat = ("ouvert" if c["ouvert"] else "fermé")
        retard = (f" · différé d'environ {c['retard']:.0f} min" if c["ouvert"] and c["retard"] >= 5 else "")
        items.append(
            f'<span class="cot" title="{ui.e(NOMS.get(tk, tk))} · marché {etat} · cotation de {c["heure"]:%H:%M} '
            f'(heure de Paris){retard} · {ui.nombre(c["natif"], 2)} {ui.e(c["devise"])}">'
            f'<i class="pt {"on" if c["ouvert"] else ""}"></i><b>{ui.e(NOMS.get(tk, tk))}</b> '
            f'{ui.chiffre(c["prix"], 2, " €", depuis=prec.get(tk))}'
            + (f' <span class="mono {ui.classe(var)}">{ui.pct(var, 2)}</span>' if var is not None else "")
            + f' <span class="h">{c["heure"]:%H:%M}{" · différé" if c["ouvert"] and c["retard"] >= 5 else ""}</span></span>')
    H(f'<div class="direct" title="Yahoo Finance, actualisé toutes les 30 s. Selon la place, les cours peuvent être '
      f'différés de 15 à 20 min ; l\'heure de chaque cotation est indiquée.">'
      f'<span class="etat" style="--c:{"var(--buy)" if ouverts else "var(--muted)"}">'
      f'{"En direct" if ouverts else "Marchés fermés"}</span>{"".join(items)}</div>')
    bouge = any(abs(c["prix"] - ss.get("cot_page", {}).get(t_, c["prix"])) > 1e-9 for t_, c in cot.items())
    if (bouge and ss.get("direct_auto", True) and time.time() - ss.get("maj_page", 0) >= 55
            and time.time() - ss.get("dlg_t", 0) > 180 and not SIMU):
        st.rerun(scope="app")        # la page entière se redessine ; le clignotement se fera à ce rendu
    ss["cot_aff"] = {t_: c_["prix"] for t_, c_ in cot.items()}


def entete_app() -> None:
    g, d = st.columns([5, 1.1], vertical_alignment="center")
    g.markdown(f"""<div class="entete-app">{ui.logo(46, G_SCORE * .9, bool(HORS_LIGNE))}<div>
      <div class="nom">Boussole</div><div class="sous">{ui.e(ss.profil.nom_affiche)} · profil {ui.e(ss.profil.profil_risque.lower())}
      {" · <b style='color:var(--wait)'>simulateur</b>" if SIMU else ""}</div></div></div>{ui.ecran("app")}""",
               unsafe_allow_html=True)
    if d.button("Se déconnecter", use_container_width=True, key="deco_haut"):
        deconnecter()


entete_app()
bandeau_marche()
cours_en_direct()
onglets = st.tabs(["Accueil", "Synthèse et opérations", "Signes, santé et actualités", "Portefeuille",
                   "Mes actions", "Mon profil", "Budget et règles"])

# --------------------------------------------------------------------------- Accueil
with onglets[0]:
    H(f"""<div class="surtitre">Séance du {fmt_date(DATES[T])}</div>
      <div class="titre-xl">Bonjour, {ui.e(ss.profil.prenom or ss.profil.nom_affiche)}</div>
      <div class="petit" style="font-size:15px;margin-top:.3rem">Votre boussole du jour · profil
      <b>{ui.e(ss.profil.profil_risque.lower())}</b></div><div class="trait"></div>""")
    manuelles = any(x["motif"] in ("Manuel", "Rééquilibrage") for x in ss.pf.transactions) if ss.get("pf") else False
    pas_faits = [("Créer votre compte", True), ("Définir votre profil d'investisseur", bool(ss.profil.historique)),
                 ("Composer votre portefeuille", ss.configure),
                 ("Comprendre un signal : bouton « Pourquoi ce signal ? »", bool(ss.guide.get("pourquoi"))),
                 ("Passer votre première opération (Synthèse et opérations)", manuelles)]
    if not ss.guide.get("masque") and not all(ok for _, ok in pas_faits):
        H(ui.carte(f'<div style="display:flex;justify-content:space-between;align-items:baseline"><b>Premiers pas</b>'
                   f'<span class="mono legende">{sum(ok for _, ok in pas_faits)} / {len(pas_faits)}</span></div>'
                   f'{ui.premiers_pas(pas_faits)}', 1,
                   "border-left:3px solid var(--accent);margin-bottom:.4rem", plat=True))
        if st.button("Masquer les premiers pas", key="masquer_guide"):
            ss.guide["masque"] = True; sauver(); st.rerun()
        st.write("")
    if pr.a_revoir(ss.profil.historique, 12):
        H(ui.guide("Votre profil date de plus d'un an : pensez à le mettre à jour dans <b>Mon profil</b>."))
    if aide():
        H(ui.guide("La <b>jauge</b> va de vendre (gauche) à acheter (droite). Pour agir sur une valeur : "
                   "<b>Synthèse et opérations</b>."))
    g, d = st.columns([1, 1.45], gap="medium")
    with g:
        resume = ("Achats suspendus par la règle de risque" if RISQUE.suspendre_achats else
                  f"{sum(1 for s in SIGNAUX.values() if s.code == 1)} achat · "
                  f"{sum(1 for s in SIGNAUX.values() if s.code == 0)} attente · "
                  f"{sum(1 for s in SIGNAUX.values() if s.code == -1)} vente")
        H(ui.carte('<div class="label" style="text-align:center;margin-bottom:.4rem">Signal global · mes actions</div>'
                   + ui.jauge(G_CODE, G_SCORE, G_CONF, resume, HORS_LIGNE, 300), 1, plat=True))
    with d:
        k1, k2 = st.columns(2)
        k1.markdown(ui.kpi("Valeur du portefeuille", ui.chiffre(VALEUR, 0, " €", depuis=PREC.get("valeur")),
                           f'<span class="mono {ui.classe(GAIN)}">{ui.pct(GAIN / PF.apports(T))}</span> depuis le début', 1),
                    unsafe_allow_html=True)
        k2.markdown(ui.kpi("Plus ou moins-value", f'<span class="{ui.classe(GAIN)}">'
                           f'{ui.chiffre(GAIN, 0, chr(0x202f) + "€", True, PREC.get("gain"))}</span>',
                           f"Sur un capital de {ui.euros(PF.apports(T))}", 2), unsafe_allow_html=True)
        ph = RISQUE.perf_hebdo
        k1.markdown(ui.kpi("Rendement de la semaine", f'<span class="{ui.classe(ph)}">{ui.pct(ph)}</span>',
                           ui.barre((ph + REGLES.tolerance_hebdo) / (REGLES.objectif_hebdo + REGLES.tolerance_hebdo),
                                    "buy" if ph >= 0 else "sell")
                           + f'<div style="display:flex;justify-content:space-between;margin-top:.3rem" '
                             f'class="legende mono"><span>{ui.pct(-REGLES.tolerance_hebdo, 0)}</span>'
                             f'<span>objectif {ui.pct(REGLES.objectif_hebdo, 0)}</span></div>', 3),
                    unsafe_allow_html=True)
        k2.markdown(ui.kpi("Liquidités", ui.chiffre(LIQ, 0, " €", depuis=PREC.get("liq")),
                           f'<span class="mono">{ui.pct(LIQ / VALEUR, 1, False)}</span> du portefeuille', 4),
                    unsafe_allow_html=True)
        H(ui.risque(RISQUE.niveau, RISQUE.message))

    ui.section("Ma liste de suivi")
    lignes = []
    for i, tk in enumerate(COURS.columns):
        serie = COURS[tk].iloc[max(0, T - 40): T + 1]
        var = serie.iloc[-1] / serie.iloc[-2] - 1 if len(serie) > 1 else 0
        s = SIGNAUX[tk]
        lignes.append(f"""<div class="ligne" style="animation-delay:{i * .04:.2f}s">
          <div><div class="mono legende">{ui.e(tk)}</div><div style="font-weight:600">{ui.e(NOMS[tk])}</div></div>
          <div>{ui.sparkline(serie.values, "accent")}</div>
          <div style="text-align:right"><div style="font-size:16px">
          {ui.chiffre(float(serie.iloc[-1]), 2, depuis=PREC.get(f"c_{tk}"))}</div>
          <div class="mono {ui.classe(var)}" style="font-size:13px">{ui.pct(var, 2)}</div></div>
          <div style="text-align:right">{ui.pastille(s.code)}<div class="legende mono" style="margin-top:.2rem">
          score {ui.nombre(s.score, 0, True)}</div></div></div>""")
    H("".join(lignes))

    ui.section("Dernières actualités de mes valeurs")
    fil = sorted(((tk, n) for tk in COURS.columns for n in ACTUS[tk]), key=lambda x: x[1]["date"], reverse=True)[:6]
    if fil:
        blocs = []
        for i, (tk, n) in enumerate(fil):
            signe = {1: '<span class="pos mono">+</span>', -1: '<span class="neg mono">−</span>'}.get(
                n.get("tonalite", 0), '<span class="mono neutre">·</span>')
            titre = (f'<a href="{ui.e(n["lien"])}" target="_blank" rel="noopener">{ui.e(n["titre"])}</a>'
                     if n.get("lien") else f'<span class="t">{ui.e(n["titre"])}</span>')
            quand = nw.il_y_a(n["date"]) if not DEMO else pd.Timestamp(n["date"]).strftime("%d/%m/%Y")
            blocs.append(f'<div class="news" style="animation-delay:{i * .04:.2f}s;padding:10px 8px">{signe} {titre}'
                         f'<div class="meta legende"><span class="mono">{ui.e(tk)}</span><span>·</span>'
                         f'<span class="src">{ui.e(n["source"])}</span><span>·</span><span>{ui.e(quand)}</span></div></div>')
        H(ui.carte("".join(blocs), 1, "padding:6px 14px", plat=True))
    else:
        H(ui.carte('<div class="petit">Aucune actualité récente d\'une source reconnue.</div>', 1, plat=True))

    ui.section("Évolution du portefeuille")
    if T - T0 < 2:
        H(ui.carte(('<b>Le simulateur commence au début de l\'année passée.</b><div class="petit">Avancez avec « +1 J » dans la barre latérale.</div>') if SIMU else
                   (f'<b>Votre portefeuille a été ouvert le {fmt_date(DATES[T0])}.</b><div class="petit">La courbe '
                    f'se dessinera au fil des séances.</div>'),
                   1, plat=True))
    else:
        hist = PF.historique(COURS, T0, T)
        ref = valeur_reference()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ref.index, y=ref, name="Achat-conservation",
                                 line=dict(color=TK["muted"], width=1.3, dash="dash", **SPL)))
        fig.add_trace(go.Scatter(x=hist.index, y=hist, name="Votre portefeuille",
                                 line=dict(color=TK["accent"], width=1.8, **SPL),
                                 fill="tozeroy", fillcolor=theme.rgba(TK["accent"], .13)))
        fig.update_yaxes(range=[min(hist.min(), ref.min()) * .98, max(hist.max(), ref.max()) * 1.01], ticksuffix=" €")
        st.plotly_chart(ui.style_fig(fig, 320), use_container_width=True)
    H(ui.avertissement())

# --------------------------------------------------------------------------- Synthèse et opérations
with onglets[1]:
    if aide():
        H(ui.guide("Choisissez une action, lisez son signal (<b>Pourquoi ce signal ?</b> détaille le calcul), "
                   "puis passez l'opération plus bas."))
    tk = st.segmented_control("Valeur", list(COURS.columns), format_func=lambda x: NOMS[x], key="sel_synthese",
                              default=COURS.columns[0], label_visibility="collapsed") or COURS.columns[0]
    rec, s = RECS[tk], SIGNAUX[tk]
    prix = float(COURS[tk].iloc[T])
    var = prix / float(COURS[tk].iloc[T - 1]) - 1
    pos = POS.get(tk, {})
    qte = pos.get("quantite", 0)
    if qte:
        perf_pos = prix / pos["pru"] - 1
        info_pos = (f'<span class="petit">Position : <span class="mono">{qte}</span> titres · prix de revient '
                    f'<span class="mono">{ui.euros(pos["pru"], 2)}</span> · <span class="mono {ui.classe(perf_pos)}">'
                    f'{ui.pct(perf_pos)}</span></span>')
    else:
        info_pos = '<span class="petit">Aucune position détenue</span>'
    H(f"""<div class="surtitre">{" · ".join(ui.e(x) for x in (tk, place_titre(tk), secteur_titre(tk)) if x and x != "—")}</div>
      <div class="titre" style="font-size:32px;line-height:38px">{ui.e(NOMS[tk])}</div>
      <div style="display:flex;align-items:center;gap:1rem;margin:.5rem 0 1.1rem;flex-wrap:wrap">
      <span style="font-size:26px">{ui.chiffre(prix, 2, " EUR", depuis=PREC.get(f"c_{tk}"))}</span>{conv_note(tk)}
      <span class="mono {ui.classe(var)}" style="font-size:15px">{ui.pct(var, 2)}</span>{ui.pastille(s.code, True)}
      {info_pos}{adequation_html(tk)}</div>""")
    g, d = st.columns([1, 2.1], gap="medium")
    with g:
        H(ui.carte(ui.jauge(s.code, s.score, s.confiance, s.stop_loss, HORS_LIGNE, 240)
                   + '<div class="label" style="margin-top:1rem">Les raisons principales</div>'
                   + "".join(ui.raison(r, t) for r, t in s.raisons if r != "EXG-F-25"), 1, plat=True))
        st.write("")
        if st.button("Pourquoi ce signal ?", type="primary", use_container_width=True, key="pourquoi"):
            dialogue_pourquoi(tk)
    with d:
        per = st.segmented_control("Période", list(PERIODES), default="3M", key="periode_synth_v2",
                                   label_visibility="collapsed") or "3M"
        graphique_cours(tk, per, 470, "fig_synth")
        H(ui.carte('<div class="label">Les 6 piliers de la décision</div>'
                   + "".join(ui.pilier(k, v) for k, v in s.piliers.items()), 2, plat=True))
    H(ui.avertissement())

    ui.section("Passer une opération" if not SIMU else "Opération d'essai (simulateur)")
    o1, o2, o3, o4 = st.columns([1, 1.1, 1.1, 1.5])
    sens = o1.segmented_control("Sens", ["Achat", "Vente"], default="Vente" if rec.code == rules.VENDRE else "Achat",
                                key=f"sens_{tk}") or "Achat"
    mode_s = o2.segmented_control("Saisie", ["Montant", "Quantité"], default="Montant", key="mode_saisie") or "Montant"
    if mode_s == "Montant":
        montant = o3.number_input("Montant (€)", min_value=0.0, max_value=float(max(LIQ, VALEUR)),
                                  value=float(min(10_000.0, LIQ)) if sens == "Achat" else float(qte * prix),
                                  step=1_000.0, key=f"montant_{tk}_{sens}")
        quantite = int(montant // prix)
    else:
        quantite = int(o3.number_input("Quantité", min_value=0, value=int(qte) if sens == "Vente" else 10, step=1,
                                       key=f"qte_{tk}_{sens}"))
    total = quantite * prix
    apres = LIQ - total if sens == "Achat" else LIQ + total
    ok = (total <= LIQ if sens == "Achat" else quantite <= qte) and quantite > 0
    o4.markdown(ui.carte(f'<div class="label">Aperçu</div><div class="mono">{quantite} titres = {ui.euros(total, 2)}</div>'
                         f'<div class="petit">Liquidités après : <span class="mono">{ui.euros(apres)}</span></div>'
                         + ("" if ok else '<div class="petit neg">Opération impossible : liquidités ou titres '
                            'insuffisants.</div>'), 0, "padding:10px 16px", plat=True), unsafe_allow_html=True)
    b1, b2, _ = st.columns([1, 1.4, 2])
    if b1.button("Valider l'opération", type="primary", disabled=not ok, use_container_width=True):
        dialogue_operation(dict(sens=sens, ticker=tk, quantite=quantite, prix=prix,
                                motif="Manuel" if rec.code == 0 else f"Manuel ({rec.raisons[0][0]})"))
    if b2.button("Appliquer les recommandations du jour", use_container_width=True):
        dialogue_appliquer()

    ui.section("Historique des transactions")
    MOTIFS_LISIBLES = {"Manuel": "Votre décision", "Investissement initial": "Investissement initial",
                       "Allocation initiale": "Répartition de départ", "Rééquilibrage": "Nouvelle répartition"}
    if PF.transactions:
        filtre = st.segmented_control("Filtrer", ["Toutes", "Achats", "Ventes", "Liquidités"], default="Toutes",
                                      key="filtre_tx", label_visibility="collapsed") or "Toutes"
        tx = pd.DataFrame(PF.transactions[::-1])
        garder = {"Achats": ["Achat"], "Ventes": ["Vente"], "Liquidités": ["Apport", "Retrait"]}.get(filtre)
        if garder:
            tx = tx[tx["sens"].isin(garder)]
        if "enregistre" not in tx:
            tx["enregistre"] = None
        tx["Action"] = tx["ticker"].map(lambda x: "Liquidités" if x == "—" else (NOMS.get(x) or nom_titre(x)))
        tx["Date"] = pd.to_datetime(tx["date"]).dt.strftime("%d/%m/%Y")
        def _motif(m) -> str:
            m = str(m)
            if m.startswith("Manuel (") and m.endswith(")"):
                code = m[len("Manuel ("):-1]
                return "Votre décision · " + ui.RAISONS.get(code, (code,))[0].lower()
            return MOTIFS_LISIBLES.get(m) or ui.RAISONS.get(m, (m,))[0]
        tx["Motif"] = tx["motif"].map(_motif)
        titres = tx["sens"].isin(["Achat", "Vente"])
        tx["Quantité"] = [f"{q:,}".replace(",", "\u202f") if t_ else "" for q, t_ in zip(tx["quantite"], titres)]
        tx["Prix (€)"] = [f"{p_:,.2f}".replace(",", "\u202f").replace(".", ",") if t_ else ""
                          for p_, t_ in zip(tx["prix"], titres)]
        tx["Enregistrée le"] = pd.to_datetime(tx["enregistre"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
        vue = tx[["Date", "Action", "sens", "Quantité", "Prix (€)", "montant", "Motif"]
                 + ([] if SIMU else ["Enregistrée le"])].rename(columns={"sens": "Sens", "montant": "Montant (€)"})
        st.dataframe(vue, hide_index=True, use_container_width=True, height=min(380, 36 * (len(vue) + 1) + 2),
                     column_config={"Montant (€)": st.column_config.NumberColumn(format="%.2f")})
        st.caption(f"{len(PF.transactions)} opération(s)" + (" dans le simulateur" if SIMU else ""))
        st.download_button("Exporter l'historique (CSV)", vue.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "historique_boussole.csv", "text/csv")
    else:
        H(ui.carte('<div class="petit">Aucune opération pour l\'instant.</div>', plat=True))

# --------------------------------------------------------------------------- Signes, santé et actualités
with onglets[2]:
    ui.entete("Analyse", "Signes, santé et actualités",
              "Indicateurs techniques, santé financière de l'entreprise et actualités récentes.")
    if aide():
        H(ui.guide("Bande grisée : zone habituelle du cours. RSI au-dessus de 70 : forte hausse récente ; "
                   "sous 30 : forte baisse."))
    tk = st.segmented_control("Valeur ", list(COURS.columns), format_func=lambda x: NOMS[x], key="sel_sante",
                              default=COURS.columns[0], label_visibility="collapsed") or COURS.columns[0]
    ind = INDS[tk].iloc[: T + 1]
    der = ind.iloc[-1]
    f = FONDS[tk]
    etat = rules.ti.etat_technique(ind, REGLES.rsi_survente, REGLES.rsi_surachat)
    c = st.columns(4)
    rsi_v = float(der["rsi"])
    if rsi_v > REGLES.rsi_surachat:
        zone, role = "Le titre a beaucoup monté, il risque de souffler.", "wait"
    elif rsi_v < REGLES.rsi_survente:
        zone, role = "Le titre a beaucoup baissé, un rebond est possible.", "wait"
    else:
        zone, role = "Ni excès d'achat, ni excès de vente.", "accent"
    c[0].markdown(ui.carte(f'<div class="label">Élan du cours (RSI 14)</div><div class="valeur">{ui.nombre(rsi_v, 0)}'
                           f'</div><div style="margin:.4rem 0">{ui.barre(rsi_v / 100, role)}</div>'
                           f'<div class="petit">{zone}</div>', 1), unsafe_allow_html=True)
    ecart = der["mm_courte"] / der["mm_longue"] - 1
    txt_tend = ("La tendance courte est au-dessus de la longue." if ecart > 0
                else "La tendance courte est sous la longue.")
    c[1].markdown(ui.carte(f'<div class="label">Tendance (MM{REGLES.mm_courte} / MM{REGLES.mm_longue})</div>'
                           f'<div class="valeur {ui.classe(ecart)}">{"▲" if ecart > 0 else "▼"} {ui.pct(ecart)}</div>'
                           f'<div class="petit">{txt_tend}</div>', 2), unsafe_allow_html=True)
    c[2].markdown(ui.carte(f'<div class="label">Santé financière</div><div class="valeur">{len(f["criteres"])}/5</div>'
                           f'<div style="margin:.4rem 0">{ui.barre(f["score"])}</div>'
                           f'<div class="petit">critères favorables</div>', 3), unsafe_allow_html=True)
    etat_txt = {"favorable": "Tendance bien orientée", "defavorable": "Tendance fragile", "neutre": "Tendance hésitante"}
    c[3].markdown(ui.carte(f'<div class="label">Synthèse</div><div style="margin:.5rem 0">'
                           f'{ui.pastille(RECS[tk].code, True)}</div><div class="petit">{etat_txt[etat]} · score '
                           f'<span class="mono">{ui.nombre(SIGNAUX[tk].score, 0, True)}</span></div>', 4),
                  unsafe_allow_html=True)

    ui.section("Analyse technique")
    per = st.segmented_control("Période ", list(PERIODES), default="1A", key="periode_sante_v2",
                               label_visibility="collapsed") or "1A"
    graphique_cours(tk, per, 560, "fig_tech")

    ui.section("Santé financière : 5 indicateurs fondamentaux")
    fc = st.columns(5)
    dev = "€" if f.get("devise", "EUR") == "EUR" else f.get("devise", "")

    def fmt(cle, rendu):
        return rendu(f[cle]) if f.get(cle) is not None else "n.d."
    vals = [("Chiffre d'affaires", fmt("ca", lambda v: f"{ui.nombre(v / 1e9, 1)}\u202fMd{dev}"), "ca",
             lambda v: v >= 1e9, "≥ 1 Md"),
            ("Dividende par action", fmt("dpa", lambda v: f"{ui.nombre(v, 2)}\u202f{dev}"), "dpa", lambda v: v > 0, "> 0"),
            ("Rendement du dividende", fmt("rendement", lambda v: ui.pct(v, 2, False)), "rendement",
             lambda v: v >= .02, "≥ 2 %"),
            ("PER", fmt("per", lambda v: ui.nombre(v, 1)), "per", lambda v: 0 < v <= 25, "≤ 25"),
            ("Marge nette", fmt("marge", lambda v: ui.pct(v, 1, False)), "marge", lambda v: v >= .10, "≥ 10 %")]
    for i, (lab, v, cle, test, crit) in enumerate(vals):
        if f.get(cle) is None:
            etat_f = '<div class="petit neutre">donnée non publiée</div>'
        elif test(f[cle]):
            etat_f = '<div class="petit pos">+ favorable</div>'
        else:
            etat_f = '<div class="petit neg">− à surveiller</div>'
        fc[i].markdown(ui.carte(f'<div class="label">{lab}</div><div class="valeur" style="font-size:20px">{v}</div>'
                                f'{etat_f}<div class="legende">repère : {crit}</div>', i + 1), unsafe_allow_html=True)
    st.caption(f"Source des fondamentaux : {f['source']}.")

    ui.section("Actualités financières")
    news, erreurs_news, heure_news = ACTUS_BRUT[tk]
    tons = [n.get("tonalite", 0) for n in news]
    senti = sc.piliers(INDS[tk].iloc[: T + 1], FONDS[tk], news)["Actualités"]
    g, d = st.columns([1, 2], gap="medium")
    with g:
        H(ui.carte(f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
                   f'<b>Actualités</b><span class="mono {ui.classe(senti)}" style="font-size:18px">'
                   f'{ui.nombre(senti, 0, True)}</span></div><div class="petit">Ton '
                   f'{"plutôt positif" if senti > 10 else "plutôt négatif" if senti < -10 else "neutre"} sur {len(news)} '
                   f'articles ({tons.count(1)} positifs, {tons.count(-1)} négatifs)</div>'
                   f'<div style="margin-top:.7rem">{ui.barre_centree(senti)}</div>'
                   f'<div class="legende" style="margin-top:.7rem">{"Mis à jour à " + heure_news if heure_news else ""}</div>', 1))
        if not DEMO and st.button("Actualiser les actualités", use_container_width=True, key="maj_news"):
            actus_reelles.clear(); st.rerun()
    items = []
    for i, n in enumerate(news):
        t_ = n.get("tonalite", 0)
        signe = {1: '<span class="pos mono">+</span>', -1: '<span class="neg mono">−</span>'}.get(
            t_, '<span class="mono neutre">·</span>')
        titre = (f'<a href="{ui.e(n["lien"])}" target="_blank" rel="noopener">{ui.e(n["titre"])}</a>' if n.get("lien")
                 else f'<span class="t">{ui.e(n["titre"])}</span>')
        quand = nw.il_y_a(n["date"]) if not DEMO else pd.Timestamp(n["date"]).strftime("%d/%m/%Y")
        heure = n["date"].astimezone(PARIS).strftime("%d/%m %H:%M") if not DEMO else ""
        items.append(f'<div class="news" style="animation-delay:{i * .04:.2f}s;padding:10px 8px">{signe} {titre}'
                     f'<div class="meta legende"><span class="src">{ui.e(n["source"])}</span><span>·</span>'
                     f'<span title="{heure}">{ui.e(quand)}</span></div></div>')
    if not items:
        items = ['<div class="petit" style="padding:14px 4px">Aucun article récent d\'une source reconnue pour cette '
                 'valeur.' + (f' ({ui.e(", ".join(erreurs_news))})' if erreurs_news else "") + '</div>']
    d.markdown(ui.carte("".join(items), 2, "padding:6px 14px", plat=True), unsafe_allow_html=True)
    if DEMO:
        st.caption("Titres fictifs (démonstration).")
    else:
        st.caption("Médias reconnus uniquement (Les Echos, Reuters, Bloomberg, AFP…).")
    H(ui.avertissement())

# --------------------------------------------------------------------------- Portefeuille
with onglets[3]:
    ui.entete("Suivi", "Portefeuille", "Vos investissements et leurs performances.")
    if aide():
        H(ui.guide("Gain latent : si vous vendiez maintenant. Gain réalisé : déjà encaissé."))
    tab = PF.tableau(T, COURS, NOMS)
    latente = float(tab["pv_latente"].sum()) if len(tab) else 0.0
    realisee = float(tab["pv_realisee"].sum()) if len(tab) else 0.0
    investi = float(tab["valeur"].sum()) if len(tab) else 0.0
    k = st.columns(5)
    k[0].metric("Valeur totale", ui.euros(VALEUR), ui.pct(GAIN / PF.apports(T)).replace("−", "-"))
    k[1].metric("Investi en actions", ui.euros(investi))
    k[2].metric("Plus-value latente", ui.euros(latente, 0, True))
    k[3].metric("Plus-value réalisée", ui.euros(realisee, 0, True))
    k[4].metric("Liquidités", ui.euros(LIQ))

    hist = PF.historique(COURS, T0, T)
    g, d = st.columns([2, 1])
    with g:
      if T - T0 < 2:
        H(ui.carte(f'<b>Performance cumulée</b><div class="petit" style="margin-top:.4rem">Portefeuille ouvert le '
                   f'{fmt_date(DATES[T0])} : la courbe apparaîtra après quelques séances.</div>', 1, plat=True))
      else:
        ref = valeur_reference()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ref.index, y=ref / PF.apports(T) * 100 - 100, name="Achat-conservation",
                                 line=dict(color=TK["muted"], width=1.3, dash="dash", **SPL)))
        fig.add_trace(go.Scatter(x=hist.index, y=hist / PF.apports(T) * 100 - 100, name="Portefeuille",
                                 line=dict(color=TK["accent"], width=1.8, **SPL),
                                 fill="tozeroy", fillcolor=theme.rgba(TK["accent"], .13)))
        fig.update_layout(title="Performance cumulée")
        fig.update_yaxes(ticksuffix=" %")
        st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)
    with d:
        detenus = tab[tab["valeur"] > 0] if len(tab) else tab
        labels = ([NOMS.get(t, nom_titre(t)) for t in detenus["ticker"]] if len(detenus) else []) + ["Liquidités"]
        valeurs = (list(detenus["valeur"]) if len(detenus) else []) + [LIQ]
        n_l = max(len(labels) - 1, 1)
        couleurs = [theme.rgba(TK["accent"], 1 - .72 * i / max(n_l - 1, 1)) for i in range(n_l)][:len(labels) - 1] + [TK["muted"]]
        fig = go.Figure(go.Pie(labels=labels, values=valeurs, hole=.66, sort=False,
                               marker=dict(colors=couleurs, line=dict(color=TK["surface"], width=2)),
                               textinfo="none", hovertemplate="%{label}<br>%{value:,.0f} € · %{percent}<extra></extra>"))
        fig.update_layout(title="Répartition", annotations=[dict(text=f"{ui.nombre(VALEUR / 1000, 0)} k€",
                                                                 showarrow=False, font=dict(family="IBM Plex Mono",
                                                                                            size=17, color=TK["text"]))])
        st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)

    ui.section("Gains et pertes par action")
    lignes = ""
    for _, r in tab.iterrows():
        rc = RECS[r["ticker"]].code if r["ticker"] in RECS else None
        lignes += (f'<tr><td><b>{ui.e(r["nom"])}</b> <span class="legende mono">{ui.e(r["ticker"])}</span></td>'
                   f'<td>{r["quantite"]}</td><td>{ui.euros(r["pru"], 2)}</td><td>{ui.euros(r["cours"], 2)}</td>'
                   f'<td>{ui.euros(r["valeur"])}</td><td class="{ui.classe(r["pv_latente"])}">'
                   f'{ui.euros(r["pv_latente"], 0, True)}</td><td class="{ui.classe(r["pv_realisee"])}">'
                   f'{ui.euros(r["pv_realisee"], 0, True)}</td><td class="{ui.classe(r["perf"])}">{ui.pct(r["perf"])}</td>'
                   f'<td>{ui.pastille(rc) if rc is not None else ""}</td></tr>')
    lignes += (f'<tr><td><b>Total</b></td><td></td><td></td><td></td><td><b>{ui.euros(investi)}</b></td>'
               f'<td class="{ui.classe(latente)}"><b>{ui.euros(latente, 0, True)}</b></td>'
               f'<td class="{ui.classe(realisee)}"><b>{ui.euros(realisee, 0, True)}</b></td>'
               f'<td class="{ui.classe(GAIN)}"><b>{ui.pct(GAIN / PF.apports(T))}</b></td><td></td></tr>')
    H(ui.carte(f'<table class="tbl"><thead><tr><th>Action</th><th>Qté</th><th>Prix de revient</th><th>Cours</th>'
               f'<th>Valeur</th><th>+/− latente</th><th>+/− réalisée</th><th>Perf.</th><th>Signal</th></tr></thead>'
               f'<tbody>{lignes}</tbody></table>', 1, plat=True))

    ui.section("Rendements hebdomadaires")
    hebdo = hist.resample("W-FRI").last().pct_change().dropna()
    if len(hebdo):
        fig = go.Figure(go.Bar(x=hebdo.index, y=hebdo * 100,
                               marker=dict(color=[TK["buy"] if v >= 0 else TK["sell"] for v in hebdo], cornerradius=3),
                               hovertemplate="%{x|%d/%m/%Y} : %{y:+.2f} %<extra></extra>"))
        for y, txt, role in ((REGLES.objectif_hebdo * 100, "Objectif", "buy"),
                             (-REGLES.alerte_perte_hebdo * 100, "Alerte", "wait"),
                             (-REGLES.tolerance_hebdo * 100, "Perte maximale", "sell")):
            fig.add_hline(y=y, line=dict(color=TK[role], dash="dash", width=1), annotation_text=txt,
                          annotation_position="top left", annotation_font=dict(color=TK[role], size=11))
        fig.update_yaxes(ticksuffix=" %")
        fig.update_layout(bargap=.35)
        st.plotly_chart(ui.style_fig(fig, 300, False), use_container_width=True)
    else:
        st.info("Avancez d'au moins une semaine pour voir les rendements hebdomadaires.")

# --------------------------------------------------------------------------- Mes 5 actions
with onglets[4]:
    ui.entete("Sélection", "Mes actions",
              f"Suivez jusqu'à {MAX_ACTIONS} actions ou ETF, de n'importe quelle bourse du monde, et répartissez votre argent.")
    if aide():
        H(ui.guide("Le point de couleur indique si la valeur convient à votre profil."))

    def ajouter_titre(sym, _r):
        if sym not in ss.tickers and len(ss.tickers) < MAX_ACTIONS:
            ss.tickers = ss.tickers + [sym]
            ss.allocation.setdefault(sym, 0.0)
            ss["rech_actions"] = ""
            sauver()
            st.toast(f"{nom_titre(sym)} ajoutée : elle apparaît maintenant dans tous les onglets.")

    def retirer_titre(sym):
        ss.tickers = [t_ for t_ in ss.tickers if t_ != sym]
        ss.allocation.pop(sym, None)
        sauver()
        st.toast(f"{nom_titre(sym)} retirée de vos actions.")

    g, d = st.columns([1.35, 1], gap="large")
    with g:
        ui.section(f"Mes actions suivies ({len(ss.tickers)} / {MAX_ACTIONS})")
        for i, t_ in enumerate(COURS.columns):
            qte = POS.get(t_, {}).get("quantite", 0)
            c_t, c_v, c_b = st.columns([3, 1.6, 1.1], vertical_alignment="center")
            pl = place(t_)[0]
            c_t.markdown(f'<div class="ligne-recherche"><b>{ui.e(NOMS[t_])}</b><div class="legende"><span class="mono">'
                         f'{ui.e(t_)}</span> · {ui.e(place_titre(t_) or pl)}'
                         f'{" · " + ui.e(DEVISES.get(t_)) + " → EUR" if DEVISES.get(t_, "EUR") != "EUR" else ""}</div>'
                         f'{adequation_html(t_, True)}</div>', unsafe_allow_html=True)
            c_v.markdown(f'<div class="ligne-recherche" style="text-align:right"><span class="mono">'
                         f'{ui.euros(qte * float(COURS[t_].iloc[T]))}</span><div class="legende">{qte} titre(s)</div></div>',
                         unsafe_allow_html=True)
            bloque = qte > 0 and not SIMU
            c_b.button("Retirer", key=f"ret_{t_}", use_container_width=True, disabled=bloque or len(ss.tickers) <= 1,
                       on_click=retirer_titre, args=(t_,),
                       help="Vendez d'abord vos titres (onglet Synthèse et opérations ou répartition ci-dessous)."
                       if bloque else "Ne plus suivre cette valeur")
    with d:
        ui.section("Ajouter une valeur")
        bloc_recherche(ss.tickers, ajouter_titre, "actions", DEMO)

    if not SIMU:
        ui.section("Répartir mon argent")
        H(f'<div class="petit" style="margin:-.3rem 0 .8rem">Valeur totale du portefeuille : <span class="mono">'
          f'{ui.euros(VALEUR)}</span>, dont <span class="mono">{ui.euros(LIQ)}</span> de liquidités · au plus '
          f'<span class="mono">{ui.pct(REGLES.poids_max_ligne, 0, False)}</span> par valeur.</div>')
        pas = 1_000 if VALEUR >= 100_000 else 100 if VALEUR >= 10_000 else 10
        cibles = {}
        cols_n = min(len(COURS.columns), 5)
        for debut_l in range(0, len(COURS.columns), cols_n):
            cols = st.columns(cols_n)
            for j, t_ in enumerate(list(COURS.columns)[debut_l: debut_l + cols_n]):
                actuel = POS.get(t_, {}).get("quantite", 0) * float(COURS[t_].iloc[T])
                with cols[j]:
                    H(f'<div class="legende mono">{ui.e(t_)}</div><div style="font-weight:600;white-space:nowrap;'
                      f'overflow:hidden;text-overflow:ellipsis">{ui.e(NOMS[t_])}</div>')
                    cibles[t_] = float(st.number_input("Montant visé (€)", 0.0, float(VALEUR), float(round(actuel, -1)),
                                                       step=float(pas), format="%.0f", key=f"cible_{t_}",
                                                       label_visibility="collapsed"))
                    ecart = cibles[t_] - actuel
                    trop = cibles[t_] > VALEUR * REGLES.poids_max_ligne + 1
                    H(f'<div class="legende">actuel {ui.euros(actuel)}'
                      + (f' · <span class="{ui.classe(ecart)}">{"+" if ecart > 0 else "−"}{ui.euros(abs(ecart))}</span>'
                         if abs(ecart) >= 1 else "")
                      + ('<br><span style="color:var(--wait)">au-delà de la limite du profil</span>' if trop else "")
                      + "</div>")
        total = sum(cibles.values())
        depasse = total > VALEUR + 1
        H(ui.carte(f'<div style="display:flex;justify-content:space-between;margin-bottom:.5rem"><span class="label">'
                   f'Total visé</span><span class="mono {"neg" if depasse else ""}">{ui.euros(total)} / {ui.euros(VALEUR)}'
                   f'</span></div>' + ui.barre(min(total / max(VALEUR, 1), 1), "sell" if depasse else "accent")
                   + f'<div class="petit" style="margin-top:.4rem">Liquidités restantes après les ordres : environ '
                     f'<span class="mono">{ui.euros(max(VALEUR - total, 0))}</span></div>', plat=True))
        st.write("")
        c1, c2, _ = st.columns([1.2, 1.2, 2])
        if c1.button("Voir les ordres à passer", type="primary", use_container_width=True, disabled=depasse):
            dialogue_reequilibrage(cibles)
        if c2.button("Répartir à parts égales", use_container_width=True):
            part = min(VALEUR / len(COURS.columns), VALEUR * REGLES.poids_max_ligne)
            for t_ in COURS.columns:
                ss[f"cible_{t_}"] = float(int(part // pas * pas))
            st.rerun()

        ui.section("Ajouter ou retirer des liquidités")
        with st.form("form_mouvement"):
            m1, m2, m3 = st.columns([1, 1.3, 1], vertical_alignment="bottom")
            sens_m = m1.segmented_control("Opération", ["Apport", "Retrait"], default="Apport")
            montant_m = m2.number_input("Montant (€)", min_value=0.0, value=10_000.0, step=1_000.0, format="%.0f")
            ok_m = m3.form_submit_button("Enregistrer", type="primary", use_container_width=True)
        if ok_m:
            try:
                PF.mouvement(T, DATES[T], sens_m or "Apport", montant_m)
                sauver()
                st.toast(f"{sens_m} de {ui.euros(montant_m)} enregistré dans l'historique.")
                st.rerun()
            except OperationRefusee as exc:
                st.error(str(exc))
    else:
        ui.section("Capital et répartition du simulateur")
        H(ui.guide("Modifier ces montants redémarre la simulation, sans effet sur votre portefeuille réel."))
        choix = list(COURS.columns)
        pas = 1_000 if CAPITAL >= 100_000 else 100 if CAPITAL >= 10_000 else 10
        c_cap, c_eq, _ = st.columns([1.2, 1, 1.4], vertical_alignment="bottom")
        capital = float(c_cap.number_input("Capital d'essai (€)", min_value=1_000.0, max_value=100_000_000.0,
                                           value=float(CAPITAL), step=float(pas), format="%.0f", key="capital_saisie"))
        pas = 1_000 if capital >= 100_000 else 100 if capital >= 10_000 else 10
        egal = capital / max(len(choix), 1)
        if c_eq.button("Répartir équitablement", use_container_width=True):
            for t_ in choix:
                ss[f"alloc_{t_}"] = int(egal // pas * pas)
            st.rerun()
        alloc = {}
        for debut_l in range(0, len(choix), 5):
            cols = st.columns(5)
            for j, t_ in enumerate(choix[debut_l: debut_l + 5]):
                cle = f"alloc_{t_}"
                defaut = int(min(ss.allocation.get(t_, egal), capital) // pas * pas)
                if cle in ss and ss[cle] > capital:
                    ss[cle] = int(capital // pas * pas)
                with cols[j]:
                    H(f'<div class="legende mono">{ui.e(t_)}</div><div style="font-weight:600">{ui.e(NOMS[t_])}</div>')
                    alloc[t_] = float(st.slider("Montant", 0, int(capital), defaut, step=pas, key=cle,
                                                label_visibility="collapsed"))
                    H(f'<div class="mono" style="text-align:center">{ui.euros(alloc[t_])}</div>')
        total = sum(alloc.values())
        depasse = total > capital
        H(ui.carte(f'<div style="display:flex;justify-content:space-between;margin-bottom:.5rem"><span class="label">'
                   f'Total alloué</span><span class="mono {"neg" if depasse else ""}">{ui.euros(total)} / '
                   f'{ui.euros(capital)}</span></div>' + ui.barre(min(total / capital, 1), "sell" if depasse else "accent"),
                   plat=True))
        st.write("")
        change = capital != CAPITAL or any(abs(alloc.get(t_, 0) - ss.allocation.get(t_, 0)) > .5 for t_ in choix)
        if st.button("Redémarrer le simulateur avec cette répartition", type="primary", disabled=depasse or not change):
            dialogue_selection(choix, alloc, capital)

    ui.section("Comparer mes actions")
    per_c = st.segmented_control("Période  ", list(PERIODES), default="1A", key="periode_comp",
                                 label_visibility="collapsed") or "1A"
    fig = go.Figure()
    intra_ok = True
    for i, t_ in enumerate(COURS.columns):
        s_ = serie_intraday(t_, PERIODES[per_c]) if per_c in INTRA else None
        if s_ is None:
            intra_ok = intra_ok and per_c not in INTRA
            s_ = COURS[t_].iloc[max(0, T - (10 if per_c in INTRA else PERIODES[per_c])): T + 1]
        coul, tiret = SERIES[i % len(SERIES)]
        fig.add_trace(go.Scatter(x=s_.index, y=s_ / s_.iloc[0] * 100, name=NOMS[t_],
                                 line=dict(color=coul, width=1.6, dash=tiret, **SPL)))
    fig.add_hline(y=100, line=dict(color=TK["border"], width=1))
    fig.update_layout(title="Performance comparée (base 100)")
    fig = ui.style_fig(fig, 380)
    if per_c in INTRA and intra_ok:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], tickformat="%d/%m %H:%M",
                         hoverformat="%d/%m %H:%M")
    st.plotly_chart(fig, use_container_width=True)
    note_intraday(per_c, intra_ok)
    lignes = ""
    for t_ in COURS.columns:
        s_ = COURS[t_].iloc[: T + 1]
        p1a = s_.iloc[-1] / s_.iloc[max(0, len(s_) - 252)] - 1
        ind = INDS[t_].iloc[T]
        lignes += (f'<tr><td><b>{ui.e(NOMS[t_])}</b></td><td>{ui.euros(s_.iloc[-1], 2)}</td>'
                   f'<td class="{ui.classe(p1a)}">{ui.pct(p1a)}</td><td>{ui.nombre(ind["rsi"], 0)}</td>'
                   f'<td>{ui.pct(FONDS[t_]["rendement"], 2, False)}</td><td>{ui.nombre(FONDS[t_]["per"], 1)}</td>'
                   f'<td>{len(FONDS[t_]["criteres"])}/5</td><td>{ui.nombre(SIGNAUX[t_].score, 0, True)}</td>'
                   f'<td>{ui.pastille(RECS[t_].code)}</td></tr>')
    H(ui.carte(f'<table class="tbl"><thead><tr><th>Action</th><th>Cours</th><th>Perf. 1 an</th><th>RSI</th>'
               f'<th>Rendement</th><th>PER</th><th>Santé</th><th>Score</th><th>Signal</th></tr></thead>'
               f'<tbody>{lignes}</tbody></table>', 1, plat=True))

# --------------------------------------------------------------------------- Mon profil
with onglets[5]:
    ui.entete("Client", "Mon profil", "Mieux vous connaître pour mieux vous conseiller.")
    if aide():
        H(ui.guide("Votre situation change ? Refaites le questionnaire plus bas."))
    p = ss.profil
    initiales = "".join(m[0] for m in p.nom_affiche.split()[:2]).upper() or "?"
    der_eval = p.historique[-1] if p.historique else None
    role_p = {"Prudent": "buy", "Équilibré": "accent", "Dynamique": "wait"}.get(p.profil_risque, "accent")
    g, d = st.columns([1, 1.6], gap="medium")
    with g:
        H(ui.carte(f"""<div style="text-align:center">
          <div style="width:96px;height:96px;border-radius:50%;margin:0 auto 1rem;display:grid;place-items:center;
          font-family:var(--serif);font-size:34px;font-weight:700;color:var(--ontint);background:var(--accent)">
          {ui.e(initiales)}</div>
          <div style="font-family:var(--serif);font-size:22px;font-weight:700">{ui.e(p.nom_affiche)}</div>
          <div class="petit">Investisseur au profil <b>{ui.e(p.profil_risque.lower())}</b></div>
          <div style="margin:.7rem auto 0;max-width:220px">{ui.barre((der_eval or {}).get("score", 75) / 100, role_p)}</div>
          <div class="legende" style="margin-top:.3rem">{f'score de risque {der_eval["score"]}/100 · évalué le '
                                                         f'{dt.date.fromisoformat(der_eval["date"]):%d/%m/%Y}'
                                                         if der_eval else "profil par défaut, questionnaire à remplir"}</div>
          <div style="margin-top:1rem">{"".join(f'<span class="chip">{ui.e(x)}</span>' for x in p.preferences)}</div></div>
          <div style="margin-top:1rem" class="petit">Capital : <span class="mono">{ui.euros(PF.apports(T))}</span><br>
          Horizon : {ui.e(p.horizon)}<br>Objectif : <span class="mono">{ui.pct(REGLES.objectif_hebdo, 0)}</span> par
          semaine<br>Perte maximale tolérée : <span class="mono">{ui.pct(-REGLES.tolerance_hebdo, 0)}</span> par
          semaine<br>Poids maximal d'une valeur : <span class="mono">{ui.pct(REGLES.poids_max_ligne, 0, False)}</span>
          <br>Affichage : {ui.e(p.mode.lower())}</div>""", 1))
    with d:
        with st.form("form_profil"):
            n1, n2 = st.columns(2)
            prenom_p = n1.text_input("Prénom", p.prenom or (p.nom_affiche.split(" ", 1)[0] if " " in p.nom_affiche else ""))
            nom = n2.text_input("Nom", p.nom_affiche[len(p.prenom):].strip() if p.prenom
                                else (p.nom_affiche.split(" ", 1)[1] if " " in p.nom_affiche else p.nom_affiche))
            c2, c3 = st.columns(2)
            source = c2.selectbox("Source des données", data.SOURCES, index=data.SOURCES.index(p.source_donnees),
                                  help="Yahoo Finance : cours réels. Démonstration : données fictives, pour découvrir "
                                       "l'application sans connexion.")
            mode_p = c3.selectbox("Affichage", theme.MODES, index=theme.MODES.index(p.mode),
                                  )
            prefs = st.multiselect("Préférences d'investissement",
                                   ["Dividendes", "Croissance", "Grandes capitalisations", "Valeurs défensives",
                                    "ESG", "Europe"], default=p.preferences)
            anim = st.toggle("Animations de l'interface", value=p.animations)
            aides_p = st.toggle("Afficher les aides sur chaque page", value=p.aides)
            if st.form_submit_button("Enregistrer mes préférences", type="primary"):
                p.prenom = prenom_p.strip()
                p.nom_affiche = " ".join(x for x in (p.prenom, nom.strip()) if x) or p.nom_affiche
                p.source_donnees, p.animations, p.preferences, p.mode = source, anim, prefs, mode_p
                p.aides = aides_p
                sauver()
                st.toast("Préférences enregistrées.")
                st.rerun()
        H(ui.carte(f"""<div class="label">Compte et confidentialité</div><div class="petit" style="margin-top:.4rem">
          Compte local <span class="mono">{ui.e((comptes.compte_par_uid(ss.uid) or {}).get("email", ""))}</span>.
          Vos préférences, votre profil et votre portefeuille sont enregistrés uniquement sur cet ordinateur
          (dossier <span class="mono">data/comptes</span>) ; le mot de passe n'est conservé que sous forme chiffrée.
          Rien n'est envoyé à un serveur tiers. Les cours proviennent de Yahoo Finance (bibliothèque yfinance), pour un
          usage strictement personnel.</div>""", 2, plat=True))
        st.write("")
        with st.expander("Supprimer mon compte"):
            st.write("Le compte, le profil et tout l'historique du portefeuille seront définitivement effacés de cet "
                     "ordinateur.")
            if st.checkbox("Je confirme vouloir supprimer mon compte", key="conf_suppr") and \
                    st.button("Supprimer définitivement", type="primary"):
                comptes.supprimer_compte(ss.uid)
                deconnecter()

    ui.section("Mon profil d'investisseur")
    questionnaire(False)
    H(ui.avertissement())

# --------------------------------------------------------------------------- Budget et règles
with onglets[6]:
    ui.entete("Paramètres", "Budget et règles", "Consulter et configurer les paramètres d'investissement.")
    if aide():
        H(ui.guide("Réglées d'après votre profil. Vérifiez l'effet d'un changement avec le <b>backtest</b>."))
    k = st.columns(4)
    k[0].markdown(ui.kpi("Budget", ui.euros(PF.apports(T)), f"Capital investi sur {len(COURS.columns)} valeurs", 1),
                  unsafe_allow_html=True)
    k[1].markdown(ui.kpi("Horizon", "1 an", f"{JOURS_PAR_AN} séances de bourse", 2), unsafe_allow_html=True)
    k[2].markdown(ui.kpi("Objectif hebdomadaire", f'<span class="pos">{ui.pct(REGLES.objectif_hebdo, 0)}</span>',
                         "Rendement visé par semaine", 3), unsafe_allow_html=True)
    k[3].markdown(ui.kpi("Perte maximale", f'<span class="neg">{ui.pct(-REGLES.tolerance_hebdo, 0)}</span>',
                         "Tolérance par semaine", 4), unsafe_allow_html=True)

    ui.section("Budget d'investissement")
    if not SIMU:
        H(ui.carte(f'<div class="petit">Capital investi depuis l\'ouverture : <span class="mono">{ui.euros(PF.apports(T))}'
                   f'</span> · valeur actuelle : <span class="mono">{ui.euros(VALEUR)}</span>. Pour investir davantage ou '
                   f'récupérer de l\'argent, utilisez <b>Ajouter ou retirer des liquidités</b> dans l\'onglet '
                   f'<b>Mes actions</b> : chaque mouvement est daté dans l\'historique.</div>', plat=True))
        st.write("")
    else:
        b1, b2, b3 = st.columns([1.2, 1, 1.6], vertical_alignment="bottom")
        nouveau = float(b1.number_input("Capital d'essai du simulateur (€)", min_value=1_000.0, max_value=100_000_000.0,
                                        value=float(CAPITAL), step=1_000.0 if CAPITAL >= 10_000 else 100.0, format="%.0f",
                                        key="capital_budget"))
        if b2.button("Modifier le capital", type="primary", use_container_width=True, disabled=nouveau == CAPITAL):
            ratio = nouveau / CAPITAL
            dialogue_selection(list(ss.tickers), {t_: v * ratio for t_, v in ss.allocation.items()}, nouveau)
        b3.markdown('<div class="petit">La répartition est conservée en proportion et le simulateur redémarre au début '
                    'de l\'année passée.</div>', unsafe_allow_html=True)

    ui.section("Règles de décision")
    H(ui.carte(f'<div class="petit">{"Règles calées sur votre profil" if ss.profil.regles_auto else "Règles personnalisées, à partir du profil"} '
               f'<b>{ui.e(ss.profil.profil_risque.lower())}</b> : chaque valeur est limitée à '
               f'<span class="mono">{ui.pct(REGLES.poids_max_ligne, 0, False)}</span> du portefeuille et les achats sont '
               f'écartés au-delà de <span class="mono">{ui.pct(REGLES.vol_max, 0, False)}</span> de volatilité annuelle. '
               f'Le questionnaire de l\'onglet « Mon profil » ajuste ces seuils.</div>', plat=True))
    st.write("")
    r = REGLES
    with st.form("form_regles"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Vente**")
            sl = st.slider("Stop-loss : perte depuis l'achat", 1, 20, int(round(r.stop_loss * 100)), format="%d %%")
            tp = st.slider("Take-profit : gain depuis l'achat", 2, 40, int(round(r.take_profit * 100)), format="%d %%")
            td = st.slider("Trailing stop : gain déclencheur", 1, 20, int(round(r.trailing_declenchement * 100)),
                           format="%d %%")
            tr = st.slider("Trailing stop : repli depuis le plus haut", 1, 15, int(round(r.trailing_repli * 100)),
                           format="%d %%")
        with c2:
            st.markdown("**Achat et indicateurs**")
            rh = st.slider("RSI : seuil de surachat", 55, 90, int(r.rsi_surachat))
            rb = st.slider("RSI : seuil de survente", 10, 45, int(r.rsi_survente))
            mc, ml = st.slider("Moyennes mobiles (courte, longue)", 5, 200, (r.mm_courte, r.mm_longue), step=5)
            mini = st.number_input("Montant d'achat minimum (€)", 100, 100_000, int(r.montant_achat_min), step=500)
            part = st.slider("Part des liquidités engagée par achat", 10, 100, int(round(r.part_achat * 100)), step=5,
                             format="%d %%")
        with c3:
            st.markdown("**Risque global, prioritaire**")
            al = st.slider("Alerte si perte sur la semaine", 1, 20, int(round(r.alerte_perte_hebdo * 100)),
                           format="%d %%")
            su = st.slider("Suspension des achats si perte", 2, 30, int(round(r.suspension_perte_hebdo * 100)),
                           format="%d %%")
            se = st.slider("Sécuriser les gains si rendement", 2, 30, int(round(r.securisation_gain_hebdo * 100)),
                           format="%d %%")
            ob = st.slider("Objectif de rendement hebdomadaire", 1, 20, int(round(r.objectif_hebdo * 100)),
                           format="%d %%")
            to = st.slider("Tolérance maximale aux pertes", 1, 20, int(round(r.tolerance_hebdo * 100)), format="%d %%")
        if st.form_submit_button("Enregistrer les règles", type="primary"):
            if mc >= ml:
                st.error("La moyenne mobile courte doit être inférieure à la longue.")
            elif al >= su:
                st.error("Le seuil d'alerte doit être inférieur au seuil de suspension des achats.")
            else:
                ss.regles = Regles(stop_loss=sl / 100, take_profit=tp / 100, trailing_declenchement=td / 100,
                                   trailing_repli=tr / 100, rsi_surachat=rh, rsi_survente=rb, mm_courte=mc,
                                   mm_longue=ml, alerte_perte_hebdo=al / 100, suspension_perte_hebdo=su / 100,
                                   securisation_gain_hebdo=se / 100, objectif_hebdo=ob / 100, tolerance_hebdo=to / 100,
                                   montant_achat_min=float(mini), part_achat=part / 100,
                                   poids_max_ligne=r.poids_max_ligne, vol_max=r.vol_max)
                ss.profil.regles_auto = False
                ss.backtest = None
                sauver()
                st.toast("Règles enregistrées.")
                st.rerun()
    if st.button(f"Rétablir les règles de mon profil ({ss.profil.profil_risque.lower()})"):
        ss.regles = pr.regles_pour(ss.profil.profil_risque); ss.profil.regles_auto = True
        ss.backtest = None; sauver(); st.rerun()

    ui.section("Backtest sur l'année")
    st.caption("Rejoue l'année passée avec ces règles.")
    c1, c2, _ = st.columns([1, 1.3, 2])
    if c1.button("Lancer le backtest", type="primary", use_container_width=True):
        with st.spinner("Calcul en cours…"):
            ss.backtest = engine.backtest(COURS, ss.allocation, REGLES, T0, CAPITAL, SOURCE)
    if c2.button("Vérifier la reproductibilité", use_container_width=True):
        empreintes = []
        for _ in range(2):
            res = engine.backtest(COURS, ss.allocation, REGLES, T0, CAPITAL, SOURCE)
            empreintes.append(hashlib.sha256(res.valeurs.round(6).to_json().encode()).hexdigest()[:16])
        if empreintes[0] == empreintes[1]:
            st.success(f"Deux exécutions donnent un résultat identique (empreinte {empreintes[0]}).")
        else:
            st.error(f"Résultats différents : {empreintes}")
    bt = ss.backtest
    if bt is not None:
        hebdo_bt = bt.hebdo()
        k = st.columns(5)
        ecart = (bt.rendement - bt.rendement_reference) * 100
        k[0].metric("Stratégie", ui.pct(bt.rendement), f"{ecart:+.1f} pt vs réf.".replace(".", ","))
        k[1].metric("Achat-conservation", ui.pct(bt.rendement_reference))
        k[2].metric("Baisse maximale", ui.pct(bt.drawdown_max))
        k[3].metric("Opérations", f"{len(bt.portefeuille.transactions)}")
        k[4].metric("Durée", f"{ui.nombre(bt.duree_s, 2)} s", "< 5 min" if bt.duree_s < 300 else "> 5 min",
                    delta_color="off")
        st.caption(f"Semaines au-dessus de l'objectif de {ui.pct(REGLES.objectif_hebdo, 0, False)} : "
                   f"{int((hebdo_bt >= REGLES.objectif_hebdo).sum())} sur {len(hebdo_bt)}. "
                   f"Semaines sous le seuil d'alerte : {int((hebdo_bt <= -REGLES.alerte_perte_hebdo).sum())}.")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bt.reference.index, y=bt.reference, name="Achat-conservation",
                                 line=dict(color=TK["muted"], width=1.3, dash="dash", **SPL)))
        fig.add_trace(go.Scatter(x=bt.valeurs.index, y=bt.valeurs, name="Stratégie Boussole",
                                 line=dict(color=TK["accent"], width=1.8, **SPL),
                                 fill="tozeroy", fillcolor=theme.rgba(TK["accent"], .13)))
        fig.update_yaxes(range=[min(bt.valeurs.min(), bt.reference.min()) * .98,
                                max(bt.valeurs.max(), bt.reference.max()) * 1.01], ticksuffix=" €")
        st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)
        motifs = pd.Series([o["motif"] for o in bt.portefeuille.transactions]).value_counts()
        H("".join(f'<span class="chip"><span class="mono">{ui.e(m)}</span>&nbsp;·&nbsp;{n}</span>'
                  for m, n in motifs.items()))
    H(ui.avertissement())


# =========================================================================== #
# Lecture automatique
# =========================================================================== #
if ss.lecture and SIMU and T < N - 1:
    time.sleep(1.2)
    avancer(1)
    st.rerun()
