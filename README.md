# journaldegaspard

Journal de Gaspard.

## Synchronisation des données Fandom

```bash
python sync_personnages.py
python scripts/sync_entities.py
```

- `sync_personnages.py` : collecte de base des personnages.
- `scripts/sync_entities.py` : enrichissement équipes/techniques et génération de `equipes.json` + `techniques.json`.

Voir `docs/entities-sync.md` pour les détails d'architecture et de format.
