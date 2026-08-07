# Enrichissement des entités (équipes / techniques)

## Arborescence cible

```text
scripts/
  sync_entities.py
  fandom/
    client.py
    normalize.py
    extract_teams.py
    extract_techniques.py
    relations.py
    writers.py
```

## Rôle des modules

- `scripts/sync_entities.py` : script principal indépendant qui lit `personnages.json`, récupère les relations Fandom, enrichit les personnages, puis génère `equipes.json` et `techniques.json`.
- `scripts/fandom/client.py` : appels API MediaWiki/Fandom (catégories, wikitext, liens, extraits).
- `scripts/fandom/normalize.py` : nettoyage texte, extraction infobox et normalisation des slugs.
- `scripts/fandom/extract_teams.py` : extraction des équipes depuis les champs infobox prioritaires.
- `scripts/fandom/extract_techniques.py` : extraction des techniques (infobox + catégories dédiées) et reconstruction des utilisateurs via les liens des pages techniques.
- `scripts/fandom/relations.py` : construction des objets liés `{ slug, name, url }` pour frontend statique.
- `scripts/fandom/writers.py` : écriture JSON atomique avec garde-fous anti-écrasement vide.

## Schémas cibles

### `assets/data/personnages.json`

Chaque personnage conserve ses champs existants (`slug`, `name`, `image`, `popularity`, `popularityRank`, etc.) et reçoit :

- `teams`: tableau compatible frontend contenant des objets `{ slug, name, url }`.
- `techniques`: tableau d'objets `{ slug, name, url }`.

### `assets/data/equipes.json`

- `slug`, `name`, `url`, `description`, `image`
- `japanese_name` : nom en kana/kanji, isolé du champ `name` de l'infobox
- `players`: tableau de pointeurs vers personnages (`slug`, `name`, `url`)

### `assets/data/techniques.json`

- `slug`, `name`, `url`, `description`, `image`
- `japanese_name` : nom en kana/kanji, isolé du champ `name` de l'infobox
- `first_appearance` : œuvre et chapitre, souvent vide côté wiki
- `familles` : familles de jeu du duel (`tir`, `construction`, `defense`) —
  une technique peut en relever de deux
- `effets` : `{ famille: effet }`, déduit de la sous-catégorie
- `users`: tableau de pointeurs vers personnages (`slug`, `name`, `url`)

### `assets/data/duel-roster.json`

Fichier dérivé, dédié au mode Équipe du duel (voir `jeu-duel.md`). Un objet par
personnage possédant au moins une technique rattachée à une famille.

- `slug`, `nom`, `image`, `poste`
- `familles` : `{ famille: { technique, slug, effet, description } }`

Pour chaque famille, on retient la technique la plus **personnelle** du
personnage — celle qui compte le moins d'utilisateurs. La rareté sert donc de
courbe de puissance sans donnée supplémentaire.

La technique dépend du poste, non du personnage seul : Wakabayashi défend avec
« Uppercut Defense » mais construirait avec « Birdcage ». Une signature unique
par personnage le rangerait en construction, ce qui est un contresens pour un
gardien.

Ce fichier évite au serveur du duel de charger `personnages.json` (330 Ko) et
`techniques.json` à chaque composition d'équipe.

### `assets/data/duel-adversaires.json`

Les équipes réelles que l'ordinateur peut aligner en mode Équipe : `slug`,
`nom`, `type` et `effectif` (les membres présents au vivier).

Une équipe n'est retenue que si trois de ses joueurs distincts couvrent les
trois familles — 22 des 102. Presque toutes les écartées le sont faute de trois
personnages jouables, et non par déséquilibre des familles.

## Stratégie d'extraction

### Équipes

1. Extraction prioritaire via infobox personnages :
   - `team`, `former_team`, `club`, `current_team`, `national_team`, `youth_team`, etc.
2. Normalisation des noms + dédoublonnage.
3. Construction relation réciproque (`personnages -> équipes`, puis `équipes -> players`).
4. Fiche de chaque équipe (`fetch_team_details`) : introduction et nom japonais.

> La page d'une équipe n'était consultée que pour vérifier l'appartenance d'un
> joueur, jamais pour son contenu — `description` et `image` restaient donc
> vides sur les 102 entrées. Même angle mort que côté techniques, même
> correctif. Une page sans introduction exploitable (homonymie, simple liste)
> laisse la description vide, et la fiche la tait.

### Techniques

**Le catalogue des catégories du wiki fait autorité.** Une technique existe
parce que le wiki la recense dans l'une de ces huit catégories, jamais parce
qu'une page la mentionne :

`Ground shots`, `Aerial shots`, `Dribbles and feints`, `Cooperative tactics`,
`Defensive techniques`, `Passes`, `Saves`, `Tactics and skills`.

1. Construction du catalogue (`fetch_technique_catalog`), sous-pages exclues
   (`Drive Shot/Variations` est une annexe, pas une technique).
2. Amorçage de `techniques.json` depuis ce catalogue : une technique que
   nulle page ne cite existe quand même, avec `users` vide.
3. Relations : parcours des pages `<Personnage>/Techniques`, dont on ne retient
   que les liens présents au catalogue.
4. Fiche de chaque technique (`fetch_technique_details`) : introduction, nom
   japonais, première apparition.

> Le filtrage par catalogue a remplacé une heuristique sur les noms de liens.
> Celle-ci retenait tout lien « à l'allure de technique » figurant sur une page
> `/Techniques`, où voisinent coéquipiers, clubs et tomes du manga : sur 304
> entrées produites, 203 n'étaient pas des techniques (`AC Reggiana`,
> `Captain Tsubasa (1981)`), et 55 vraies techniques manquaient. Le nom du
> template ne permet pas de trancher — une technique utilise
> `Infobox character`, comme un personnage.

> Limite connue : une technique réelle mais non catégorisée sur le wiki est
> absente du catalogue (`Back-Heel Pass`). Le correctif est à porter en amont,
> sur le wiki.

### Description des pages

Ce wiki n'a pas l'extension **TextExtracts** : `prop=extracts` y répond `200`
en signalant un paramètre inconnu, sans lever d'erreur — les descriptions
étaient donc vides sur la totalité du catalogue, silencieusement. Elles sont
désormais lues sur le HTML rendu (`action=parse&prop=text`), dont on prend le
premier paragraphe utile (`first_paragraph_from_html`).

## Robustesse / sécurité

- Écriture atomique via fichier temporaire + remplacement.
- Validation minimale avant écriture (`minimum_items`) pour éviter d'écraser les JSON en cas d'échec distant.
- Logs explicites (`[info]`, `[warn]`, `[ok]`).
- Si une partie de collecte échoue, le script continue en best-effort sans suppression massive.

## Intégration workflow existant

Exécution locale manuelle après `sync_personnages.py` :

```bash
python sync_personnages.py
python scripts/sync_entities.py
```

Ce flux reste incrémental et conserve le pipeline actuel.
