# Boussole · conseiller de portefeuille d'actions

Application web locale (Python + Streamlit) qui aide un investisseur particulier à gérer son capital
(**500 000 € par défaut, modifiable**) réparti sur **jusqu'à 10 actions ou ETF de n'importe quelle bourse du monde**,
sur un horizon d'**un an** : indicateurs fondamentaux et techniques, actualités de sources reconnues,
recommandation **Acheter (+1) / Attendre (0) / Vendre (−1)** adaptée à son **profil de risque**,
simulation d'opérations validées par le client et backtest annuel.

Interface en verre translucide (« liquid glass ») fondée sur la **charte graphique Boussole v3** :
rôles de couleur clair / sombre, jauge de décision, aiguille à ressort, mouvement amorti sans animation en boucle.

## Installation et lancement

Prérequis : Python 3.10 ou plus récent (Windows ou macOS), connexion internet, navigateur récent.

```bash
cd boussole
python -m venv .venv
# Windows : .venv\Scripts\activate      macOS : source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501. Tests automatisés : `python -m pytest -q` (32 tests).

Si une ancienne version de Streamlit est installée, mettez-la à jour (`pip install -U -r requirements.txt`) :
les versions antérieures à 1.45 affichent « undefined » comme titre des graphiques Plotly récents.

## Parcours

1. **Connexion / inscription** sur une page dédiée. Les comptes sont **locaux** (`data/comptes/`) : le mot de
   passe n'est stocké que sous forme d'empreinte PBKDF2-SHA256 salée, rien n'est envoyé en ligne. La session
   reste ouverte 30 jours sur cet ordinateur (bouton « Se déconnecter » en haut à droite).
2. **Profil d'investisseur obligatoire** (8 questions) avant d'accéder à l'application.
3. **Composition du portefeuille** : capital, actions de toutes les bourses, répartition à parts égales ou libre.
4. **Accueil** avec les « Premiers pas » et, sur chaque page, un encadré d'aide (désactivable dans « Mon profil »).

## Portefeuille réel et simulateur

- **Mon portefeuille** (par défaut) : constitué au dernier cours connu le jour de l'ouverture, puis suivi
  séance après séance avec les vrais cours. L'**historique** ne contient que ce que vous avez fait :
  investissement initial, achats et ventes confirmés, nouvelles répartitions, apports et retraits de
  liquidités, chacun daté (séance et heure d'enregistrement), filtrable et exportable en CSV.
- **Simulateur** (barre latérale) : un portefeuille d'essai séparé rejoue l'année passée séance par séance
  (+1 J, +1 S, +1 M, lecture et pilote automatiques), sans toucher au portefeuille réel.
- Une valeur ajoutée dans « Mes actions » apparaît **aussitôt dans tous les onglets** ; une valeur encore
  détenue ne peut être retirée qu'après la vente des titres.

## Données

- **Cours réels Yahoo Finance par défaut** (bibliothèque yfinance, clôtures ajustées, 3 ans d'historique).
  Les cours sont mis en cache dans `data/cache/`. Si Yahoo Finance devient injoignable, Boussole réutilise
  les derniers cours réels enregistrés et l'affiche clairement (« Hors ligne · cours du … »).
  Sans cache, un écran d'erreur propose « Réessayer » : **aucune donnée fictive n'est jamais présentée
  comme réelle**.
- **Toutes les places de cotation** : la recherche de « Mes actions » interroge Yahoo Finance (nom ou symbole) et
  des suggestions couvrent New York, Francfort, Amsterdam, Zurich, Londres, Tokyo, Hong Kong… Les cours cotés hors
  zone euro (USD, GBp, CHF, JPY…) sont **convertis en euros** au taux de change de chaque séance.
- **Bandeau de marché** : l'indice de référence de chaque bourse où sont cotées vos actions (CAC 40, S&P 500 et
  Nasdaq, DAX, FTSE 100, SMI, Nikkei 225, Hang Seng…).
- **Courbes** : 1J, 2J et 5J en données toutes les 5 minutes (heure de Paris) à la séance la plus récente ;
  1M, 3M, 6M, 1A et 2A en clôtures quotidiennes.
- **Actualités** : fil Yahoo Finance de la valeur et Google Actualités (France), filtrés sur une liste de
  médias reconnus (Les Echos, Boursorama, Zonebourse, Reuters, Bloomberg, AFP, BFM, Investir, Le Figaro…),
  avec la source et l'heure de publication (« il y a 12 min »), actualisés toutes les 10 minutes.
- **Mode démonstration** : uniquement sur choix explicite (onglet « Mon profil » ou écran d'erreur), avec un
  bandeau « données fictives » permanent. Il sert aussi aux tests (graine fixe).

## Profil de risque

L'onglet « Mon profil » contient un questionnaire de 8 questions (horizon, épargne de précaution, part du
patrimoine, revenus, objectif, perte acceptable, réaction à une baisse, expérience). Il donne un score sur 100
et un profil **Prudent**, **Équilibré** ou **Dynamique** ; une réponse de capacité à 0 (horizon court, pas
d'épargne de précaution, perte acceptable de 5 %) plafonne le profil.

Le profil adapte le conseil :
- seuils de décision (stop-loss, prise de bénéfices, trailing stop, alertes et objectif hebdomadaires) ;
- part des liquidités engagée par achat et **poids maximal d'une valeur** (25 / 35 / 50 %) ;
- **adéquation des valeurs** : un signal d'achat est écarté si la volatilité du titre dépasse le maximum du
  profil (25 / 35 / 50 %), et chaque fiche indique si la valeur est adaptée au profil.

Chaque évaluation est conservée avec sa date et son motif (retraite, projet, héritage…) : refaire le
questionnaire quand la situation change met à jour les règles. Un rappel s'affiche si le profil n'a jamais
été évalué ou date de plus d'un an. Le profil « Dynamique » correspond aux objectifs du cahier des charges
(+10 % / −10 % par semaine).

## Sur téléphone, tablette et ordinateur

- **Lancer pour tous les appareils** : `python lancer.py` (Windows, macOS, Linux). Le terminal affiche l'adresse à ouvrir sur le téléphone ou la tablette, par exemple `http://192.168.1.20:8501` (même Wi-Fi). `python lancer.py --local` limite l'accès à cet ordinateur.
- **Installer comme une application** : sur iPhone/iPad (Safari) « Partager → Sur l'écran d'accueil » ; sur Android (Chrome) « ⋮ → Ajouter à l'écran d'accueil » ; sur ordinateur (Chrome, Edge) l'icône d'installation dans la barre d'adresse. Icônes et manifeste dans `static/`.
- **Affichage adapté** : sur téléphone, la page de connexion se resserre (boussole puis formulaire), les bandeaux de cours défilent horizontalement, la barre latérale se replie d'elle-même sous 1 100 px.
- **Remplissage automatique** : les champs portent les noms et attributs `autocomplete` standard (username, current-password, new-password, given-name, family-name), reconnus par les navigateurs et gestionnaires de mots de passe ; une valeur remplie automatiquement est bien prise en compte à l'envoi.
- Les comptes restent sur l'ordinateur qui exécute Boussole : les autres appareils s'y connectent, rien n'est envoyé ailleurs.

## Catalogue

Plus de 360 actions et ETF des principales bourses (Paris, Francfort, Amsterdam, Londres, Zurich, New York, Tokyo, Hong Kong, Séoul, Bombay, Sydney…) sont proposés dès la création du compte, sans connexion. La recherche Yahoo Finance complète le catalogue pour tout autre titre.

## Cours en direct

- Le bandeau « En direct » interroge Yahoo Finance toutes les 30 s (cours minute par minute, une seule requête groupée, mise en cache 20 s). Chaque valeur affiche son prix en euros, sa variation depuis la clôture précédente, l'heure de la cotation et un point vert si sa place est ouverte.
- Le dernier cours remplace la clôture de la séance du jour : valeur du portefeuille, plus-values, signaux et prix des ordres sont calculés au cours réel du moment. Les jours précédents ne sont jamais modifiés.
- Quand un cours bouge, la page entière se met à jour d'elle-même (au plus une fois par minute, jamais pendant qu'une fenêtre de confirmation est ouverte) et le chiffre clignote en vert ou en rouge. Les indices (CAC 40, S&P 500…) sont actualisés de la même façon. Interrupteur « Cours en direct » dans la barre latérale.
- Selon la place, Yahoo peut différer les cours de 15 à 20 min : la mention « différé » apparaît alors à côté de l'heure.
- Si les cotations n'arrivent pas, le bandeau en donne la cause. En mode démonstration, un encadré rappelle que les cours sont fictifs et immobiles, avec le bouton « Données réelles ».

## Animations et interactivité (v4)

Toutes les animations sont déclenchées par une action (ouverture, survol, saisie, clic) et s'arrêtent d'elles-mêmes : aucune boucle, conformément à la charte. Elles se coupent avec l'option « Animations » du profil ou le réglage système « réduire les animations ».

- **Chargement** : un voile de verre dépoli, l'aiguille tourne tant que la page se calcule (seule animation en boucle, liée à l'attente), puis se cale au nord et le voile s'efface. Le thème choisi et l'onglet ouvert sont conservés au rechargement.
- **Changement de page** (connexion → profil → portefeuille → tableau de bord) : l'aiguille tourne vers le cap de la nouvelle page (0°, 120°, 240°, 360°), le contenu apparaît en fondu.
- **Page de connexion** : la grande boussole suit le curseur, pointe le champ actif et commente la saisie ; e-mail invalide ou identifiants refusés → l'aiguille plonge au sud et tremble ; mot de passe : trois segments de robustesse, plein nord quand il est solide ; confirmation vérifiée en direct.
- **Jeu « Trouvez le nord »** : cliquez sur la boussole, elle tourne ; recliquez pour l'arrêter au plus près du nord. Le meilleur écart est gardé dans le navigateur.
- **Dans l'application** : l'aiguille du logo indique l'onglet actif (et prévisualise celui survolé), les cartes de verre s'inclinent et captent la lumière sous le curseur, les boutons ondulent au clic, le grand cadran du fond suit légèrement la souris, une pastille « Mise à jour… » apparaît pendant les calculs longs.

## Organisation

| Fichier | Rôle |
| --- | --- |
| `app.py` | Interface : 7 onglets, horloge de simulation, dialogues de validation |
| `boussole/data.py` | Yahoo Finance (cours, conversion en euros, intrajournalier, recherche, fondamentaux), cache hors ligne, mode démonstration |
| `boussole/news.py` | Actualités Yahoo + Google Actualités, liste blanche de sources, tonalité |
| `boussole/profil_risque.py` | Questionnaire, calcul du profil, règles et adéquation par profil |
| `boussole/comptes.py` | Comptes locaux : inscription, connexion, sessions, mots de passe chiffrés |
| `boussole/indicators.py` | MM20/MM50, RSI, Bollinger, MACD, support/résistance, volatilité |
| `boussole/rules.py` | Règles de décision EXG-F-12 à EXG-F-25, avec la priorité au risque |
| `boussole/score.py` | Jauge : score −100…+100, confiance, 6 piliers, niveau de stop-loss |
| `boussole/portfolio.py` | Portefeuille, transactions, gains et pertes par action |
| `boussole/engine.py` | Analyse du jour, pilote automatique, backtest |
| `boussole/ui.py`, `boussole/theme.py` | Jetons de design, CSS « liquid glass », composants |
| `static/fonts/` | Polices embarquées (licence SIL OFL) |
| `tests/` | 32 tests automatisés |

## Typographie

À la demande du client (rendu « moins IA »), les polices de la charte (Fraunces, Inter, JetBrains Mono)
sont remplacées par **Source Serif 4** (titres), **IBM Plex Sans** (texte) et **IBM Plex Mono** (chiffres),
embarquées dans `static/fonts/`.

## Utilisation

- **Barre latérale** : avancer la séance (+1 J, +1 S, +1 M, Début, Aujourd'hui, lecture automatique),
  pilote automatique, mode Sombre / Clair / Automatique.
- **Accueil** : signal global, chiffres clés, risque de la semaine, liste de suivi, dernières actualités.
- **Synthèse et opérations** : fiche d'une valeur, adéquation au profil, jauge, « Pourquoi ce signal ? »,
  courbes 1J à 2A, simulation d'achat ou de vente, historique exportable en CSV.
- **Signes, santé et actualités** : analyse technique, 5 indicateurs fondamentaux, actualités datées et sourcées.
- **Portefeuille** : performance, répartition, gains et pertes par action, rendements hebdomadaires.
- **Mes actions** : rechercher et ajouter n'importe quelle valeur, répartir son argent (Boussole calcule les
  ordres), apports et retraits de liquidités, comparaison des valeurs.
- **Mon profil** : questionnaire de profil de risque, historique, préférences, compte.
- **Budget et règles** : capital investi, seuils de décision, backtest et reproductibilité.

## Hypothèses

- « Rester (0) » du cahier des charges est affiché **ATTENDRE**, conformément à la charte v3.
- Les 5 indicateurs fondamentaux : chiffre d'affaires, dividende par action, rendement, PER et marge nette.
  Une donnée non publiée par Yahoo est affichée « n.d. » et n'est pas inventée.
- Les opérations sont enregistrées au cours de clôture de la dernière séance connue (pas d'ordre au marché en
  temps réel : Boussole n'est relié à aucun courtier).
- Aucune donnée n'est envoyée en dehors de l'ordinateur : comptes, profils et portefeuilles restent dans `data/`.

Boussole est un outil d'information et d'aide à l'analyse. Elle ne constitue pas un conseil en
investissement personnalisé. Tout investissement comporte un risque de perte en capital et les
performances passées ne préjugent pas des performances futures.

Captures d'écran (en mode démonstration, faute d'accès à Yahoo depuis l'environnement de développement) : dossier `docs/captures/`.
