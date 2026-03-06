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
- `players`: tableau de pointeurs vers personnages (`slug`, `name`, `url`)

### `assets/data/techniques.json`

- `slug`, `name`, `url`, `description`, `image`
- `users`: tableau de pointeurs vers personnages (`slug`, `name`, `url`)

## Stratégie d'extraction

### Équipes

1. Extraction prioritaire via infobox personnages :
   - `team`, `former_team`, `club`, `current_team`, `national_team`, `youth_team`, etc.
2. Normalisation des noms + dédoublonnage.
3. Construction relation réciproque (`personnages -> équipes`, puis `équipes -> players`).

### Techniques

1. Extraction via champs infobox si présents (`technique`, `special_move`, etc.).
2. Complément robuste via catégories techniques Fandom (`Category:Special Techniques`, etc.).
3. Pour chaque page technique, récupération des liens de page et intersection avec les titres de personnages connus.
4. Construction relation réciproque (`personnages -> techniques`, puis `techniques -> users`).

> Ce choix évite de dépendre uniquement d'heuristiques de sections libres dans les pages personnages.

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
