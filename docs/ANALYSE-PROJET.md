# Journal de Gaspard — Analyse technique du projet

> Document de référence — analyse réalisée le 3 août 2026, mise à jour le 3 août 2026 (ajout du duel 007)
> Dépôt : https://github.com/ldcom1993-hue/journaldegaspard (branche `main`, 211 commits)
> Site en production : https://journaldegaspard.fr/

---

## 1. Ce que fait le projet

**Journal de Gaspard** est un **site statique encyclopédique** organisé en « univers » fictionnels.

Un seul univers est actuellement implémenté : **Olive et Tom** (*Captain Tsubasa*). Le site expose un catalogue de personnages (235 fiches), d'équipes (102) et de techniques (304), avec recherche, filtres et fiches détaillées.

La particularité du projet : **les données ne sont pas écrites à la main**. Elles sont moissonnées automatiquement depuis l'**API MediaWiki du Fandom Captain Tsubasa** par un pipeline Python, puis commitées dans le dépôt sous forme de JSON statiques que le front consomme via `fetch()`.

**Modèle mental** : c'est un *static site generator* inversé — pas de build, mais un pipeline de données découplé qui alimente des fichiers JSON versionnés.

### Nouveauté : le duel « 007 » (univers Olive et Tom)

Depuis le commit `a7e7d0a` (`feat(duel): jeu 007 à deux joueurs en ligne`), le site n'est plus seulement une encyclopédie consultative : il embarque un **mini-jeu en ligne à deux joueurs**, en tour par tour, transposition du jeu de mise "007" au football (construire / tirer au but / défendre). Deux joueurs rejoignent une partie via un code à 4 caractères, choisissent leur coup en secret, et les coups sont révélés et résolus simultanément. Premier à 3 buts gagne.

Points clés :
- **Backend PHP autoritatif** (`api/partie.php`) sans dépendance ni base de données — l'état de chaque partie vit dans un fichier JSON sous `api/parties/`, protégé par `flock` pour sérialiser les accès concurrents.
- Le client ne fait qu'exprimer une intention ; toutes les règles (munitions, anti-défense-en-boucle, jetons de session) sont validées côté serveur.
- Le coup en attente de l'adversaire n'est jamais exposé dans la réponse réseau avant résolution de la manche.
- Le client (`univers/olive-et-tom/match.html`, `assets/js/match.js`, `assets/css/match.css`) fonctionne par polling de l'état de partie.

**⚠️ Rupture avec le modèle initial** : cette fonctionnalité introduit la première dépendance serveur du projet (PHP 7.4+, dossier `api/` inscriptible), ce qui déroge explicitement à la règle « no server-side code » d'`agents.md`. Aucune dépendance externe, aucun build step ni service tiers n'est introduit pour autant — c'est une exception ciblée, pas un changement de stack. `agents.md` doit encore être mis à jour pour documenter formellement cette exception (voir §5 et §7).

---

## 2. Stack technique

### Front-end
| Élément | Choix |
|---|---|
| Langage | HTML5 + CSS3 + **JavaScript vanilla ES6+** |
| Framework | **Aucun** (contrainte explicite dans `agents.md`) |
| Build step | **Aucun** — pas de npm, pas de bundler, pas de transpilation |
| Données | `fetch()` sur des JSON statiques |
| APIs navigateur | `IntersectionObserver`, `<template>`, `URLSearchParams`, `data:` URI SVG |

### Back-end / Data (pipeline de contenu)
| Élément | Choix |
|---|---|
| Langage | **Python 3** (stdlib uniquement — `urllib`, `json`, `re`, `pathlib`) |
| Dépendances | **Zéro** (pas de `requirements.txt`, pas de `requests`/`BeautifulSoup`) |
| Source | API MediaWiki : `https://captaintsubasa.fandom.com/api.php` |
| Sortie | JSON dans `assets/data/` |

### Back-end applicatif — duel « 007 » (nouveau, `a7e7d0a`)
| Élément | Choix |
|---|---|
| Langage | **PHP 7.4+**, un seul fichier (`api/partie.php`) |
| Dépendances | **Zéro** |
| État | Fichiers JSON sous `api/parties/` (non versionnés, `.gitignore`), verrouillage `flock` |
| Protocole | Polling HTTP côté client (GET/POST JSON) |

Cette brique casse la règle « site 100 % statique » posée dans `agents.md` — voir encadré ci-dessus. C'est actuellement la **seule** exception au principe « zéro serveur » du projet.

### Infra
| Élément | Choix |
|---|---|
| CI/CD | GitHub Actions (5 workflows) |
| Hébergement | **OVH**, déploiement **FTP** (`SamKirkland/FTP-Deploy-Action@v4.3.4`) |
| Secrets | `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD` |

**Contraintes fortes documentées dans `agents.md`** : tout doit fonctionner en fichiers statiques purs. Interdit : runtime Node, code serveur, gestionnaire de paquets, dépendances externes. Les images ne doivent jamais être hotlinkées — elles sont téléchargées et stockées dans `assets/images/olive-et-tom/`.

---

## 3. Architecture

### Arborescence

```
/
├── index.html                    # Hub : grille des univers
├── agents.md                     # ⚠️ Règles impératives pour tout contributeur (humain ou IA)
├── README.md
├── .gitignore                    # Exclut api/parties/ (état vivant du duel) et divers
├── sync_personnages.py           # Pipeline #1 : collecte de base (659 l.)
│
├── api/
│   └── partie.php                # ⚠️ Backend PHP du duel — API + moteur de règles (639 l.)
│
├── assets/
│   ├── css/
│   │   ├── style.css             # Feuille unique, 393 l.
│   │   └── match.css             # Styles du duel, en extension de style.css (691 l.)
│   ├── js/
│   │   ├── main.js               # Rendu du hub (36 l.)
│   │   ├── personnages.js        # Liste + filtres + tri (480 l.)
│   │   └── match.js              # Duel : polling, rendu, reprise de session (611 l.)
│   ├── data/
│   │   ├── personnages.json      # 235 entrées — 409 Ko
│   │   ├── equipes.json          # 102 entrées — 88 Ko
│   │   └── techniques.json       # 304 entrées — 183 Ko
│   └── images/olive-et-tom/      # 268 PNG — ~12 Mo
│
├── univers/olive-et-tom/
│   ├── index.html                # Sommaire de l'univers (carte d'accès au duel ajoutée)
│   ├── personnages.html          # Liste (338 l.)
│   ├── personnage.html           # Fiche détail (625 l., JS inline)
│   └── match.html                # Duel : accueil, salon, match, fin (209 l.)
│
├── scripts/                      # Pipeline #2 (modulaire)
│   ├── sync_entities.py          # Orchestrateur (366 l.)
│   ├── build_team_graph.py       # (310 l., non câblé en CI)
│   └── fandom/
│       ├── client.py             # Couche API MediaWiki
│       ├── normalize.py          # Nettoyage, infobox, slugify (294 l.)
│       ├── extract_teams.py      # Extraction équipes (215 l.)
│       ├── extract_techniques.py # Extraction techniques (121 l.)
│       ├── relations.py          # Construction des refs {slug,name,url}
│       └── writers.py            # Écriture atomique + garde-fous
│
├── docs/
│   ├── entities-sync.md          # Doc d'architecture du pipeline #2
│   └── jeu-duel.md               # Matrice de résolution, API, pistes V2 du duel
└── .github/
    ├── scripts/                  # ⚠️ Copies divergentes de scripts racine
    └── workflows/                # 5 workflows
```

**Volumétrie code** : ~7 250 lignes au total (hors JSON/images), dont ~1 950 Python, ~1 750 HTML/JS front (encyclopédie) et ~1 550 lignes pour le duel (PHP + JS + CSS + HTML).

### Flux de données

```
Fandom Captain Tsubasa (API MediaWiki)
            │
            ├─► sync_personnages.py ──────► personnages.json  (base : nom, image, position, popularité)
            │
            └─► scripts/sync_entities.py ─► personnages.json  (enrichi : teams[], techniques[])
                                          ├► equipes.json     (+ players[])
                                          └► techniques.json  (+ users[])
                            │
                            ▼
                    commit sur main (bot)
                            │
                            ▼
                 deploy.yml ──FTP──► OVH /www/
                            │
                            ▼
              Navigateur : fetch() des JSON → rendu DOM
```

### Modèle de données

**`personnages.json`** — liste d'objets :
```json
{
  "slug": "tsubasa-ozora",
  "name": "Tsubasa Ozora",
  "japaneseName": "大空 翼",
  "nameSplit": { "latin": "...", "kanji": "..." },
  "position": "Attacking midfielderForward",
  "nationality": "...",
  "image": "/assets/images/olive-et-tom/tsubasa-ozora.png",
  "popularity": 1, "popularityRank": 1,
  "physical": {...}, "infobox": {...},
  "teams":      [{ "slug","name","url","confidence" }],
  "techniques": [{ "slug","name","url" }]
}
```

**`equipes.json`** : `slug, name, type (club|national|school), age_category, parent_team, url, description, image, players[]`

**`techniques.json`** : `slug, name, url, description, image, users[]`

Les relations sont **bidirectionnelles et dénormalisées** (personnage→équipe *et* équipe→joueurs), et chaque référence embarque déjà son `url` front. Choix pragmatique : zéro jointure côté client, au prix d'une redondance.

### Points d'architecture notables

- **Écriture atomique + garde-fou anti-écrasement** (`writers.py`) : refuse d'écrire si le résultat contient moins de `minimum_items` entrées. Protège contre un JSON vidé par une panne réseau du Fandom. Bonne pratique, à conserver.
- **Score de confiance** (`confidence: low|medium|high`) sur les relations équipes — reconnaissance explicite de l'incertitude de l'extraction heuristique.
- **Stratégie techniques** : plutôt que de parser les sections libres des pages personnages (fragile), le pipeline part des catégories Fandom de techniques, puis intersecte les liens de chaque page technique avec les titres de personnages connus. Approche robuste, bien documentée dans `docs/entities-sync.md`.
- **Placeholder SVG généré à la volée** (`makePlaceholder()` dans `personnages.js`) : initiales sur dégradé, encodé en `data:` URI. Aucune requête réseau, aucun asset supplémentaire.
- **Progressive enhancement** : les cartes apparaissent via `IntersectionObserver`, le HTML reste sémantique et accessible (`aria-live`, `visually-hidden`, `alt` explicites).

---

## 4. CI/CD — les 5 workflows

| Workflow | Déclencheur | État |
|---|---|---|
| `deploy.yml` | push sur `main` + manuel | ✅ Actif — FTP vers OVH `/www/`, exclut `.github`, `scripts/`, `docs/`, `README.md`, `agents.md`, `api/parties/` (état vivant du duel, propre au serveur) |
| `sync-entities.yml` | manuel | ✅ Actif — lance `scripts/sync_entities.py`, commit les 3 JSON |
| `sync-personnages.yml` | manuel | ⚠️ **L'étape d'exécution du script est commentée** — le job ne fait plus qu'un `git add`/commit à vide |
| `update-captain-tsubasa-portraits.yml` | **cron lundi 5h** + manuel | ⚠️ Actif mais **basé sur du code obsolète** (voir §5) |
| `fetch-all-character-images.yml` | manuel | ❌ **Cassé** — parse `personnages.js` en `grep`/`sed` pour y trouver `japaneseName` et des liens qui n'y sont plus |

`dangerous-clean-slate: false` sur le déploiement : les fichiers supprimés du dépôt **ne sont pas supprimés du serveur**. Comportement à connaître.

---

## 5. Dette technique identifiée

### 🔴 Bloquants fonctionnels

**1. Liens morts vers `equipe.html` et `technique.html`**
Les trois JSON et `personnage.html` (l. 457, 465) génèrent des URLs `/univers/olive-et-tom/equipe.html?slug=...` et `technique.html?slug=...`. **Ces deux pages n'existent pas.** Toute relation cliquée depuis une fiche personnage → 404. C'est le chantier le plus évident du projet (les données sont prêtes, il ne manque que les vues).

**2. Le pipeline de portraits tourne chaque semaine sur du code périmé**
`.github/scripts/update_ct_portraits.py` télécharge tous les portraits puis **réécrit `assets/js/personnages.js` par substitution regex** sur des littéraux `image: "..."`. Or `personnages.js` est aujourd'hui un *moteur de rendu*, plus un fichier de données — les portraits sont référencés dans `personnages.json`. Conséquences : la mise à jour des chemins d'images est inopérante, et le regex opère à l'aveugle sur du code applicatif (risque de corruption). Les 17 commits `chore: update Captain Tsubasa portraits` consécutifs en tête d'historique en sont la trace, et gonflent le dépôt de PNG réécrits chaque semaine.

### 🟠 Cohérence

**3. Duplication divergente de `sync_personnages.py`**
Deux versions coexistent avec des contenus différents : `/sync_personnages.py` (659 l.) et `/.github/scripts/sync_personnages.py` (304 l.). Aucun workflow n'exécute ni l'une ni l'autre actuellement. Source de confusion garantie.

**4. Assets incohérents**
- 2 images référencées mais absentes du disque (`gentile`, `minor-characters`) — rattrapées par le placeholder, donc invisibles en prod.
- 35 fichiers PNG présents mais référencés par aucun personnage (dont des artefacts de scraping : `categorymain-characters.png`, `category-groups.png`…). Doublons de nommage également (`category-anime-characters.png` *et* `categoryanime-characters.png`), et un fichier avec une **tabulation dans son nom** : `Ozora\tolivier-atton.png`.

**5. Données non traduites**
`agents.md` impose les noms français (« Olivier Atton », « Thomas Price »…). Les JSON contiennent les noms **japonais romanisés** issus du Fandom (« Tsubasa Ozora », « Kojiro Hyuga »). Idem pour les positions (`"Attacking midfielderForward"` — non nettoyée, concaténation d'infobox) et les nationalités. Il manque une couche de mapping FR.

### 🟡 Qualité / perf

**6. Chargement intégral du JSON pour une seule fiche**
`personnage.html` fait `fetch('/assets/data/personnages.json')` (409 Ko) puis un `.find()` pour un seul personnage. Idem pour les futures pages équipe/technique. À terme : soit un split par slug, soit un index léger.

**7. Front dupliqué entre pages**
`personnage.html` embarque 330 lignes de JS inline (normalisation des relations, slugify, placeholder) qui recoupent largement `assets/js/personnages.js`. Aucun module partagé. Les ES modules natifs (`<script type="module">`) résoudraient ça sans violer la contrainte « no build step ».

**8. CSS dispersé**
`univers/olive-et-tom/index.html` contient ~90 lignes de `<style>` inline pour le header, non partagées avec les autres pages de l'univers.

**9. Divers**
- `console.log("Sorting mode:", mode)` laissé en production (`personnages.js` l. 402).
- `main.js` s'exécute sans garde : si `#projects-grid` est absent, TypeError.
- Image du hub en `placehold.co` — hotlink externe, ce qui contredit la politique images d'`agents.md`.
- Aucun test, aucun linter, aucun formateur configuré.
- `.gitignore` ajouté avec le duel (`a7e7d0a`) — couvre `api/parties/` et le bruit habituel (`.DS_Store`, `*.log`). Aucune `LICENSE` en revanche.

### 🟠 Cohérence (suite — introduit par le duel)

**10. `agents.md` en retard sur le code**
Le commit `a7e7d0a` introduit un backend PHP (`api/partie.php`) alors qu'`agents.md` interdit explicitement tout code serveur. Le message de commit reconnaît la rupture (« BREAKING ») mais `agents.md` n'a pas encore été mis à jour pour documenter cette exception. Tant que ce n'est pas fait, la règle écrite et le code réel divergent — risque de confusion pour le prochain contributeur (humain ou agent IA) qui lira `agents.md` au pied de la lettre.

---

## 6. Comment contribuer — règles à respecter

**`agents.md` fait autorité.** C'est un contrat explicite pour tout contributeur (il est d'ailleurs rédigé pour des agents IA). Résumé opérationnel :

1. **Pas de framework, pas de build, pas de dépendance.** Tout doit tourner nativement dans le navigateur.
2. **Images** : jamais de hotlink. Téléchargement local dans `assets/images/olive-et-tom/`, nommage `kebab-case` minuscule, chemins relatifs. Placeholder si introuvable.
3. **Structure de navigation** : chaque univers = `/univers/{univers}/index.html` + pages internes. La home ne lie que vers les `index.html` d'univers.
4. **Avant de terminer une tâche** : vérifier liens, images, chemins relatifs, responsive mobile + desktop.
5. **Éviter les hacks temporaires** — préférer la solution maintenable.

⚠️ **Exception non encore actée dans le texte** : le duel « 007 » (`api/partie.php`) requiert désormais PHP côté serveur, en contradiction avec la règle 1. C'est une exception délibérée et documentée dans le message du commit `a7e7d0a` et dans `docs/jeu-duel.md`, mais `agents.md` lui-même n'a pas encore été édité pour l'autoriser explicitement — à faire avant que la règle ne induise en erreur un futur contributeur.

### Environnement local

```bash
git clone https://github.com/ldcom1993-hue/journaldegaspard.git
cd journaldegaspard

# Serveur statique — obligatoire : les fetch() utilisent des chemins absolus (/assets/...)
python3 -m http.server 8000
# → http://localhost:8000

# Régénérer les données (Python 3, aucune dépendance)
python sync_personnages.py
python scripts/sync_entities.py
```

⚠️ Ouvrir les fichiers en `file://` ne marchera pas : chemins absolus + CORS sur `fetch()`.

**Pour tester le duel en local**, `python3 -m http.server` ne suffit pas (il ne sait pas exécuter du PHP) : utiliser le serveur intégré de PHP à la place, à la racine du dépôt :

```bash
php -S localhost:8000
```

---

## 7. Pistes de contribution, par valeur décroissante

| # | Chantier | Effort | Impact |
|---|---|---|---|
| 1 | Créer `equipe.html` et `technique.html` — supprime tous les 404 actuels, données déjà prêtes | M | 🔥 Élevé |
| 2 | Réparer ou retirer `update_ct_portraits.py` (cible `personnages.json`, pas le JS) + désactiver le cron en attendant | S | 🔥 Élevé |
| 3 | Ajouter `equipes.html` / `techniques.html` (listes) et les cartes correspondantes dans l'index d'univers | M | Élevé |
| 4 | Couche de traduction FR (noms, positions, nationalités) conforme à `agents.md` | M | Élevé |
| 5 | Extraire un module partagé (`assets/js/shared.js`, ES module) : slugify, placeholder, normalisation des relations | S | Moyen |
| 6 | Nettoyer les assets orphelins + le fichier au nom contenant une tabulation | S | Moyen |
| 7 | Dédupliquer `sync_personnages.py`, supprimer ou réparer `fetch-all-character-images.yml` | S | Moyen |
| 8 | Mettre à jour `agents.md` pour documenter formellement l'exception PHP du duel (règle 1) | S | Élevé |
| 9 | Ajouter `CONTRIBUTING.md` et un lint minimal (Prettier + Ruff/PHP_CodeSniffer en CI) | S | Moyen |
| 10 | Optimiser le chargement (index léger ou split par slug) | M | Faible aujourd'hui |
| 11 | Compresser les PNG (12 Mo pour 268 fichiers) | S | Faible |

---

## 8. Verdict

**Points forts** — L'architecture est plus réfléchie que la taille du projet ne le laisse supposer : séparation nette données/présentation, pipeline Python modulaire et documenté, garde-fous d'écriture atomique, scores de confiance sur les relations, contraintes de projet explicitées dans `agents.md`. La discipline « zéro dépendance » est réellement tenue des deux côtés de la stack.

**Points faibles** — Le projet a *pivoté* d'un modèle « données dans le JS » vers « données en JSON » sans nettoyer derrière lui. Il en reste des scripts et workflows qui pointent vers l'ancien monde, dont un qui tourne en cron toutes les semaines. Et le front n'a pas suivi le back : les données d'équipes et de techniques existent, sont riches et correctement liées, mais **aucune page ne les affiche**.

**Le vrai chantier** : combler l'écart entre les données disponibles et les vues existantes. C'est là que le rapport valeur/effort est le meilleur.

**Nouveau depuis le duel (`a7e7d0a`)** — Le projet pivote une seconde fois, cette fois côté infra : d'un site 100 % statique vers un site majoritairement statique avec une brique serveur ciblée. L'implémentation elle-même est propre (autorité serveur, verrouillage de fichier, jetons de session, non-fuite du coup adverse), mais la gouvernance n'a pas suivi : `agents.md` interdit encore, noir sur blanc, ce que le code fait déjà. À corriger avant que d'autres briques serveur n'arrivent sans qu'on ait tranché la question une fois pour toutes.
