# Journal de Gaspard — Analyse technique du projet

> Document de référence — analyse réalisée le 3 août 2026, mise à jour le 5 août 2026
> (duel 007, puis pages équipes/techniques et correction du pipeline de techniques)
> Dépôt : https://github.com/ldcom1993-hue/journaldegaspard (branche `main`, 218 commits)
> Site en production : https://journaldegaspard.fr/

---

## 1. Ce que fait le projet

**Journal de Gaspard** est un **site statique encyclopédique** organisé en « univers » fictionnels.

Un seul univers est actuellement implémenté : **Olive et Tom** (*Captain Tsubasa*). Le site expose un catalogue de personnages (235 fiches), d'équipes (102) et de techniques (155), avec recherche, filtres et fiches détaillées.

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

### Nouveauté : pages équipes et techniques, et pipeline de techniques corrigé

La PR #55 comble l'écart qui faisait l'objet du chantier n°1 de ce document : les données d'équipes et de techniques existaient, étaient riches et correctement liées, mais **aucune page ne les affichait**. Quatre pages sont livrées (`equipes.html`, `equipe.html`, `techniques.html`, `technique.html`), portées par un module ES partagé `assets/js/entites.js` — natif, sans build step.

En chemin, deux défauts du pipeline de données ont été trouvés et corrigés. Ils se masquaient l'un l'autre et **vidaient silencieusement** les fiches techniques :

1. **`prop=extracts` sur un wiki qui ne l'a pas.** `fetch_intro_extract` interrogeait une extension absente du Fandom. L'API répondait `200` avec un avertissement de paramètre inconnu, sans jamais lever d'exception : le `except RuntimeError` ne se déclenchait pas et les descriptions restaient vides sur la totalité du catalogue, sans le moindre signal. Elles sont désormais lues sur le HTML rendu.
2. **La page de la technique n'était jamais consultée.** L'extraction ne collectait que les titres des liens présents sur les pages `<Personnage>/Techniques`, où voisinent coéquipiers, clubs et tomes du manga — d'où des « techniques » nommées `AC Reggiana` ou `Captain Tsubasa (1981)`.

Les **huit catégories du wiki font désormais autorité** (`Ground shots`, `Aerial shots`, `Dribbles and feints`, `Cooperative tactics`, `Defensive techniques`, `Passes`, `Saves`, `Tactics and skills`). Une technique existe parce que le wiki la recense, non parce qu'une page la mentionne. Ce filtrage a permis de supprimer deux heuristiques de devinette sur les noms de liens.

| `techniques.json` | Avant | Après |
|---|---|---|
| Entrées | 304 | 155 |
| Avec description | **0** | **155** |
| Avec nom japonais | 0 | 144 |
| Dont artefacts | 203 | 0 |

Le nom du template ne pouvait pas servir de critère : une vraie technique utilise `Infobox character`, exactement comme un personnage.

**Limites assumées** :
- Une technique réelle mais non catégorisée sur le wiki reste absente du catalogue (`Back-Heel Pass`). Le correctif est à porter en amont, sur le wiki.
- `first_appearance` n'est rempli que 13 fois sur 155, le champ étant réellement vide côté source. Les fiches taisent les champs vides plutôt que d'aligner des « non renseigné ».
- **Aucune image de technique n'est récupérée**, alors que 13 pages sur 14 en ont une. `agents.md` interdit le hotlink, et télécharger ~150 visuels doublerait le poids du dépôt — chantier à part (voir §7).

### Le même angle mort côté équipes, corrigé dans la foulée

`description` et `image` étaient vides sur les **102 équipes**, pour une raison voisine : la page d'une équipe était bien récupérée par `fetch_page_wikitext`, mais uniquement pour vérifier qu'un joueur y figurait (`validate_team_membership`) — jamais pour son contenu. Le correctif des techniques s'est transposé tel quel (`fetch_team_details`).

| `equipes.json` | Avant | Après |
|---|---|---|
| Avec description | **0 / 102** | **98 / 102** |
| Avec nom japonais | 0 / 102 | 100 / 102 |

Les quatre équipes restantes (`ac-chievo-verona`, `brazil-middle-school`, `liverpool-fc`, `newcastle-united-fc`) ont une page dépourvue de tout paragraphe de prose — quand elle existe. Vérifié page par page : ce n'est pas un défaut d'extraction.

**Deux angles morts identiques à deux endroits du même pipeline** : la donnée était chargée, mais personne ne la lisait. C'est le motif à retenir de ce chantier — voir le verdict en §8.

### Nouveauté : le mode Équipe du duel

Le duel a désormais deux modes. **Classique** est le jeu d'origine, inchangé. **Équipe** ajoute une phase de composition : chaque joueur aligne trois personnages, un par famille de technique, et chacun apporte une cartouche jouable une seule fois dans le match.

Les huit catégories du wiki, qui servaient déjà à filtrer le catalogue, se projettent sur les trois coups du jeu — tir, construction, défense. Les retenir n'a coûté aucun appel supplémentaire : `techniques.json` porte maintenant `familles` et `effets`, et `assets/data/duel-roster.json` (54 Ko, 60 personnages) en dérive. Ce fichier dédié évite au serveur PHP de charger `personnages.json` (330 Ko) à chaque composition.

**La technique dépend du poste, pas du personnage seul.** Wakabayashi défend avec « Uppercut Defense » mais construirait avec « Birdcage » : une signature unique par personnage l'aurait rangé en construction, contresens pour un gardien. Les viviers y gagnent — 54 / 40 / 28 au lieu de 32 / 18 / 10 — et 45 personnages sur 60 sont éligibles à deux familles ou plus, ce qui donne au draft de vrais arbitrages.

**`resoudreManche()` n'a pas été modifiée.** `resoudreMancheEquipe()` l'enveloppe : surcoût prélevé en amont, issue corrigée en aval. Une manche de mode Classique suit exactement le chemin d'avant, ce que vérifie un test dédié.

Le mode a aussi fait grossir `api/partie.php` de ~450 à ~1000 lignes, et `match.js` de 611 à ~900. `assets/js/entites.js` n'est plus seulement le socle des pages entités : `match.js`, passé en module ES, y puise `makePlaceholder` et `safeText`.

**Jouer seul** est possible depuis l'ajout d'un adversaire piloté par le serveur. Plutôt que d'encoder une politique de jeu, il simule le vrai moteur : il énumère les actions légales des deux camps, appelle la résolution — qui est pure — sur chaque paire, note les positions obtenues et tire une stratégie mixte de la matrice par *regret matching*. On n'encode donc que « cette position est-elle bonne », jamais « que jouer ». Le mode Équipe n'a demandé aucun code de plus.

Sa qualité n'est pas une impression : `scripts/solve_duel.py` résout le mode classique et sert d'étalon. Le bot gagne 28 % des parties en facile, 41 % en normal et 53 % en difficile contre ce joueur de référence — chiffres qui ont servi à régler la fonction d'évaluation.

Il aligne une vraie équipe de la série (`duel-adversaires.json`, 22 équipes composables sur 102), ce qui donne un adversaire identifiable plutôt qu'un assemblage anonyme.

**Quitter une partie en cours** passe par l'action `abandonner` : le match s'achève et l'adversaire l'emporte. Effacer la session côté client suffirait à partir, mais laisserait l'autre devant un écran d'attente que rien ne viendrait clore.

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
├── .htaccess                     # Politique de cache : code revalidé, images figées un an
├── sync_personnages.py           # Pipeline #1 : collecte de base (659 l.)
│
├── api/
│   └── partie.php                # ⚠️ Backend PHP du duel — règles des deux modes (1106 l.)
│
├── assets/
│   ├── css/
│   │   ├── style.css             # Feuille unique, 393 l.
│   │   ├── match.css             # Styles du duel, en extension de style.css (691 l.)
│   │   └── entites.css           # Styles équipes/techniques, idem (498 l.)
│   ├── js/
│   │   ├── main.js               # Rendu du hub (36 l.)
│   │   ├── personnages.js        # Liste + filtres + tri (480 l.)
│   │   ├── match.js              # Duel : module ES — polling, draft, cartouches (941 l.)
│   │   └── entites.js            # Module ES partagé listes/fiches entités (639 l.)
│   ├── data/
│   │   ├── personnages.json      # 235 entrées — 330 Ko
│   │   ├── equipes.json          # 102 entrées — 104 Ko
│   │   ├── techniques.json       # 155 entrées — 119 Ko
│   │   ├── duel-roster.json      # Vivier du mode Équipe — 60 personnages, 53 Ko
│   │   └── duel-adversaires.json # Équipes alignables par l'ordinateur — 22
│   └── images/olive-et-tom/      # 268 PNG — ~12 Mo
│
├── univers/olive-et-tom/
│   ├── index.html                # Sommaire de l'univers (4 cartes d'accès)
│   ├── personnages.html          # Liste (338 l.)
│   ├── personnage.html           # Fiche détail (625 l., JS inline)
│   ├── equipes.html              # Liste des équipes (101 l.)
│   ├── equipe.html               # Fiche équipe (63 l.)
│   ├── techniques.html           # Liste des techniques (88 l.)
│   ├── technique.html            # Fiche technique (64 l.)
│   └── match.html                # Duel : accueil, salon, match, fin (209 l.)
│
├── scripts/                      # Pipeline #2 (modulaire)
│   ├── sync_entities.py          # Orchestrateur (366 l.)
│   ├── build_team_graph.py       # (310 l., non câblé en CI)
│   └── fandom/
│       ├── client.py             # Couche API MediaWiki
│       ├── normalize.py          # Nettoyage, infobox, slugify (294 l.)
│       ├── extract_teams.py      # Extraction + fiches équipes (244 l.)
│       ├── extract_techniques.py # Catalogue + fiches techniques (179 l.)
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

**Volumétrie code** : ~10 200 lignes au total (hors JSON/images), dont ~2 100 Python, ~1 750 HTML/JS front (encyclopédie), ~3 000 pour le duel et ses deux modes (PHP + JS + CSS + HTML) et ~1 450 pour les pages équipes/techniques.

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

**`equipes.json`** : `slug, name, type (club|national|school), age_category, parent_team, url, japanese_name, description, image, players[]`

**`techniques.json`** : `slug, name, url, japanese_name, first_appearance, description, image, users[]`

Les relations sont **bidirectionnelles et dénormalisées** (personnage→équipe *et* équipe→joueurs), et chaque référence embarque déjà son `url` front. Choix pragmatique : zéro jointure côté client, au prix d'une redondance.

### Points d'architecture notables

- **Écriture atomique + garde-fou anti-écrasement** (`writers.py`) : refuse d'écrire si le résultat contient moins de `minimum_items` entrées. Protège contre un JSON vidé par une panne réseau du Fandom. Bonne pratique, à conserver.
- **Score de confiance** (`confidence: low|medium|high`) sur les relations équipes — reconnaissance explicite de l'incertitude de l'extraction heuristique.
- **Stratégie techniques** : les huit catégories du wiki font autorité. Le catalogue amorce `techniques.json`, si bien qu'une technique existe parce que le wiki la recense — et non parce qu'une page la mentionne. Les relations ne retiennent ensuite que les liens présents au catalogue. Cette règle a remplacé une heuristique sur les noms de liens qui produisait 203 faux positifs (voir §1 et `docs/entities-sync.md`).
- **Module ES partagé** (`assets/js/entites.js`) : les quatre pages entités partagent fetch, recherche, tri, empty state et rendu des portraits. Modules natifs, donc aucun build step — la voie à suivre pour dédupliquer `personnages.js` et `personnage.html`.
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

**1. ~~Liens morts vers `equipe.html` et `technique.html`~~ — ✅ résolu (PR #55)**
Les quatre pages existent désormais, et l'intégrité référentielle a été vérifiée dans les quatre sens après régénération : aucune référence orpheline entre les trois JSON. Plus aucun 404 sur les relations.

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

**11. ~~Aucun cache-busting sur les assets~~ — ✅ résolu**
Aucun fichier ne porte de version ni d'empreinte, et sans build step il n'y a pas de moyen d'en apposer une : `style.css` déployé aujourd'hui porte le même nom qu'hier. Sans en-tête explicite, le navigateur appliquait sa propre heuristique — constaté en développement, un ancien `entites.js` resservi pendant plusieurs rechargements, y compris forcés.

Un `.htaccess` à la racine tranche la question sans toucher au HTML : code et données (`html`, `js`, `css`, `json`) se revalident à chaque visite, images et polices se mettent en cache un an. Une revalidation ne coûte qu'un `304` à vide quand rien n'a changé.

**12. ~~Descriptions vides sur les équipes~~ — ✅ résolu**
`equipes.json` avait `description` et `image` à `""` sur les 102 entrées. La description et le nom japonais sont désormais lus (98/102 et 100/102) — voir §1. **Les images restent vides**, sur les équipes comme sur les techniques : `agents.md` interdit le hotlink, et les télécharger est un chantier à part (piste n°6).

**13. ~~Un déploiement pouvait rester sur un commit intermédiaire~~ — ✅ résolu**
Le 6 août, deux PR fusionnées à 28 secondes d'écart n'ont donné qu'un seul déploiement — sur le premier des deux commits. Le mode Équipe est resté invisible en production alors que le workflow était vert, et l'était légitimement : il avait déployé ce qu'on lui avait demandé. `deploy.yml` porte désormais un `concurrency` avec `cancel-in-progress: false`, pour que les déploiements se suivent au lieu de se chevaucher — annuler laisserait justement la production en arrière.

C'est une variante du motif du §8 : rien n'échoue, tout est vert, et pourtant le résultat n'est pas là.

### 🟡 Qualité / perf

**6. Chargement intégral du JSON pour une seule fiche**
`personnage.html` fait `fetch('/assets/data/personnages.json')` (330 Ko) puis un `.find()` pour un seul personnage. Les fiches équipe et technique font de même, et chargent en plus `personnages.json` pour afficher les portraits des personnages liés — soit deux fichiers complets pour une seule fiche. À terme : soit un split par slug, soit un index léger.

**7. Front dupliqué entre pages**
`personnage.html` embarque 330 lignes de JS inline (normalisation des relations, slugify, placeholder) qui recoupent largement `assets/js/personnages.js`. Aucun module partagé. Les ES modules natifs (`<script type="module">`) résoudraient ça sans violer la contrainte « no build step ».

**8. CSS dispersé**
`univers/olive-et-tom/index.html` contient ~90 lignes de `<style>` inline pour le header, non partagées avec les autres pages de l'univers.

**9. Divers**
- Trois `console.log` laissés en production : `personnages.js` l. 414 (`"Sorting mode:"`), et `personnage.html` l. 511-512 (`"[debug] teams"` / `"[debug] techniques"`).
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
| ~~—~~ | ~~Créer `equipe.html` / `technique.html` et les listes~~ — ✅ livré (PR #55) | — | — |
| ~~—~~ | ~~Descriptions des équipes~~ — ✅ livré, images exceptées (piste n°5) | — | — |
| ~~—~~ | ~~Cache des assets~~ et ~~concurrence des déploiements~~ — ✅ livré | — | — |
| 1 | Assertions de qualité en sortie de pipeline (« si moins de X % des entrées ont une description, échouer ») — c'est ce qui aurait détecté les deux angles morts | S | 🔥 Élevé |
| 2 | Réparer ou retirer `update_ct_portraits.py` (cible `personnages.json`, pas le JS) + désactiver le cron en attendant | S | 🔥 Élevé |
| 3 | Mettre à jour `agents.md` : exception PHP du duel, et modules ES désormais utilisés | S | Élevé |
| 4 | Couche de traduction FR (noms, positions, nationalités) conforme à `agents.md` | M | Élevé |
| 5 | Télécharger les visuels d'équipes et de techniques dans `assets/images/`, sans hotlink — seul champ encore vide des deux catalogues | M | Moyen |
| 6 | Migrer `personnages.js` et `personnage.html` vers `assets/js/entites.js` — le module partagé existe déjà | S | Moyen |
| 7 | Nettoyer les assets orphelins + le fichier au nom contenant une tabulation | S | Moyen |
| 8 | Dédupliquer `sync_personnages.py`, supprimer ou réparer `fetch-all-character-images.yml` | S | Moyen |
| 9 | Retirer les trois `console.log` de production | S | Moyen |
| 10 | Ajouter `CONTRIBUTING.md` et un lint minimal (Prettier + Ruff/PHP_CodeSniffer en CI) | S | Moyen |
| 11 | Optimiser le chargement (index léger ou split par slug) | M | Faible aujourd'hui |
| 12 | Compresser les PNG (12 Mo pour 268 fichiers) | S | Faible |

---

## 8. Verdict

**Points forts** — L'architecture est plus réfléchie que la taille du projet ne le laisse supposer : séparation nette données/présentation, pipeline Python modulaire et documenté, garde-fous d'écriture atomique, scores de confiance sur les relations, contraintes de projet explicitées dans `agents.md`. La discipline « zéro dépendance » est réellement tenue des deux côtés de la stack.

**Points faibles** — Le projet a *pivoté* d'un modèle « données dans le JS » vers « données en JSON » sans nettoyer derrière lui. Il en reste des scripts et workflows qui pointent vers l'ancien monde, dont un qui tourne en cron toutes les semaines.

**L'écart front/back est comblé** (PR #55) : les quatre pages entités existent, et le pipeline de techniques a été réparé au passage.

**Le vrai risque, maintenant : les défaillances muettes.** Les bugs des techniques n'ont pas fait de bruit — l'API répondait `200`, le script se terminait sur `[ok]`, la CI était verte, et pourtant 100 % des descriptions étaient vides et deux tiers du catalogue étaient des artefacts. Rien ne l'a signalé pendant des mois.

Ce n'est pas un accident isolé : **le même angle mort existait à un second endroit du pipeline**, sur les équipes, et pour la même raison — la page était chargée, mais personne n'en lisait le contenu. Deux occurrences du même motif dans le même fichier, invisibles l'une comme l'autre. C'est ce qui rend le diagnostic généralisable plutôt qu'anecdotique.

Le pipeline gagnerait des **assertions de qualité en sortie** (« si moins de X % des entrées ont une description, échouer ») bien plus que des tests unitaires. Le garde-fou `minimum_items` de `writers.py` va dans ce sens, mais ne surveille que le volume — jamais la qualité. Un champ vide à 100 % passait sans encombre.

**Le second angle mort est le cache** : sans versionnement des assets, une correction déployée n'atteint pas forcément le visiteur. Un bug corrigé peut donc rester visible en production sans que rien ne l'indique — même famille de problème, autre bout de la chaîne.

**Nouveau depuis le duel (`a7e7d0a`)** — Le projet pivote une seconde fois, cette fois côté infra : d'un site 100 % statique vers un site majoritairement statique avec une brique serveur ciblée. L'implémentation elle-même est propre (autorité serveur, verrouillage de fichier, jetons de session, non-fuite du coup adverse), mais la gouvernance n'a pas suivi : `agents.md` interdit encore, noir sur blanc, ce que le code fait déjà. À corriger avant que d'autres briques serveur n'arrivent sans qu'on ait tranché la question une fois pour toutes.
