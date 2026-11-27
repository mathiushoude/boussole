"""Habillage « liquid glass » conforme à la charte graphique Boussole v3.

- Typographies : Source Serif 4 (titres), IBM Plex Sans (interface), IBM Plex Mono (chiffres).
- Couleurs : uniquement les rôles de la charte (fond, surface, texte, secondaire, bordure,
  accent, hausse, baisse, neutre), en mode clair ou sombre.
- Verre : surfaces translucides floutées (backdrop-filter), liseré lumineux, reflet qui suit
  le curseur. Aucun dégradé décoratif ; seul fondu autorisé : sous la courbe de prix.
- Mouvement : amorti, jamais en boucle (aiguille à ressort 450 ms, écrans 300 ms,
  courbes tracées en 600 ms). Le réglage « mouvement réduit » du système est respecté.
"""
from __future__ import annotations

import html
import math
from urllib.parse import quote

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from .theme import rgba

TK: dict = {}          # jetons du mode courant (renseignés par injecter_style)
MOTS = {1: "ACHETER", 0: "ATTENDRE", -1: "VENDRE"}
FORMES = {1: "▲", 0: "◆", -1: "▼"}
ROLES = {1: "buy", 0: "wait", -1: "sell"}
AVERTISSEMENT = ("Boussole est un outil d'information et d'aide à l'analyse. Elle ne constitue pas un conseil en "
                 "investissement personnalisé. Tout investissement comporte un risque de perte en capital et les "
                 "performances passées ne préjugent pas des performances futures.")


def e(txt) -> str:
    return html.escape(str(txt))


# --------------------------------------------------------------------------- #
# Formats (chiffres : virgule décimale, espace fine, signe explicite)
# --------------------------------------------------------------------------- #
def nombre(v: float, dec: int = 2, signe: bool = False) -> str:
    v = 0.0 if abs(v) < 0.5 * 10 ** -dec else v
    s = f"{v:+,.{dec}f}" if signe else f"{v:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",").replace("-", "−")


def euros(v: float, dec: int = 0, signe: bool = False) -> str:
    return nombre(v, dec, signe) + " €"


def pct(v: float, dec: int = 1, signe: bool = True) -> str:
    return nombre(v * 100, dec, signe) + " %"


def classe(v: float) -> str:
    return "pos" if v > 1e-9 else ("neg" if v < -1e-9 else "neutre")


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
def _cadran_fond(t: dict) -> str:
    """Grand cadran gradué (48 graduations) en filigrane : le verre le floute."""
    R, c = 300, 320
    traits = []
    for i in range(48):
        a = math.radians(i * 7.5)
        long_ = i % 6 == 0
        r1 = R - (34 if long_ else 16)
        traits.append(f'<line x1="{c + r1 * math.sin(a):.1f}" y1="{c - r1 * math.cos(a):.1f}" '
                      f'x2="{c + R * math.sin(a):.1f}" y2="{c - R * math.cos(a):.1f}" '
                      f'stroke-width="{6 if long_ else 3}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640">'
           f'<g fill="none" stroke="{t["border"]}" stroke-linecap="round">'
           f'<circle cx="{c}" cy="{c}" r="{R}" stroke-width="10"/>{"".join(traits)}'
           f'<circle cx="{c}" cy="{c}" r="{R * .62:.0f}" stroke-width="2" stroke-dasharray="2 14"/></g></svg>')
    return "data:image/svg+xml;utf8," + quote(svg)


def css(t: dict, animations: bool) -> str:
    sombre = t["nom"] == "sombre"
    verre = rgba(t["surface"], .58 if sombre else .62)
    verre_fort = rgba(t["surface"], .80 if sombre else .84)
    reflet = rgba("#FFFFFF", .08 if sombre else .9)
    lueur = rgba("#FFFFFF", .035 if sombre else .22)
    arete_bas = rgba("#FFFFFF", .03 if sombre else .35)
    arete_cote = rgba("#FFFFFF", .04 if sombre else .45)
    ombre = "0 8px 32px rgba(0,0,0,.35)" if sombre else "0 8px 28px rgba(15,23,42,.07)"
    return f"""
<style>
@font-face{{font-family:'IBM Plex Sans';src:url('/app/static/fonts/IBMPlexSans.woff2') format('woff2');font-weight:100 700;font-display:swap}}
@font-face{{font-family:'Source Serif 4';src:url('/app/static/fonts/SourceSerif4.woff2') format('woff2');font-weight:200 900;font-display:swap}}
@font-face{{font-family:'IBM Plex Mono';src:url('/app/static/fonts/IBMPlexMono-400.woff2') format('woff2');font-weight:400;font-display:swap}}
@font-face{{font-family:'IBM Plex Mono';src:url('/app/static/fonts/IBMPlexMono-500.woff2') format('woff2');font-weight:500;font-display:swap}}
@font-face{{font-family:'IBM Plex Mono';src:url('/app/static/fonts/IBMPlexMono-600.woff2') format('woff2');font-weight:600;font-display:swap}}
:root{{--bg:{t["bg"]};--surface:{t["surface"]};--text:{t["text"]};--muted:{t["muted"]};--border:{t["border"]};
  --accent:{t["accent"]};--buy:{t["buy"]};--sell:{t["sell"]};--wait:{t["wait"]};--ontint:{t["ontint"]};
  --verre:{verre};--verre-fort:{verre_fort};--reflet:{reflet};--lueur:{lueur};
  --flou: blur(22px) saturate(180%);--arete:inset 0 1px 0 var(--reflet), inset 0 -1px 0 {arete_bas}, inset 1px 0 0 {arete_cote}, inset -1px 0 0 {arete_cote};--ease: cubic-bezier(.22,.8,.3,1);--ressort: cubic-bezier(.34,1.56,.64,1);
  --serif:'Source Serif 4',Georgia,serif;--sans:'IBM Plex Sans','Segoe UI',system-ui,sans-serif;--mono:'IBM Plex Mono',Consolas,monospace}}
html,body,.stApp{{font-family:var(--sans);color:var(--text)}}
.stApp{{background:var(--bg) !important;transition: background-color .25s ease, color .25s ease}}
[data-testid="stHeader"]{{background:transparent}}
[data-testid="stMainBlockContainer"]{{padding-top:2rem;max-width:1360px}}
/* Cadran en filigrane (instrument, pas décor) */
[data-testid="stAppViewContainer"]{{isolation:isolate}}
[data-testid="stAppViewContainer"] > *{{position:relative;z-index:1}}
[data-testid="stAppViewContainer"]::before{{content:"";position:fixed;z-index:0;pointer-events:none;
  width:min(78vw,860px);aspect-ratio:1;right:-14vw;top:-10vh;background:url("{_cadran_fond(t)}") center/contain no-repeat;opacity:.7;
  transform:translate(var(--px,0),var(--py,0)) rotate(var(--prot,0deg));transition:transform .9s var(--ease)}}

/* ---------- Verre liquide ---------- */
.glass{{position:relative;background:var(--verre);backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);
  border:1px solid var(--border);border-radius:12px;padding:18px 20px;overflow:hidden;color:var(--text);
  box-shadow:{ombre}, var(--arete);transition: transform .3s var(--ease), border-color .3s var(--ease);
  animation: apparait .3s var(--ease) both}}
.glass::before{{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;
  background:radial-gradient(360px circle at var(--mx,50%) var(--my,0%), var(--lueur), transparent 60%);
  transition:opacity .3s var(--ease)}}
.glass:hover{{border-color:{rgba(t["accent"], .28)}}}
.glass:hover::before{{opacity:1}}
.glass.plat:hover{{transform:none}}
@keyframes apparait{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.d1{{animation-delay:.03s}}.d2{{animation-delay:.06s}}.d3{{animation-delay:.09s}}.d4{{animation-delay:.12s}}.d5{{animation-delay:.15s}}

/* ---------- Typographie ---------- */
.titre,.section-t,.titre-xl{{font-family:var(--serif);font-weight:700;color:var(--text)}}
.surtitre{{color:var(--accent);font-size:13px;line-height:18px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}}
.titre{{font-size:28px;line-height:34px;margin:.2rem 0 0}}
.titre-xl{{font-size:40px;line-height:46px;letter-spacing:-.015em;margin:0}}
.trait{{width:56px;height:2px;background:var(--accent);border-radius:2px;margin:.45rem 0 1rem}}
.section-t{{font-size:20px;line-height:26px;margin:1.6rem 0 0}}
.label{{color:var(--muted);font-size:11px;line-height:16px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}}
.mono{{font-family:var(--mono);font-weight:500;font-variant-numeric:tabular-nums}}
.valeur{{font-family:var(--mono);font-weight:500;font-size:clamp(17px,2.1vw,24px);line-height:1.25;margin-top:.2rem;white-space:nowrap}}
.label{{overflow-wrap:normal;word-break:normal}}
.petit{{font-size:13px;line-height:18px;color:var(--muted)}}
.legende{{font-size:11px;line-height:16px;color:var(--muted);font-weight:500}}
.pos{{color:var(--buy)}} .neg{{color:var(--sell)}} .neutre{{color:var(--muted)}}
.avert{{font-size:11px;line-height:16px;color:var(--muted);margin-top:.8rem}}

/* ---------- Pastilles de signal : couleur + signe + mot + forme ---------- */
.pill{{display:inline-flex;align-items:center;gap:.45rem;min-height:28px;padding:0 .9rem;border-radius:999px;
  font-size:12px;font-weight:700;letter-spacing:.06em;color:var(--ontint);white-space:nowrap}}
.pill.buy{{background:var(--buy)}} .pill.sell{{background:var(--sell)}} .pill.wait{{background:var(--wait)}}
.pill.grand{{min-height:36px;font-size:13px;padding:0 1.1rem}}
.pill .f{{font-size:.8em}}
.chip{{display:inline-flex;align-items:center;min-height:26px;padding:0 .7rem;border-radius:999px;font-size:12px;
  border:1px solid var(--border);color:var(--muted);margin:0 .35rem .35rem 0;background:var(--verre)}}
.code{{font-family:var(--mono);font-size:11px;color:var(--accent);border:1px solid {rgba(t["accent"], .4)};
  border-radius:999px;padding:1px 8px;white-space:nowrap}}
/* ---------- Boussole interactive (page de connexion) : mouvements déclenchés par l'utilisateur ---------- */
.bs-zone{{display:flex;align-items:center;gap:1.6rem;margin-bottom:.4rem}}
.bs-rose{{flex:none;cursor:pointer;overflow:visible;filter:drop-shadow(0 10px 30px {rgba(t["accent"], .18)});
  transition:filter .3s var(--ease)}}
.bs-rose:hover{{filter:drop-shadow(0 12px 36px {rgba(t["accent"], .32)})}}
.bs-rose .bs-cadran{{stroke:var(--text)}}
.bs-rose .bs-ticks line{{stroke:var(--muted);stroke-dasharray:12;stroke-dashoffset:12;animation:trace .6s var(--ease) forwards}}
.bs-rose .bs-ticks line.l{{stroke:var(--text)}}
.bs-rose text{{font-family:var(--serif);font-weight:700;font-size:15px;fill:var(--muted);text-anchor:middle;
  dominant-baseline:central;transition:fill .3s var(--ease)}}
.bs-rose text.n{{fill:var(--accent)}}
.bs-rose .bs-seg{{fill:none;stroke:var(--border);stroke-width:5;stroke-linecap:round;opacity:0;transition:stroke .3s var(--ease),opacity .3s var(--ease)}}
.bs-rose.mdp .bs-seg{{opacity:1}} .bs-rose .bs-seg.on{{stroke:var(--accent)}} .bs-rose .bs-seg.tout{{stroke:var(--buy)}}
#bs-aiguille{{transform-origin:100px 100px;transform:rotate(0deg)}}
#bs-aiguille .tete{{fill:var(--accent);transition:fill .3s var(--ease)}} #bs-aiguille .queue{{fill:var(--muted)}}
.bs-rose.ok #bs-aiguille .tete{{fill:var(--buy)}} .bs-rose.err #bs-aiguille .tete{{fill:var(--sell)}}
.bs-rose.jeu #bs-aiguille .tete{{fill:var(--wait)}}
.bs-rose.secoue{{animation:secoue .45s var(--ease) 1}}
@keyframes secoue{{0%,100%{{transform:translateX(0)}}20%{{transform:translateX(-7px)}}40%{{transform:translateX(6px)}}60%{{transform:translateX(-4px)}}80%{{transform:translateX(2px)}}}}
.bs-halo{{fill:none;stroke:var(--accent);stroke-width:1.5;opacity:0}}
.bs-rose.pulse .bs-halo{{animation:halo .7s var(--ease) 1}}
@keyframes halo{{from{{opacity:.7;r:60}}to{{opacity:0;r:98}}}}
.bs-msg{{min-height:44px;font-size:14px;line-height:21px;color:var(--muted);padding:10px 14px;border-radius:12px;
  border:1px solid var(--border);background:var(--verre);margin:.6rem 0 1rem;max-width:520px}}
.bs-msg.ok{{color:var(--buy);border-color:{rgba(t["buy"], .45)}}} .bs-msg.err{{color:var(--sell);border-color:{rgba(t["sell"], .45)}}}
.bs-msg.jeu{{color:var(--wait);border-color:{rgba(t["wait"], .45)}}}
.bs-pop{{animation:apparait .3s var(--ease) 1}}
.bs-record{{font-family:var(--mono);font-size:12px;color:var(--muted)}}
/* Chargement : la boussole s'oriente une fois, puis s'efface (aucune boucle) */
#bs-charge{{position:fixed;inset:0;z-index:999999;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:14px;background:{rgba(t["bg"], .78)};backdrop-filter:blur(18px) saturate(1.2);-webkit-backdrop-filter:blur(18px) saturate(1.2);
  transition:opacity .38s var(--ease),transform .38s var(--ease)}}
#bs-charge.premier{{animation:efface .42s var(--ease) 30s forwards}}   /* filet de sécurité */
#bs-charge.premier .ag{{animation:tourne 1.1s linear infinite}}       /* chargement : seule boucle, fonctionnelle */
#bs-charge.premier.fini .ag{{animation:none;transition:transform .45s var(--ressort)}}
#bs-charge.premier.part{{animation:none}}
@keyframes tourne{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
#bs-charge.premier .lg span{{grid-area:1/1}} #bs-charge.premier .lg{{display:grid;justify-items:center}}
#bs-charge.premier .lg .b{{opacity:0;color:var(--accent)}}
#bs-charge.premier.fini .lg .a{{opacity:0;transition:opacity .2s var(--ease)}}
#bs-charge.premier.fini .lg .b{{opacity:1;transition:opacity .25s var(--ease) .1s}}
@keyframes oriente{{to{{transform:rotate(0deg)}}}}
@keyframes efface{{to{{opacity:0;visibility:hidden}}}}
@media (prefers-reduced-motion: reduce){{#bs-charge.premier{{display:none}}}}
#bs-charge.leger{{background:{rgba(t["bg"], .55)}}}
#bs-charge.part{{opacity:0;transform:scale(1.03);pointer-events:none}}
#bs-charge .lentille{{width:168px;height:168px;border-radius:50%;display:grid;place-items:center;background:var(--verre);
  border:1px solid var(--border);backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);box-shadow:{ombre}, var(--arete);
  animation:apparait .4s var(--ease) both}}
#bs-charge svg{{overflow:visible;filter:drop-shadow(0 14px 40px {rgba(t["accent"], .25)})}}
#bs-charge .cad{{fill:none;stroke:var(--text);stroke-width:2;stroke-dasharray:290;stroke-dashoffset:290;animation:trace .7s var(--ease) forwards}}
#bs-charge .tk line{{stroke:var(--muted);stroke-dasharray:10;stroke-dashoffset:10;animation:trace .4s var(--ease) forwards}}
#bs-charge .tk line.l{{stroke:var(--text)}}
#bs-charge .ag{{transform-origin:50px 50px;transform:rotate(var(--de));transition:transform var(--dur,1s) var(--ressort)}}
#bs-charge .nom{{font-family:var(--serif);font-size:30px;font-weight:700;color:var(--text);opacity:0;animation:apparait .5s var(--ease) .35s forwards}}
#bs-charge .lg{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);min-height:18px;transition:color .3s var(--ease)}}
#bs-charge .lg.ok{{color:var(--accent)}}
#bs-charge.leger .nom{{display:none}}
.bs-entree{{animation:apparait .45s var(--ease) both}}
#bs-calcul{{position:fixed;top:14px;right:72px;z-index:99999;display:flex;align-items:center;gap:8px;padding:6px 12px 6px 8px;
  border-radius:999px;font-size:12.5px;color:var(--muted);background:{rgba(t["surface"], .72)};border:1px solid var(--border);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);opacity:0;transform:translateY(-6px);
  transition:opacity .25s var(--ease),transform .25s var(--ease);pointer-events:none}}
#bs-calcul.vu{{opacity:1;transform:none}}
#bs-calcul .ag{{transform-origin:12px 12px}}
#bs-calcul.vu .ag{{animation:cherche 1.8s var(--ease) 1 forwards}}
@keyframes cherche{{0%{{transform:rotate(-90deg)}}35%{{transform:rotate(40deg)}}60%{{transform:rotate(-18deg)}}80%{{transform:rotate(7deg)}}100%{{transform:rotate(0)}}}}
.atout{{border-radius:12px;padding:4px 8px;margin-left:-8px;transition:background .25s var(--ease),transform .25s var(--ease)}}
.atout:hover{{background:{rgba(t["accent"], .07)};transform:translateX(4px)}}
.atout:hover .n{{background:var(--accent);color:var(--ontint)}}
.logo.vive .aiguille{{animation:none;transition:transform .45s var(--ressort)}}
.glass:not(.plat){{transform:perspective(900px) translateY(var(--ty,0)) rotateX(var(--rx,0deg)) rotateY(var(--ry,0deg))}}
.glass:not(.plat):hover{{--ty:-1px}}
.ondee{{position:absolute;border-radius:50%;pointer-events:none;background:currentColor;opacity:.25;transform:scale(0);
  animation:ondee .55s var(--ease) forwards}}
@keyframes ondee{{to{{transform:scale(1);opacity:0}}}}
.stButton>button,.stFormSubmitButton>button{{position:relative;overflow:hidden}}
[role="tab"]{{transition:color .25s var(--ease),transform .25s var(--ease)}} [role="tab"]:hover{{transform:translateY(-1px)}}
.premiers .pas.fait .c{{animation:coche .45s var(--ressort) 1}}
@keyframes coche{{from{{transform:scale(.2)}}to{{transform:scale(1)}}}}
.ligne-suivi,.raison{{transition:background .2s var(--ease)}}
.accroche{{max-width:520px;animation:apparait .5s ease both}}
.atout{{display:flex;gap:.9rem;align-items:flex-start;margin:.9rem 0}}
.atout .n{{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-family:var(--mono);font-size:13px;
  color:var(--accent);border:1px solid {rgba(t["accent"], .45)};background:{rgba(t["accent"], .10)}}}
.atout b{{display:block;font-size:15px;margin-bottom:.1rem}}
.etapes{{display:flex;align-items:center;gap:.5rem;margin:.2rem 0 1rem;flex-wrap:wrap}}
.etapes .e{{display:flex;align-items:center;gap:.45rem;font-size:13px;color:var(--muted)}}
.etapes .e .p{{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-family:var(--mono);font-size:12px;
  border:1px solid var(--border)}}
.etapes .e.fait .p{{background:var(--accent);color:var(--ontint);border-color:var(--accent)}}
.etapes .e.cours{{color:var(--text);font-weight:600}} .etapes .e.cours .p{{border-color:var(--accent);color:var(--accent)}}
.etapes .l{{width:28px;height:1px;background:var(--border)}}
.guide{{display:flex;gap:.8rem;align-items:flex-start;padding:12px 16px;margin:0 0 1rem;border-radius:12px;
  border:1px solid {rgba(t["accent"], .35)};background:{rgba(t["accent"], .07)};font-size:14px;line-height:21px;animation:apparait .35s ease both}}
.guide .i{{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;background:var(--accent);
  color:var(--ontint);font-family:var(--serif);font-weight:700;font-size:13px;margin-top:1px}}
.guide b{{color:var(--text)}}
.entete-app{{display:flex;align-items:center;gap:.8rem}}
.entete-app .nom{{font-family:var(--serif);font-weight:700;font-size:26px;line-height:28px}}
.entete-app .sous{{font-size:12px;color:var(--muted)}}
.premiers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.6rem;margin-top:.7rem}}
.premiers .pas{{display:flex;gap:.55rem;align-items:flex-start;font-size:13px;line-height:18px;padding:10px 12px;border-radius:10px;
  border:1px solid var(--border)}}
.premiers .pas .c{{flex:none;width:18px;height:18px;border-radius:50%;border:1.5px solid var(--muted);display:grid;place-items:center;
  font-size:11px;margin-top:1px}}
.premiers .pas.fait{{border-color:{rgba(t["buy"], .45)}}} .premiers .pas.fait .c{{background:var(--buy);border-color:var(--buy);color:var(--ontint)}}
.indices{{display:flex;gap:1.1rem;flex-wrap:wrap;align-items:center}}
[data-testid="stMultiSelect"] .react-aria-ComboBox>div{{max-height:none!important;height:auto!important;min-height:40px}}
[data-testid="stMultiSelect"] .react-aria-ComboBox>div>div{{overflow:visible!important;height:auto!important;flex-wrap:wrap!important;padding:3px 0}}
[data-testid="stMultiSelect"] .react-aria-ComboBox>div>div>span:first-child{{display:flex!important;flex-wrap:wrap!important;gap:4px}}
.ligne-recherche{{padding:.35rem .2rem;border-top:1px solid var(--border);font-size:14px;line-height:19px;animation:apparait .3s ease both}}
.raison{{display:flex;gap:.7rem;align-items:flex-start;padding:.6rem 0;border-top:1px solid var(--border);font-size:14px}}
.raison .puce{{flex:none;width:8px;height:8px;border-radius:50%;margin-top:7px}}
.raison:first-child{{border-top:0}}

/* ---------- Bandeau de risque ---------- */
.risque{{border:1px solid var(--border);border-left:4px solid var(--c);padding:12px 16px;border-radius:12px;
  background:var(--verre);backdrop-filter:var(--flou);margin:.4rem 0 1rem;animation:apparait .3s var(--ease) both}}
.risque b{{display:block;font-size:14px}} .risque span{{font-size:13px;color:var(--muted)}}

/* ---------- Barres ---------- */
.piste{{height:8px;border-radius:999px;background:{rgba(t["muted"], .2)};position:relative;overflow:hidden}}
.piste > i{{position:absolute;top:0;bottom:0;border-radius:999px;background:var(--c);animation:remplit .6s var(--ease) both}}
@keyframes remplit{{from{{transform:scaleX(0)}}}}
.pilier{{display:grid;grid-template-columns:150px 1fr 52px;gap:14px;align-items:center;padding:.45rem 0;font-size:14px}}

/* ---------- Jauge de décision / logo : ressort amorti 450 ms ---------- */
.aiguille{{transform:rotate(var(--a));animation:pivote .45s var(--ressort) both}}
.jauge .aiguille{{transform-origin:100px 100px}} .logo .aiguille{{transform-origin:50px 50px}}
@keyframes pivote{{from{{transform:rotate(var(--a0))}}to{{transform:rotate(var(--a))}}}}
.mot{{font-weight:700;font-size:20px;letter-spacing:.04em;margin-top:.2rem}}

/* ---------- Courbes : tracé progressif 600 ms ---------- */
.spark path.l{{fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1000;
  stroke-dashoffset:1000;animation:trace .6s var(--ease) forwards}}
@keyframes trace{{to{{stroke-dashoffset:0}}}}
[data-testid="stPlotlyChart"] .scatterlayer,[data-testid="stPlotlyChart"] .barlayer{{animation:devoile .6s var(--ease) both}}
@keyframes devoile{{from{{clip-path:inset(0 100% 0 0)}}to{{clip-path:inset(0 0 0 0)}}}}

/* ---------- Liste de suivi ---------- */
.ligne{{display:grid;grid-template-columns:1.4fr 1.6fr 1fr 130px;gap:14px;align-items:center;padding:10px 16px;
  border-radius:12px;border:1px solid var(--border);background:var(--verre);backdrop-filter:var(--flou);
  -webkit-backdrop-filter:var(--flou);margin-bottom:8px;transition:transform .3s var(--ease), border-color .3s;
  animation:apparait .3s var(--ease) both;box-shadow:inset 0 1px 0 var(--reflet)}}
.ligne:hover{{transform:translateX(3px);border-color:{rgba(t["accent"], .45)}}}

/* ---------- Actualités ---------- */
.news{{padding:12px 0;border-top:1px solid var(--border);animation:apparait .3s var(--ease) both}}
.news a,.news .t{{color:var(--text);text-decoration:none;font-weight:600}} .news a:hover{{color:var(--accent)}}

/* ---------- Tableaux ---------- */
.tbl{{width:100%;border-collapse:collapse;font-size:14px}}
.tbl th{{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;text-align:right;
  padding:6px 10px;border-bottom:1px solid var(--border)}}
.tbl td{{padding:10px;text-align:right;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:13px}}
.tbl th:first-child,.tbl td:first-child{{text-align:left;font-family:var(--sans)}}
.tbl tbody tr:hover{{background:{rgba(t["accent"], .07)}}}

/* ---------- Widgets Streamlit en verre ---------- */
[data-testid="stSidebar"]{{background:var(--verre-fort) !important;backdrop-filter:var(--flou);border-right:1px solid var(--border)}}
.stTabs [role="tablist"]{{gap:4px;padding:5px;border-radius:999px;background:var(--verre-fort);
  border:1px solid var(--border);backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);
  box-shadow:inset 0 1px 0 var(--reflet);position:sticky;top:.5rem;z-index:50;overflow-x:auto}}
.stTabs [role="tab"]{{min-height:44px;padding:0 16px;border-radius:999px;color:var(--muted);
  white-space:nowrap;background:transparent;transition:background-color .3s var(--ease), color .3s}}
.stTabs [role="tab"] p{{font-weight:600;font-size:13px}}
.stTabs [role="tab"]:hover{{color:var(--text);background:{rgba(t["accent"], .08)}}}
.stTabs [role="tab"][aria-selected="true"]{{background:var(--accent) !important}}
.stTabs [role="tab"][aria-selected="true"] p{{color:var(--ontint) !important}}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none}}
.stTabs [role="tabpanel"]{{animation:apparait .3s var(--ease) both;padding-top:1rem}}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{{min-height:44px;border-radius:999px;
  border:1px solid var(--accent);color:var(--accent);background:var(--verre);backdrop-filter:var(--flou);
  transition:transform .2s var(--ease), background-color .2s}}
.stButton>button p,.stFormSubmitButton>button p,.stDownloadButton>button p{{font-weight:600;font-size:13px}}
.stButton>button:hover,.stFormSubmitButton>button:hover,.stDownloadButton>button:hover{{transform:translateY(-1px);
  background:{rgba(t["accent"], .1)};color:var(--accent);border-color:var(--accent)}}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"],.stFormSubmitButton>button[kind="primaryFormSubmit"]{{background:var(--accent);color:var(--ontint);
  border-color:var(--accent)}}
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{{background:var(--accent);
  color:var(--ontint);filter:brightness(1.06)}}
[data-testid="stMetric"]{{background:var(--verre);border:1px solid var(--border);border-radius:12px;padding:14px 18px;
  backdrop-filter:var(--flou);box-shadow:inset 0 1px 0 var(--reflet);animation:apparait .3s var(--ease) both}}
[data-testid="stMetricValue"]{{font-family:var(--mono);font-weight:500;font-size:22px}}
[data-testid="stMetricLabel"] p{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}}
[data-testid="stPlotlyChart"],[data-testid="stForm"],[data-testid="stExpander"] details,[data-testid="stDataFrame"]{{
  background:var(--verre);border:1px solid var(--border);border-radius:12px;backdrop-filter:var(--flou);
  -webkit-backdrop-filter:var(--flou);box-shadow:var(--arete);padding:8px;animation:apparait .3s var(--ease) both}}
[data-testid="stForm"]{{position:relative;overflow:hidden;border-radius:18px;padding:18px 20px !important;
  box-shadow:{ombre}, var(--arete);transition:border-color .3s var(--ease)}}
[data-testid="stForm"]::before{{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;
  background:radial-gradient(420px circle at var(--mx,50%) var(--my,0%), var(--lueur), transparent 60%);transition:opacity .3s var(--ease)}}
[data-testid="stForm"]:hover::before,[data-testid="stForm"]:focus-within::before{{opacity:1}}
[data-testid="stForm"]:focus-within{{border-color:{rgba(t['accent'], .45)}}}
[data-testid="stForm"] [data-baseweb="input"]{{background:var(--verre) !important;backdrop-filter:blur(10px);transition:box-shadow .3s var(--ease)}}
[data-testid="stForm"] [data-baseweb="input"]:focus-within{{box-shadow:0 0 0 3px {rgba(t['accent'], .18)}}}
.bs-msg{{backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);box-shadow:var(--arete)}}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{{border-radius:8px !important}}
div[role="dialog"]{{background:var(--verre-fort) !important;backdrop-filter:blur(28px) saturate(170%) !important;
  border:1px solid var(--border);border-radius:16px !important}}

/* ---------- Bandeau de marché ---------- */
.marche{{display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:8px 16px;border-radius:999px;
  border:1px solid var(--border);background:var(--verre-fort);backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);
  box-shadow:inset 0 1px 0 var(--reflet);font-size:13px;margin-bottom:14px;animation:apparait .3s var(--ease) both}}
.marche .sep{{width:1px;height:16px;background:var(--border)}}
.direct{{display:flex;align-items:center;gap:8px 16px;flex-wrap:wrap;padding:8px 16px;border-radius:18px;font-size:13px;
  border:1px solid var(--border);background:var(--verre);backdrop-filter:var(--flou);-webkit-backdrop-filter:var(--flou);
  box-shadow:var(--arete);margin:-4px 0 14px}}
.direct .cot{{display:inline-flex;align-items:baseline;gap:6px;padding:3px 10px;border-radius:999px;border:1px solid transparent;
  transition:border-color .3s var(--ease),background .3s var(--ease)}}
.direct .cot:hover{{border-color:var(--border);background:var(--verre-fort)}}
.direct .cot .mono{{border-radius:4px;padding:0 2px}}
.direct .h{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
.direct .fin{{flex-basis:100%;font-size:11.5px}}
.direct .pt{{width:7px;height:7px;border-radius:50%;background:var(--muted);align-self:center;flex:none}}
.direct .pt.on{{background:var(--buy);box-shadow:0 0 0 3px {rgba(t["buy"], .18)}}}
.etat{{display:inline-flex;align-items:center;gap:7px;font-weight:600}}
.etat::before{{content:"";width:8px;height:8px;border-radius:50%;background:var(--c)}}
.demo{{border:1px solid var(--wait);color:var(--wait);border-radius:999px;padding:2px 10px;font-weight:600;font-size:12px}}
/* ---------- Mise à jour d'un cours : la couleur s'estompe en 600 ms ---------- */
.flash-up{{animation:flashup 1.2s ease-out}} .flash-down{{animation:flashdown 1.2s ease-out}}
@keyframes flashup{{from{{background:{rgba(t["buy"], .28)}}}to{{background:transparent}}}}
@keyframes flashdown{{from{{background:{rgba(t["sell"], .28)}}}to{{background:transparent}}}}
/* ---------- Actualités : survol ---------- */
.news{{border-radius:8px;transition:background-color .2s}} .news:hover{{background:{rgba(t["accent"], .06)}}}
.news .meta{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.src{{font-weight:600;color:var(--text);font-size:11px}}
/* ---------- Écran d'erreur ---------- */
.erreur{{max-width:640px;margin:8vh auto 0;text-align:center}}
{"" if animations else "*{animation:none !important;transition:none !important} body{--bs-calme:1}"}
@media (prefers-reduced-motion: reduce){{*{{animation:none !important;transition:none !important}}}}

/* ---------- Téléphone et tablette ---------- */
[data-testid="stMetricValue"],.valeur .mono,.direct .cot{{white-space:nowrap}}
@media (max-width: 900px){{
  [data-testid="stMainBlockContainer"]{{padding-left:1rem !important;padding-right:1rem !important}}
  .titre-xl{{font-size:34px;line-height:40px}}
  .direct{{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;border-radius:14px}}
  .direct::-webkit-scrollbar{{display:none}}
  .direct .cot{{flex:none}}
  .direct .etat,.marche .etat{{flex:none;white-space:nowrap}}
  .marche{{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;border-radius:14px}}
  .marche>span{{flex:none}}
  .stTabs [role="tablist"]{{overflow-x:auto;scrollbar-width:none}}
  .glass:not(.plat){{transform:none !important}}
}}
@media (max-width: 640px){{
  [data-testid="stMainBlockContainer"]{{padding-top:1.4rem !important}}
  .bs-zone{{flex-direction:column;align-items:center;text-align:center;gap:.8rem}}
  .bs-zone .bs-rose{{width:150px;height:150px}}
  .bs-msg{{min-height:0;max-width:none}}
  .accroche .atout{{display:none}}
  .titre-xl{{font-size:30px;line-height:36px}}
  .entete-app .sous{{font-size:12px}}
  #bs-calcul{{right:12px;top:10px}}
}}
@media (hover: none){{ .glass::before,[data-testid="stForm"]::before{{display:none}} }}
</style>
"""


# Effets JavaScript : reflet du verre qui suit le curseur, chiffres qui glissent (200 ms).
FX_JS = r"""
<script>
(function(){
  const P = window.parent, D = P.document;
  if (P.__boussoleFx) { P.__boussoleFx(); return; }
  const reduit = P.matchMedia('(prefers-reduced-motion: reduce)').matches;
  /* ---- Installation (écran d'accueil / bureau) : manifeste et icônes ---- */
  (function(){
    const H = D.head; if (H.querySelector('link[rel="manifest"]')) return;
    const ajoute = (tag, attrs) => { const el = D.createElement(tag); for (const k in attrs) el.setAttribute(k, attrs[k]); H.appendChild(el); };
    ajoute('link', {rel: 'manifest', href: '/app/static/manifest.webmanifest'});
    ajoute('link', {rel: 'apple-touch-icon', href: '/app/static/apple-touch-icon.png'});
    ajoute('meta', {name: 'theme-color', content: '#0B1220'});
    ajoute('meta', {name: 'mobile-web-app-capable', content: 'yes'});
    ajoute('meta', {name: 'apple-mobile-web-app-capable', content: 'yes'});
    ajoute('meta', {name: 'apple-mobile-web-app-title', content: 'Boussole'});
    ajoute('meta', {name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent'});
  })();
  /* ---- Remplissage automatique : noms de champs reconnus par les navigateurs et gestionnaires de mots de passe ---- */
  const NOMS_CHAMPS = {'adresse e-mail': 'email', 'mot de passe': 'password', 'confirmer le mot de passe': 'password-confirm',
                       'prénom': 'given-name', 'nom': 'family-name'};
  function champs(){
    D.querySelectorAll('[data-testid="stForm"] input').forEach(i => {
      const n = NOMS_CHAMPS[(i.getAttribute('aria-label') || '').toLowerCase()]; if (n && i.name !== n) { i.name = n; i.id = i.id || 'bs-' + n; }
    });
  }
  /* Un champ rempli par le navigateur n'envoie pas toujours d'événement : on le signale avant l'envoi du formulaire. */
  const setter = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
  function synchroniser(form){
    form.querySelectorAll('input').forEach(i => {
      if (!i.value || i.type === 'checkbox') return; const v = i.value;
      setter.call(i, v + ' '); i.dispatchEvent(new P.Event('input', {bubbles: true}));
      setter.call(i, v); i.dispatchEvent(new P.Event('input', {bubbles: true}));
    });
  }
  D.addEventListener('pointerdown', ev => {
    const b = ev.target.closest && ev.target.closest('.stFormSubmitButton button'); if (!b) return;
    const f = b.closest('[data-testid="stForm"]'); if (f) synchroniser(f);
  }, true);
  D.addEventListener('keydown', ev => {
    if (ev.key !== 'Enter') return; const f = ev.target.closest && ev.target.closest('[data-testid="stForm"]'); if (f) synchroniser(f);
  }, true);
  function chiffres(){
    /* React réutilise les éléments d'un rendu à l'autre : on suit la valeur affichée, pas l'élément. */
    D.querySelectorAll('[data-to]').forEach(el => {
      if (el.dataset.vu === el.dataset.to) return;
      el.dataset.vu = el.dataset.to; if (reduit) return;
      el.classList.remove('flash-up','flash-down'); void el.offsetWidth;
      const de = parseFloat(el.dataset.from || '0'), a = parseFloat(el.dataset.to), dec = +(el.dataset.dec||0),
            suf = el.dataset.suf || '', signe = el.dataset.signe === '1', t0 = performance.now(), dur = 200;
      if (de === a) return;
      el.classList.add(a > de ? 'flash-up' : 'flash-down');
      const f = v => { const s = Math.abs(v).toLocaleString('fr-FR',{minimumFractionDigits:dec,maximumFractionDigits:dec});
        return (v < 0 ? '−' : (signe && v > 0 ? '+' : '')) + s + suf; };
      (function pas(t){ const k = Math.min(1,(t-t0)/dur), e = 1-Math.pow(1-k,3);
        const n = el.firstChild; if (n && n.nodeType === 3) n.nodeValue = f(de + (a-de)*e); if (k<1) P.requestAnimationFrame(pas); })(t0);
    });
  }
  D.addEventListener('pointermove', ev => {
    const g = ev.target.closest && ev.target.closest('.glass,[data-testid="stForm"]'); if (!g) return;
    const r = g.getBoundingClientRect();
    g.style.setProperty('--mx', (ev.clientX-r.left)+'px'); g.style.setProperty('--my', (ev.clientY-r.top)+'px');
  }, {passive:true});
  /* ---- Cartes : légère inclinaison sous le curseur (suivie, jamais en boucle) ---- */
  D.addEventListener('pointermove', ev => {
    if (reduit || D.body.classList.contains('bs-calme')) return;
    const g = ev.target.closest && ev.target.closest('.glass:not(.plat)'); if (!g) return;
    const r = g.getBoundingClientRect(), x = (ev.clientX-r.left)/r.width-.5, y = (ev.clientY-r.top)/r.height-.5;
    g.style.setProperty('--rx', (-y*0.8).toFixed(2)+'deg'); g.style.setProperty('--ry', (x*0.8).toFixed(2)+'deg');
  }, {passive:true});
  D.addEventListener('pointerout', ev => {
    const g = ev.target.closest && ev.target.closest('.glass:not(.plat)');
    if (g && !g.contains(ev.relatedTarget)) { g.style.removeProperty('--rx'); g.style.removeProperty('--ry'); }
  }, {passive:true});
  /* ---- Boutons : onde au clic ---- */
  D.addEventListener('pointerdown', ev => {
    if (reduit) return;
    const b = ev.target.closest && ev.target.closest('.stButton>button,.stFormSubmitButton>button'); if (!b || b.disabled) return;
    const r = b.getBoundingClientRect(), d = Math.max(r.width, r.height)*2.2, o = D.createElement('span');
    o.className = 'ondee'; o.style.width = o.style.height = d+'px';
    o.style.left = (ev.clientX-r.left-d/2)+'px'; o.style.top = (ev.clientY-r.top-d/2)+'px';
    b.appendChild(o); setTimeout(() => o.remove(), 600);
  }, {passive:true});
  /* ---- Logo de l'en-tête : l'aiguille indique l'onglet ouvert (un cap par onglet) ---- */
  function capLogo(i, n){
    const lg = D.querySelector('.entete-app .logo'); if (!lg || i < 0) return;
    lg.classList.add('vive'); const a = lg.querySelector('.aiguille');
    let cible = i*360/n, cur = parseFloat(a.dataset.cap || '0');
    let d = ((cible-cur)%360+540)%360-180; cur += d; a.dataset.cap = cur;
    a.style.transform = 'rotate('+cur+'deg)';
  }
  function ongletActif(){
    const t = [...D.querySelectorAll('[role="tab"]')]; return [t.findIndex(x => x.getAttribute('aria-selected')==='true'), t.length];
  }
  D.addEventListener('pointerover', ev => {
    const tab = ev.target.closest && ev.target.closest('[role="tab"]'); if (!tab) return;
    const t = [...D.querySelectorAll('[role="tab"]')]; capLogo(t.indexOf(tab), t.length);
  }, {passive:true});
  D.addEventListener('pointerout', ev => {
    const tab = ev.target.closest && ev.target.closest('[role="tab"]'); if (!tab) return;
    setTimeout(() => capLogo(...ongletActif()), 30);
  }, {passive:true});
  D.addEventListener('click', ev => {
    if (ev.target.closest && ev.target.closest('[role="tab"]')) setTimeout(() => capLogo(...ongletActif()), 60);
  });

  /* ---- Page de connexion : la boussole vivante ---- */
  function rose(){
    const svg = D.getElementById('bs-rose'); if (!svg || svg.dataset.ok) return; svg.dataset.ok = '1';
    const ag = D.getElementById('bs-aiguille'), msg = D.getElementById('bs-msg'), rec = D.getElementById('bs-record');
    const vivant = () => svg.isConnected;
    let angle = -140, verrou = null, jeu = null, fige = 0;
    const dire = (txt, cls) => { msg.textContent = txt; msg.className = 'bs-msg bs-pop ' + (cls || '');
      void msg.offsetWidth; };
    const etat = c => { svg.classList.remove('ok','err','jeu'); if (c) svg.classList.add(c); };
    const tourner = (a, ms) => { const d = ((a-angle)%360+540)%360-180; angle += d;
      ag.style.transition = 'transform '+(ms||450)+'ms var(--ressort)'; ag.style.transform = 'rotate('+angle+'deg)'; };
    const vers = (x, y) => { const r = svg.getBoundingClientRect();
      return Math.atan2(x-(r.left+r.width/2), (r.top+r.height/2)-y)*180/Math.PI; };
    const pulse = () => { svg.classList.remove('pulse'); void svg.getBoundingClientRect(); svg.classList.add('pulse'); };
    const record = () => { const b = P.localStorage.getItem('boussole-record');
      rec.textContent = b !== null ? 'Votre record : '+b+'° du nord' : 'Pas encore de record'; };
    record();
    ag.style.transform = 'rotate(-140deg)';
    setTimeout(() => { tourner(0, 900); pulse(); }, 250);           // entrée : l'aiguille trouve le nord
    let raf = 0;
    D.addEventListener('pointermove', ev => {
      if (!vivant() || verrou || jeu || Date.now() < fige || reduit) return;
      if (raf) return; raf = P.requestAnimationFrame(() => { raf = 0; tourner(vers(ev.clientX, ev.clientY)); });
    }, {passive:true});
    const libelle = el => (el.getAttribute('aria-label') || '').toLowerCase();
    const champ = nom => [...D.querySelectorAll('input')].find(i => libelle(i) === nom);
    D.addEventListener('focusin', ev => {
      const el = ev.target; if (!vivant() || jeu || !el.matches || !el.matches('input')) return;
      if (Date.now() < fige) { verrou = el; return; }
      const r = el.getBoundingClientRect(); verrou = el; etat(''); tourner(vers(r.left+40, r.top+r.height/2));
      const l = libelle(el);
      if (l.includes('e-mail')) dire("Cap sur votre adresse e-mail : elle sert d'identifiant sur cet ordinateur.");
      else if (l === 'mot de passe') dire(el.autocomplete === 'new-password'
          ? 'Choisissez un mot de passe : 8 caractères, une lettre et un chiffre. La boussole compte avec vous.'
          : 'Votre mot de passe reste chiffré sur cet ordinateur.');
      else if (l.includes('confirmer')) dire('Retapez le mot de passe pour le confirmer.');
      else if (l === 'prénom') dire('Enchanté ! Votre prénom, pour vous saluer.');
      else if (l === 'nom') dire('Et votre nom de famille.');
    });
    D.addEventListener('focusout', ev => {
      if (!vivant() || ev.target !== verrou) return; verrou = null;
      const el = ev.target, l = libelle(el);
      if (l.includes('e-mail') && el.value && !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(el.value.trim())) {
        etat('err'); tourner(180); svg.classList.remove('secoue'); void svg.getBoundingClientRect(); svg.classList.add('secoue');
        dire("Cette adresse e-mail semble incomplète (exemple : vous@exemple.fr).", 'err'); fige = Date.now()+1600;
      }
    });
    D.addEventListener('input', ev => {
      const el = ev.target; if (!vivant() || !el.matches || !el.matches('input')) return;
      const l = libelle(el);
      if (l === 'mot de passe' && el.autocomplete === 'new-password') {
        const v = el.value, c = [v.length >= 8, /[A-Za-zÀ-ÿ]/.test(v), /\d/.test(v)], n = c.filter(Boolean).length;
        svg.classList.toggle('mdp', v.length > 0);
        svg.querySelectorAll('.bs-seg').forEach((s, i) => { s.classList.toggle('on', i < n); s.classList.toggle('tout', n === 3); });
        tourner(-60 + n*40, 450);
        if (n === 3) { etat('ok'); tourner(0); dire('Mot de passe solide : plein nord !', 'ok'); }
        else { etat(''); const m = []; if (!c[0]) m.push((8 - v.length)+' caractère(s)'); if (!c[1]) m.push('une lettre');
          if (!c[2]) m.push('un chiffre'); dire('Encore '+m.join(', ')+'.'); }
      } else if (l.includes('confirmer')) {
        const p = champ('mot de passe');
        if (p && el.value && el.value === p.value) { etat('ok'); tourner(0); pulse(); dire('Les deux mots de passe correspondent.', 'ok'); }
        else if (p && el.value.length >= p.value.length && el.value) { etat('err'); dire('Les deux mots de passe diffèrent.', 'err'); }
        else { etat(''); }
      }
    });
    /* Jeu « Trouvez le nord » : un clic lance l'aiguille, un second l'arrête — au plus près du nord. */
    const stop = auto => {
      const n = ((angle % 360) + 360) % 360, ecart = Math.round(Math.min(n, 360 - n)); const j = jeu; jeu = null;
      if (!j) return;
      let txt, c = 'ok';
      if (auto) { txt = "L'aiguille s'est arrêtée seule. Cliquez sur la boussole pour rejouer."; c = ''; }
      else if (ecart <= 3) txt = 'Plein nord ! Écart de '+ecart+'° : cap parfait.';
      else if (ecart <= 12) txt = 'Excellent cap : '+ecart+'° du nord.';
      else if (ecart <= 35) txt = 'Pas mal : '+ecart+'° du nord. Encore un essai ?';
      else { txt = ecart+'° du nord… la boussole vous attend pour un autre essai.'; c = 'err'; }
      if (!auto) { const b = P.localStorage.getItem('boussole-record');
        if (b === null || ecart < +b) { P.localStorage.setItem('boussole-record', ecart); txt += ' Nouveau record !'; } record(); }
      etat(c === 'err' ? 'err' : c); dire(txt, c); pulse(); fige = Date.now() + 2200;
      setTimeout(() => { if (!jeu) { etat(''); tourner(Math.round(angle/360)*360, 700); } }, 1400);
    };
    svg.addEventListener('click', () => {
      if (reduit) return;
      if (jeu) { stop(false); return; }
      etat('jeu'); dire("Trouvez le nord : cliquez de nouveau pour arrêter l'aiguille !", 'jeu');
      jeu = { t0: performance.now(), last: performance.now(), v: 420 + Math.random()*360 };
      ag.style.transition = 'none';
      const pas = t => { if (!jeu) return; const dt = (t - jeu.last)/1000; jeu.last = t;
        angle += jeu.v*dt; ag.style.transform = 'rotate('+angle+'deg)';
        if (t - jeu.t0 > 7000) stop(true); else P.requestAnimationFrame(pas); };
      P.requestAnimationFrame(pas);
    });
    /* Erreur renvoyée par le serveur (identifiants, doublon…) : l'aiguille plonge au sud et tremble. */
    new P.MutationObserver(() => {
      if (!vivant()) return;
      D.querySelectorAll('[data-testid="stAlertContentError"]:not([data-vu])').forEach(a => {
        a.setAttribute('data-vu', '1'); etat('err'); tourner(180);
        svg.classList.remove('secoue'); void svg.getBoundingClientRect(); svg.classList.add('secoue');
        dire(a.textContent.trim(), 'err'); fige = Date.now() + 2000;
      });
    }).observe(D.body, {childList:true, subtree:true});
  }

  /* ---- Chargement et transitions de page ---- */
  const calme = () => reduit || getComputedStyle(D.body).getPropertyValue('--bs-calme').trim() === '1';
  const CAPS = {connexion: 0, profil: 120, portefeuille: 240, app: 360};
  function cadran(){
    let tk = '';
    for (let i = 0; i < 48; i++) { const a = i*7.5*Math.PI/180, l = i%6===0, r1 = 46-(l?8:4);
      tk += '<line class="'+(l?'l':'')+'" style="animation-delay:'+(i*8)+'ms" x1="'+(50+r1*Math.sin(a)).toFixed(2)+'" y1="'+(50-r1*Math.cos(a)).toFixed(2)+
            '" x2="'+(50+44.5*Math.sin(a)).toFixed(2)+'" y2="'+(50-44.5*Math.cos(a)).toFixed(2)+'" stroke-width="'+(l?2:1)+'"/>'; }
    return '<svg width="112" height="112" viewBox="0 0 100 100" aria-hidden="true"><circle class="cad" cx="50" cy="50" r="46"/><g class="tk" stroke-linecap="round">'+tk+
      '</g><g class="ag"><polygon points="50,17.8 56.4,50 43.6,50" fill="var(--accent)"/><polygon points="50,82.2 56.4,50 43.6,50" fill="var(--muted)"/></g>'+
      '<circle cx="50" cy="50" r="2.5" fill="var(--text)"/></svg>';
  }
  function ecran(premier, de, vers, texte){
    let o = D.getElementById('bs-charge'); if (o) o.remove();
    o = D.createElement('div'); o.id = 'bs-charge'; if (!premier) o.className = 'leger';
    o.innerHTML = '<div class="lentille">' + cadran() + '</div><div class="nom">Boussole</div><div class="lg">'+texte+'</div>';
    D.body.appendChild(o);
    const ag = o.querySelector('.ag'), lg = o.querySelector('.lg');
    ag.style.setProperty('--de', de+'deg'); ag.style.setProperty('--dur', premier ? '1.05s' : '.6s');
    void ag.getBoundingClientRect();
    P.requestAnimationFrame(() => { ag.style.transform = 'rotate('+vers+'deg)'; });
    return {o, lg};
  }
  function partir(o, delai){
    setTimeout(() => { o.classList.add('part');
      const m = D.querySelector('[data-testid="stMainBlockContainer"]');
      if (m) { m.classList.remove('bs-entree'); void m.offsetWidth; m.classList.add('bs-entree'); }
      setTimeout(() => o.remove(), 420); }, delai);
  }
  let pageVue = null;
  /* Ouverture : l'aiguille tourne tant que Streamlit calcule, puis se cale au nord et le voile s'efface. */
  const tDebut = performance.now();
  function ouverture(){
    const o = D.querySelector('#bs-charge.premier'); if (!o || o.dataset.fin) return;
    const app = D.querySelector('.stApp'), etat = app && app.getAttribute('data-test-script-state');
    if (etat === 'running' || etat === 'initial' || !D.querySelector('.bs-page')) {
      clearTimeout(P.__bsOuv); P.__bsOuv = setTimeout(ouverture, 250); return; }
    o.dataset.fin = '1';
    setTimeout(() => {
      const ag = o.querySelector('.ag'), m = getComputedStyle(ag).transform;
      let a = 0; if (m && m !== 'none') { const v = m.match(/matrix\(([^)]+)\)/); if (v) { const [c0, s0] = v[1].split(',').map(parseFloat); a = Math.atan2(s0, c0)*180/Math.PI; } }
      ag.style.transform = 'rotate('+a+'deg)'; o.classList.add('fini'); void ag.getBoundingClientRect();
      ag.style.transform = 'rotate('+(a > 0 ? 360 : 0)+'deg)';
      setTimeout(() => { o.classList.add('part'); setTimeout(() => { o.style.display = 'none'; }, 420); }, 650);
    }, Math.max(0, 700 - (performance.now() - tDebut)));
  }
  /* Onglet actif mémorisé pour l'onglet du navigateur : un rechargement ramène au même endroit. */
  function onglets(){
    const t = [...D.querySelectorAll('[role="tab"]')]; if (!t.length) return;
    const voulu = +(P.sessionStorage.getItem('bs-onglet') || 0);
    if (!P.__bsOngletRestaure) { P.__bsOngletRestaure = true;
      if (voulu > 0 && t[voulu] && t[voulu].getAttribute('aria-selected') !== 'true') t[voulu].click(); return; }
    const i = t.findIndex(x => x.getAttribute('aria-selected') === 'true'); if (i >= 0) P.sessionStorage.setItem('bs-onglet', i);
  }
  const TEXTES = {connexion: 'Connexion', profil: 'Votre profil', portefeuille: 'Votre portefeuille', app: 'Votre tableau de bord'};
  function pages(){
    const m = D.querySelector('.bs-page'); if (!m) return;
    const p = m.dataset.page; if (p === pageVue) return;
    const avant = pageVue; pageVue = p;
    if (avant === null) { const m2 = D.querySelector('[data-testid="stMainBlockContainer"]');
      if (m2 && !calme()) m2.classList.add('bs-entree'); return; }
    if (calme()) return;
    const {o} = ecran(false, CAPS[avant] ?? 0, CAPS[p] ?? 0, TEXTES[p] || '');
    partir(o, 640);
  }
  /* Calcul long (cours, actualités) : une pastille discrète, l'aiguille cherche puis se fixe. */
  const pastille = D.createElement('div'); pastille.id = 'bs-calcul';
  pastille.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="none" stroke="var(--text)" stroke-width="1.2"/>'+
    '<g class="ag"><polygon points="12,4.5 14,12 10,12" fill="var(--accent)"/><polygon points="12,19.5 14,12 10,12" fill="var(--muted)"/></g></svg><span>Mise à jour…</span>';
  D.body.appendChild(pastille);
  let tCalcul = 0;
  function calcul(){
    const app = D.querySelector('.stApp');
    const enCours = !!app && app.getAttribute('data-test-script-state') === 'running' && !D.querySelector('#bs-charge.premier:not(.part)');
    if (enCours && !tCalcul) tCalcul = setTimeout(() => { if (!calme()) pastille.classList.add('vu'); }, 600);
    if (!enCours) { clearTimeout(tCalcul); tCalcul = 0; pastille.classList.remove('vu'); }
  }
  /* Le grand cadran du fond suit le curseur de quelques pixels : le verre a de la profondeur. */
  let rafP = 0;
  D.addEventListener('pointermove', ev => {
    if (calme() || rafP) return;
    rafP = P.requestAnimationFrame(() => { rafP = 0; const x = ev.clientX/P.innerWidth-.5, y = ev.clientY/P.innerHeight-.5;
      const st = D.documentElement.style; st.setProperty('--px', (-x*18).toFixed(1)+'px');
      st.setProperty('--py', (-y*14).toFixed(1)+'px'); st.setProperty('--prot', (x*8).toFixed(1)+'deg'); });
  }, {passive:true});
  /* Écran étroit (tablette en portrait, téléphone) : la barre latérale se replie d'elle-même une fois. */
  function barre(){
    if (P.__bsBarre || P.innerWidth >= 1100) return;
    const sb = D.querySelector('[data-testid="stSidebar"]'); if (!sb) return;
    P.__bsBarre = true;
    if (sb.getAttribute('data-collapsed') === 'false') {
      const b = sb.querySelector('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarHeader"] button, '
                                 + '[data-testid="stBaseButton-headerNoPadding"]');
      if (b) b.click();
    }
  }
  function tout(){ barre(); chiffres(); rose(); capLogo(...ongletActif()); pages(); calcul(); ouverture(); onglets(); champs(); }
  new P.MutationObserver(() => { if (!P.__bsT) P.__bsT = setTimeout(() => { P.__bsT = 0; tout(); }, 60); })
    .observe(D.body, {childList:true, subtree:true, attributes:true, attributeFilter:['data-test-script-state','aria-selected']});
  P.__boussoleFx = tout; tout();
})();
</script>
"""


def chargement() -> str:
    """Écran d'ouverture : l'aiguille part de −250°, trouve le nord (ressort), puis le voile s'efface.
    Rendu dès le premier affichage, en CSS seul, une seule fois par session."""
    tk = ""
    for i in range(48):
        a, l = math.radians(i * 7.5), i % 6 == 0
        r1 = 46 - (8 if l else 4)
        tk += (f'<line class="{"l" if l else ""}" style="animation-delay:{i * 8}ms" x1="{50 + r1 * math.sin(a):.2f}" '
               f'y1="{50 - r1 * math.cos(a):.2f}" x2="{50 + 44.5 * math.sin(a):.2f}" y2="{50 - 44.5 * math.cos(a):.2f}" '
               f'stroke-width="{2 if l else 1}"/>')
    return ('<div id="bs-charge" class="premier" aria-hidden="true"><div class="lentille">'
            '<svg width="112" height="112" viewBox="0 0 100 100"><circle class="cad" cx="50" cy="50" r="46"/>'
            f'<g class="tk" stroke-linecap="round">{tk}</g><g class="ag">'
            '<polygon points="50,17.8 56.4,50 43.6,50" fill="var(--accent)"/>'
            '<polygon points="50,82.2 56.4,50 43.6,50" fill="var(--muted)"/></g>'
            '<circle cx="50" cy="50" r="2.5" fill="var(--text)"/></svg></div><div class="nom">Boussole</div>'
            '<div class="lg"><span class="a">On s\'oriente…</span><span class="b">Cap au nord</span></div></div>')


def injecter_style(t: dict, animations: bool = True, ouverture: bool = False) -> None:
    TK.clear()
    TK.update(t)
    st.markdown(css(t, animations) + (chargement() if ouverture and animations else ""), unsafe_allow_html=True)
    components.html(FX_JS, height=0)


# --------------------------------------------------------------------------- #
# Composants HTML
# --------------------------------------------------------------------------- #
def chiffre(v: float, dec: int = 0, suffixe: str = "", signe: bool = False, depuis: float | None = None) -> str:
    """Chiffre en chasse fixe ; glisse (200 ms) depuis sa valeur précédente quand elle change."""
    final = nombre(v, dec, signe) + suffixe
    de = v if depuis is None else depuis
    return (f'<span class="mono" data-from="{de:.6f}" data-to="{v:.6f}" data-dec="{dec}" '
            f'data-suf="{e(suffixe)}" data-signe="{1 if signe else 0}">{final}</span>')


def carte(contenu: str, delai: int = 0, style: str = "", plat: bool = False) -> str:
    return f'<div class="glass d{delai}{" plat" if plat else ""}" style="{style}">{contenu}</div>'


def kpi(label: str, valeur_html: str, sous: str = "", delai: int = 1) -> str:
    return carte(f'<div class="label">{e(label)}</div><div class="valeur">{valeur_html}</div>'
                 f'<div class="petit">{sous}</div>', delai)


def pastille(code: int, grand: bool = False) -> str:
    return (f'<span class="pill {ROLES[code]}{" grand" if grand else ""}" role="status" '
            f'aria-label="Recommandation : {MOTS[code].lower()}"><span class="f">{FORMES[code]}</span>'
            f'{MOTS[code]}</span>')


def entete(surtitre: str, titre: str, sous: str = "") -> None:
    st.markdown(f'<div class="surtitre">{e(surtitre)}</div><div class="titre">{e(titre)}</div><div class="trait"></div>'
                + (f'<div class="petit" style="margin:-.4rem 0 1rem">{sous}</div>' if sous else ""),
                unsafe_allow_html=True)


def section(titre: str) -> None:
    st.markdown(f'<div class="section-t">{e(titre)}</div><div class="trait" style="width:40px"></div>',
                unsafe_allow_html=True)


def html_bloc(contenu: str) -> None:
    st.markdown(contenu, unsafe_allow_html=True)


def avertissement() -> str:
    return f'<div class="avert">{e(AVERTISSEMENT)}</div>'


def risque(niveau: str, message: str) -> str:
    titre, role = {"normal": ("Risque maîtrisé", "accent"), "alerte": ("Risque élevé", "wait"),
                   "critique": ("Risque très élevé", "sell"), "objectif": ("Objectif atteint", "buy")}[niveau]
    return f'<div class="risque" style="--c:var(--{role})"><b>{titre}</b><span>{e(message)}</span></div>'


def barre(part: float, role: str = "accent") -> str:
    w = max(0.0, min(1.0, part)) * 100
    return f'<div class="piste"><i style="left:0;width:{w:.1f}%;--c:var(--{role});transform-origin:left"></i></div>'


def barre_centree(v: int) -> str:
    """Barre de −100 à +100, zéro au centre : vert à droite, rouge à gauche."""
    w = abs(v) / 2
    role = "buy" if v > 0 else "sell" if v < 0 else "muted"
    pos = f"left:50%;width:{w}%;transform-origin:left" if v >= 0 else f"right:50%;width:{w}%;transform-origin:right"
    return f'<div class="piste"><i style="{pos};--c:var(--{role})"></i></div>'


def pilier(nom: str, v: int) -> str:
    return (f'<div class="pilier"><span>{e(nom)}</span>{barre_centree(v)}'
            f'<span class="mono {classe(v)}" style="text-align:right">{nombre(v, 0, True)}</span></div>')


def logo(taille: int = 40, angle: float = 35, hors_ligne: bool = False) -> str:
    """Logo de la charte : cadran fin, 48 graduations (longue tous les 45°), aiguille
    (pointe = accent, queue = texte secondaire). R = 46 ; aiguille 0,70 R × 0,28 R ;
    trait 0,045 R ; pivot 0,05 R ; repos à 35°. Sous 24 px : version sans graduations."""
    R = 46.0
    traits = ""
    if taille >= 24:
        for i in range(48):
            a = math.radians(i * 7.5)
            r1 = R - (8 if i % 6 == 0 else 4)
            traits += (f'<line x1="{50 + r1 * math.sin(a):.2f}" y1="{50 - r1 * math.cos(a):.2f}" '
                       f'x2="{50 + (R - 1.5) * math.sin(a):.2f}" y2="{50 - (R - 1.5) * math.cos(a):.2f}" '
                       f'stroke-width="{2 if i % 6 == 0 else 1}"/>')
    L, W = .70 * R, .28 * R / 2
    pointe = "var(--muted)" if hors_ligne else "var(--accent)"
    return (f'<svg class="logo" width="{taille}" height="{taille}" viewBox="0 0 100 100" role="img" '
            f'aria-label="Boussole"><g stroke="var(--text)" stroke-linecap="round"><circle cx="50" cy="50" r="{R}" '
            f'fill="none" stroke-width="{.045 * R:.2f}"/>{traits}</g>'
            f'<g class="aiguille" style="--a0:35deg;--a:{angle:.1f}deg">'
            f'<polygon points="50,{50 - L:.1f} {50 + W:.1f},50 {50 - W:.1f},50" fill="{pointe}"/>'
            f'<polygon points="50,{50 + L:.1f} {50 + W:.1f},50 {50 - W:.1f},50" fill="var(--muted)"/></g>'
            f'<circle cx="50" cy="50" r="2.5" fill="var(--text)"/></svg>')


def jauge(code: int, score: int, confiance: int, stop: str, hors_ligne: str | None = None,
          largeur: int = 260) -> str:
    """Jauge de décision : Vendre à gauche, Attendre en haut, Acheter à droite."""
    def arc(d0, d1):
        a0, a1 = math.radians(d0), math.radians(d1)
        return (f"M{100 + 80 * math.sin(a0):.2f},{100 - 80 * math.cos(a0):.2f} "
                f"A80,80 0 0 1 {100 + 80 * math.sin(a1):.2f},{100 - 80 * math.cos(a1):.2f}")
    b = 33.5 * .9   # frontières de zones à ±33,5 points
    zones = (f'<path d="{arc(-90, -b - 1.2)}" stroke="var(--sell)"/><path d="{arc(-b + 1.2, b - 1.2)}" '
             f'stroke="var(--wait)"/><path d="{arc(b + 1.2, 90)}" stroke="var(--buy)"/>')
    grad = ""
    for v in range(-100, 101, 10):
        a = math.radians(v * .9)
        r0, r1 = 64, (72 if v % 50 == 0 else 68)
        grad += (f'<line x1="{100 + r0 * math.sin(a):.1f}" y1="{100 - r0 * math.cos(a):.1f}" '
                 f'x2="{100 + r1 * math.sin(a):.1f}" y2="{100 - r1 * math.cos(a):.1f}"/>')
    couleur = "var(--muted)" if hors_ligne else "var(--text)"
    role = "muted" if hors_ligne else ROLES[code]
    angle = score * .9
    pied = f'<div class="legende">Hors ligne · dernière mise à jour {e(hors_ligne)}</div>' if hors_ligne else ""
    return f"""<div class="jauge" style="text-align:center" role="img"
      aria-label="Recommandation : {MOTS[code].lower()}. Score {score:+d}. Confiance {confiance} pour cent.">
      <svg viewBox="0 0 200 112" width="100%" style="max-width:{largeur}px;display:block;margin:auto">
        <g fill="none" stroke-width="11">{zones}</g>
        <g stroke="var(--muted)" stroke-width="1">{grad}</g>
        <g class="aiguille" style="--a0:{angle - 35:.1f}deg;--a:{angle:.1f}deg">
          <polygon points="100,36 105.5,100 100,107 94.5,100" fill="{couleur}"/></g>
        <circle cx="100" cy="100" r="5.5" fill="var(--surface)" stroke="{couleur}" stroke-width="2.5"/>
      </svg>
      <div class="mot" style="color:var(--{role})">{MOTS[code]}</div>
      <div class="mono" style="font-size:16px;line-height:20px;margin-top:.15rem">Score {nombre(score, 0, True)}</div>
      <div class="petit">Confiance {confiance}&#8239;%</div>
      <div style="max-width:200px;margin:.5rem auto">{barre(confiance / 100, role)}</div>
      <div class="legende">{e(stop)}</div>{pied}</div>"""


def sparkline(valeurs, role: str = "accent", l: int = 220, h: int = 40) -> str:
    v = np.asarray(valeurs, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return ""
    lo, hi = v.min(), v.max()
    span = (hi - lo) or 1
    pts = [(i * l / (len(v) - 1), h - 3 - (x - lo) / span * (h - 6)) for i, x in enumerate(v)]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"          # spline (Catmull-Rom → Bézier)
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    gid = f"s{abs(hash((role, len(v), float(v[-1]), float(v[0])))) % 10 ** 8}"
    return (f'<svg class="spark" viewBox="0 0 {l} {h}" width="100%" height="{h}" preserveAspectRatio="none">'
            f'<defs><linearGradient id="{gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" '
            f'stop-color="var(--{role})" stop-opacity=".13"/><stop offset="1" stop-color="var(--{role})" '
            f'stop-opacity="0"/></linearGradient></defs><path d="{d} L{l},{h} L0,{h} Z" fill="url(#{gid})"/>'
            f'<path class="l" d="{d}" stroke="var(--{role})" vector-effect="non-scaling-stroke"/></svg>')


# --------------------------------------------------------------------------- #
# Plotly
# --------------------------------------------------------------------------- #
def style_fig(fig: go.Figure, hauteur: int = 380, legende: bool = True) -> go.Figure:
    t = TK
    fig.update_layout(
        height=hauteur, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=t["text"], size=12),
        margin=dict(l=8, r=8, t=40, b=8), hovermode="x unified", showlegend=legende,
        legend=dict(orientation="h", y=-.08, yanchor="top", x=0, bgcolor="rgba(0,0,0,0)",
                    font=dict(color=t["muted"], size=11)),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["border"],
                        font=dict(family="IBM Plex Mono, monospace", color=t["text"], size=12)),
        separators=", ",
    )
    # Titre toujours défini : sans texte, certaines versions de Plotly affichent « undefined ».
    titre = fig.layout.title.text if fig.layout.title and fig.layout.title.text else ""
    fig.update_layout(title=dict(text=titre, font=dict(family="Source Serif 4, Georgia, serif", size=17,
                                                       color=t["text"])),
                      margin=dict(l=8, r=8, t=40 if titre else 14, b=8))
    fig.update_xaxes(gridcolor=rgba(t["border"], .8), gridwidth=.5, zeroline=False, linecolor=t["border"],
                     tickfont=dict(color=t["muted"], size=11), showspikes=True, spikecolor=t["muted"],
                     spikethickness=1, spikedash="dot", tickformat="%d/%m/%y", hoverformat="%d/%m/%Y")
    fig.update_yaxes(gridcolor=rgba(t["border"], .8), gridwidth=.5, zeroline=False,
                     tickfont=dict(family="IBM Plex Mono, monospace", color=t["muted"], size=11))
    return fig


CSS_PLEINE_PAGE = ('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
                   '[data-testid="stExpandSidebarButton"]{display:none!important}'
                   '[data-testid="stMainBlockContainer"]{max-width:1180px;padding-top:3.2rem}</style>')

ETAPES = ["Votre compte", "Votre profil d'investisseur", "Votre portefeuille"]


def etapes(actuelle: int) -> str:
    """Indicateur de progression de l'inscription (0, 1 ou 2)."""
    morceaux = []
    for i, lib in enumerate(ETAPES):
        etat = "fait" if i < actuelle else "cours" if i == actuelle else ""
        morceaux.append(f'<span class="e {etat}"><span class="p">{"✓" if i < actuelle else i + 1}</span>{e(lib)}</span>')
    return '<div class="etapes">' + '<span class="l"></span>'.join(morceaux) + "</div>"


def atout(n: str, titre: str, texte: str) -> str:
    return f'<div class="atout"><span class="n">{e(n)}</span><div><b>{e(titre)}</b><span class="petit">{e(texte)}</span></div></div>'


def guide(texte_html: str) -> str:
    """Encadré d'aide « Comment lire cette page » (texte déjà échappé)."""
    return f'<div class="guide"><span class="i">i</span><div>{texte_html}</div></div>'


def premiers_pas(etapes_faites: list[tuple[str, bool]]) -> str:
    return '<div class="premiers">' + "".join(
        f'<div class="pas{" fait" if ok else ""}"><span class="c">{"✓" if ok else ""}</span><span>{lib}</span></div>'
        for lib, ok in etapes_faites) + "</div>"


def ecran(page: str) -> str:
    """Repère invisible : le JS joue la transition (l'aiguille tourne vers le cap de la page)."""
    return f'<div class="bs-page" data-page="{page}" hidden></div>'


# Intitulés des raisons, en langage courant (les identifiants internes ne sont jamais affichés).
RAISONS = {
    "EXG-F-12": ("Perte limitée", "sell"), "EXG-F-13": ("Objectif de gain atteint", "sell"),
    "EXG-F-14": ("Gains à protéger", "sell"), "EXG-F-15": ("Hausse qui s'essouffle", "sell"),
    "EXG-F-16": ("Entreprise solide", "buy"), "EXG-F-17": ("Tendance qui repart", "buy"),
    "EXG-F-18": ("Rebond", "buy"), "EXG-F-19": ("Liquidités insuffisantes", "wait"),
    "EXG-F-20": ("Pas de signal", "wait"), "EXG-F-21": ("Signaux contradictoires", "wait"),
    "EXG-F-22": ("Semaine difficile", "wait"), "EXG-F-23": ("Pertes de la semaine", "wait"),
    "EXG-F-24": ("Gains de la semaine", "sell"), "EXG-F-25": ("Sécurité d'abord", "muted"),
    "PROFIL": ("Votre profil", "wait"),
}


def raison(code: str, texte: str) -> str:
    titre, role = RAISONS.get(code, ("", "muted"))
    return (f'<div class="raison"><i class="puce" style="background:var(--{role})"></i>'
            f'<span>{f"<b>{e(titre)}</b> · " if titre else ""}{e(texte)}</span></div>')


def rose(taille: int = 210) -> str:
    """Boussole interactive de la page de connexion (cadran, points cardinaux, jauge du mot de passe)."""
    c, R = 100, 92
    ticks = ""
    for i in range(72):
        a = math.radians(i * 5)
        long_ = i % 9 == 0
        r1 = R - (11 if long_ else 5)
        ticks += (f'<line class="{"l" if long_ else ""}" style="animation-delay:{i * 6}ms" '
                  f'x1="{c + r1 * math.sin(a):.2f}" y1="{c - r1 * math.cos(a):.2f}" '
                  f'x2="{c + (R - 2) * math.sin(a):.2f}" y2="{c - (R - 2) * math.cos(a):.2f}" '
                  f'stroke-width="{1.6 if long_ else 1}"/>')
    lettres = "".join(f'<text x="{c + 70 * math.sin(math.radians(a)):.1f}" y="{c - 70 * math.cos(math.radians(a)):.1f}" '
                      f'class="{"n" if l == "N" else ""}">{l}</text>' for l, a in (("N", 0), ("E", 90), ("S", 180), ("O", 270)))

    def arc(d0, d1, r=R + 7):
        a0, a1 = math.radians(d0), math.radians(d1)
        return (f'M{c + r * math.sin(a0):.2f},{c - r * math.cos(a0):.2f} '
                f'A{r},{r} 0 0 1 {c + r * math.sin(a1):.2f},{c - r * math.cos(a1):.2f}')
    segs = "".join(f'<path class="bs-seg" d="{arc(d0, d1)}"/>' for d0, d1 in ((-58, -22), (-18, 18), (22, 58)))
    L, W = 62, 9
    return (f'<svg id="bs-rose" class="bs-rose" width="{taille}" height="{taille}" viewBox="0 0 200 200" role="img" '
            f'aria-label="Boussole interactive : cliquez pour jouer à trouver le nord">'
            f'<circle class="bs-halo" cx="100" cy="100" r="60"/>'
            f'<circle class="bs-cadran" cx="100" cy="100" r="{R}" fill="none" stroke-width="2.2"/>'
            f'<g class="bs-ticks">{ticks}</g>{lettres}{segs}'
            f'<g id="bs-aiguille"><polygon class="tete" points="100,{100 - L} {100 + W},100 {100 - W},100"/>'
            f'<polygon class="queue" points="100,{100 + L} {100 + W},100 {100 - W},100"/></g>'
            f'<circle cx="100" cy="100" r="4.5" fill="var(--text)"/><circle cx="100" cy="100" r="1.8" fill="var(--bg)"/></svg>')
