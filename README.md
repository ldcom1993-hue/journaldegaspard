# journaldegaspard

Site encyclopédique organisé en univers fictionnels.
En production : https://journaldegaspard.fr/

Un seul univers est implémenté, **Olive et Tom** (*Captain Tsubasa*) : 235
personnages, 102 équipes et 155 techniques, moissonnés depuis le Fandom et
servis en JSON statiques. S'y ajoute un **duel à deux joueurs en ligne**.

HTML, CSS et JavaScript vanilla, sans framework ni build step. Voir `agents.md`
pour les contraintes qui s'imposent à toute contribution.

## Lancer le site en local

```bash
php -S localhost:8000
```

`php` plutôt que `python3 -m http.server` : le duel a besoin de PHP. Pour les
seules pages encyclopédiques, un serveur statique suffit — mais pas
l'ouverture en `file://`, les `fetch()` utilisant des chemins absolus.

## Synchronisation des données Fandom

```bash
python sync_personnages.py
python scripts/sync_entities.py
```

- `sync_personnages.py` : collecte de base des personnages.
- `scripts/sync_entities.py` : enrichissement équipes/techniques, et génération
  de `equipes.json`, `techniques.json` et `duel-roster.json` (le vivier du mode
  Équipe du duel).

## Documentation

| Document | Sujet |
|---|---|
| `agents.md` | Règles impératives pour toute contribution |
| `docs/ANALYSE-PROJET.md` | Architecture, dette technique, pistes de contribution |
| `docs/entities-sync.md` | Pipeline de données : stratégie d'extraction et formats |
| `docs/jeu-duel.md` | Duel : règles des deux modes, API, sécurité |
