"""Comptes utilisateurs locaux.

Tout reste sur l'ordinateur de l'utilisateur (dossier data/comptes) : aucun envoi vers un serveur.
Les mots de passe ne sont jamais enregistrés en clair : seule une empreinte PBKDF2-SHA256 salée
(200 000 itérations) est conservée. Une session ouverte est identifiée par un jeton aléatoire.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent.parent / "data" / "comptes"
ITERATIONS = 200_000
DUREE_SESSION_JOURS = 30
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class ErreurCompte(ValueError):
    """Saisie invalide ou identifiants incorrects (message lisible par l'utilisateur)."""


def _lire(nom: str) -> dict:
    f = DOSSIER / nom
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}


def _ecrire(nom: str, contenu: dict) -> None:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tmp = DOSSIER / (nom + ".tmp")
    tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DOSSIER / nom)


def _empreinte(mdp: str, sel: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"), sel, ITERATIONS).hex()


def normaliser(email: str) -> str:
    return (email or "").strip().lower()


def verifier_mot_de_passe(mdp: str) -> list[str]:
    """Liste des règles non respectées (vide si le mot de passe convient)."""
    manques = []
    if len(mdp or "") < 8:
        manques.append("au moins 8 caractères")
    if not re.search(r"[A-Za-zÀ-ÿ]", mdp or ""):
        manques.append("une lettre")
    if not re.search(r"\d", mdp or ""):
        manques.append("un chiffre")
    return manques


def creer_compte(email: str, nom: str, mdp: str, prenom: str | None = None) -> str:
    email = normaliser(email)
    if not _EMAIL.match(email):
        raise ErreurCompte("Adresse e-mail invalide.")
    if prenom is not None and not prenom.strip():
        raise ErreurCompte("Indiquez votre prénom.")
    if not (nom or "").strip():
        raise ErreurCompte("Indiquez votre nom.")
    manques = verifier_mot_de_passe(mdp)
    if manques:
        raise ErreurCompte("Le mot de passe doit contenir " + ", ".join(manques) + ".")
    comptes = _lire("comptes.json")
    if email in comptes:
        raise ErreurCompte("Un compte existe déjà avec cette adresse. Connectez-vous.")
    sel = secrets.token_bytes(16)
    uid = secrets.token_hex(8)
    comptes[email] = dict(uid=uid, nom=nom.strip(), prenom=(prenom or "").strip(), sel=sel.hex(), empreinte=_empreinte(mdp, sel),
                          cree=dt.datetime.now().isoformat(timespec="seconds"))
    _ecrire("comptes.json", comptes)
    return uid


def connecter(email: str, mdp: str) -> str:
    compte = _lire("comptes.json").get(normaliser(email))
    if not compte or not hmac.compare_digest(compte["empreinte"],
                                             _empreinte(mdp or "", bytes.fromhex(compte["sel"]))):
        raise ErreurCompte("Adresse e-mail ou mot de passe incorrect.")
    return compte["uid"]


def compte_par_uid(uid: str) -> dict | None:
    for email, c in _lire("comptes.json").items():
        if c["uid"] == uid:
            return dict(email=email, nom=c["nom"], prenom=c.get("prenom", ""), cree=c.get("cree"))
    return None


def ouvrir_session(uid: str) -> str:
    sessions = {k: v for k, v in _lire("sessions.json").items()
                if v.get("expire", "") > dt.datetime.now().isoformat()}
    jeton = secrets.token_urlsafe(24)
    sessions[jeton] = dict(uid=uid, expire=(dt.datetime.now() + dt.timedelta(days=DUREE_SESSION_JOURS)).isoformat())
    _ecrire("sessions.json", sessions)
    return jeton


def session_uid(jeton: str | None) -> str | None:
    if not jeton:
        return None
    s = _lire("sessions.json").get(jeton)
    if not s or s.get("expire", "") <= dt.datetime.now().isoformat():
        return None
    return s["uid"]


def fermer_session(jeton: str | None) -> None:
    sessions = _lire("sessions.json")
    if jeton and sessions.pop(jeton, None) is not None:
        _ecrire("sessions.json", sessions)


def fichier_etat(uid: str) -> Path:
    return DOSSIER / f"etat_{uid}.json"


def supprimer_compte(uid: str) -> None:
    comptes = {k: v for k, v in _lire("comptes.json").items() if v["uid"] != uid}
    _ecrire("comptes.json", comptes)
    sessions = {k: v for k, v in _lire("sessions.json").items() if v["uid"] != uid}
    _ecrire("sessions.json", sessions)
    fichier_etat(uid).unlink(missing_ok=True)
