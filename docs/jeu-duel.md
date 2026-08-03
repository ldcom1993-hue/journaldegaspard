# Duel — jeu en tour par tour à deux joueurs

Duel à distance inspiré du jeu de cour « 007 », transposé au football.
Deux joueurs rejoignent une même partie via un code à quatre caractères et
choisissent leur coup en secret à chaque manche. Premier à trois buts.

Page : `/univers/olive-et-tom/match.html`

---

## Règles

Trois coups, révélés simultanément.

| Coup | Effet | Contrainte |
|---|---|---|
| **Construire** | +1 action | — |
| **Tirer au but** | −1 action, marque si l'adversaire construisait | Nécessite ≥ 1 action |
| **Défendre** | Bloque un tir et rapporte +1 action | Interdit deux manches de suite |

### Matrice de résolution

|  | Construire | Tirer | Défendre |
|---|---|---|---|
| **Construire** | +1 / +1 | 0 / **but** | +1 / 0 |
| **Tirer** | **but** / 0 | −1 / −1 | −1 / +1 |
| **Défendre** | 0 / +1 | +1 / −1 | 0 / 0 |

Deux choix d'équilibrage méritent d'être explicités, parce qu'ils ne sont pas
dans le 007 d'origine :

- **La défense rapporte une action face à un tir** (« contre-attaque »). Sans
  ça, défendre n'est qu'un temps mort et le jeu se résume à construire/tirer.
- **On ne peut pas défendre deux manches de suite.** Sans ça, un joueur en tête
  pourrait se cadenasser. Combiné au point précédent, ça force la prise de
  risque : un joueur à 0 action qui vient de défendre n'a plus qu'un seul coup
  légal, et l'adversaire le sait.

Le score de 3 buts amortit la variance : un seul coup de chance ne suffit pas.

---

## Architecture

```
Navigateur A ──┐
               ├──► api/partie.php ──► api/parties/{CODE}.json
Navigateur B ──┘      (autoritatif)      (flock, verrou exclusif)
```

Le serveur détient **toutes** les règles. Le client n'envoie qu'une intention
(« je joue tirer ») et se contente d'afficher l'état renvoyé. Il ne calcule
jamais un score ni la légalité d'un coup.

### Pourquoi ce choix

| Contrainte | Conséquence |
|---|---|
| `agents.md` interdit npm, build step et dépendances | PHP nu, JS vanilla, zéro paquet |
| Hébergement mutualisé OVH (FTP) | PHP disponible nativement, pas de WebSocket |
| Jeu tour par tour | Le polling suffit largement, pas besoin de temps réel |

C'est la seule entorse à `agents.md` : le projet cesse d'être 100 % statique.
En échange, aucun service tiers, aucun compte externe, aucune dépendance —
l'esprit de la charte est préservé même si sa lettre ne l'est pas.

### Fichiers

| Fichier | Rôle |
|---|---|
| `api/partie.php` | API et moteur de règles (~450 l.) |
| `api/parties/` | État des parties, créé à l'exécution — **jamais versionné** |
| `univers/olive-et-tom/match.html` | Les quatre écrans du jeu |
| `assets/js/match.js` | Client : appels API, polling, rendu |
| `assets/css/match.css` | Styles, en extension de `style.css` |

---

## API

Tous les endpoints acceptent GET ou POST et répondent en JSON.
Toute erreur renvoie `{ "erreur": "message lisible" }` avec un code 4xx/5xx —
les messages sont rédigés pour être affichés tels quels au joueur.

| Action | Paramètres | Réponse |
|---|---|---|
| `creer` | — | `{ code, jeton, joueurId, etat }` |
| `rejoindre` | `code` | `{ code, jeton, joueurId, etat }` |
| `etat` | `code`, `jeton` | `{ etat }` |
| `jouer` | `code`, `jeton`, `coup` | `{ etat }` |
| `rejouer` | `code`, `jeton` | `{ etat }` |

### Sécurité

- **Le coup adverse en attente n'est jamais sérialisé.** Tant que la manche
  n'est pas résolue, le client ne reçoit qu'un booléen `aJoue`. Sans ça, il
  suffirait d'ouvrir l'onglet réseau pour lire le choix d'en face.
- **Jeton secret par joueur** (16 octets aléatoires), comparé en `hash_equals`.
  Connaître le code de partie ne permet pas de jouer à la place de l'autre.
- **Les jetons ne sortent jamais** dans les projections d'état.
- **Verrou exclusif** (`flock`) sur toute écriture : deux clics simultanés sont
  sérialisés, pas de manche résolue deux fois.
- `api/parties/.htaccess` (généré automatiquement) bloque la lecture directe
  des fichiers d'état.
- Codes de partie sans `O`/`0` ni `I`/`1` — dictables à l'oral sans ambiguïté.
- Purge automatique des parties inactives depuis 6 h, déclenchée au hasard sur
  1 requête sur 25 pour ne pas parcourir le dossier à chaque polling.

---

## Installation

1. Déployer normalement (le workflow `deploy.yml` pousse `api/` automatiquement).
2. Vérifier que **PHP est actif** sur l'hébergement.
3. Vérifier que le dossier `api/` est **inscriptible** par PHP — le script crée
   `api/parties/` tout seul au premier appel. S'il n'y arrive pas, l'API renvoie
   un message explicite plutôt que d'échouer silencieusement.

### Tester en local

```bash
php -S localhost:8000        # depuis la racine du dépôt
# → http://localhost:8000/univers/olive-et-tom/match.html
```

Ouvrir deux fenêtres (dont une en navigation privée, sinon les deux joueurs
partagent le même `localStorage`), créer un match dans l'une, rejoindre avec le
code dans l'autre.

---

## Réglages

En haut de `api/partie.php` :

| Constante | Défaut | Effet |
|---|---|---|
| `BUTS_POUR_GAGNER` | `3` | Longueur du match |
| `DUREE_DE_VIE` | `6 * 3600` | Péremption d'une partie inactive |
| `LONGUEUR_CODE` | `4` | Longueur du code de partie |

Dans `assets/js/match.js` : `DELAI_POLLING` (1500 ms). Ne pas descendre sous
1 000 ms sur un mutualisé.

---

## Ajouter un coup

Quatre endroits, dans cet ordre :

1. `api/partie.php` → constante `COUPS`
2. `api/partie.php` → `resoudreManche()` (la matrice) et `coupsAutorises()`
3. `assets/js/match.js` → objet `COUPS` (libellé + icône)
4. `match.html` → un bouton `[data-coup="…"]`, et `match.css` → sa couleur

Le reste suit : les boutons sont activés d'après `coupsAutorises` renvoyé par
le serveur, jamais d'après une règle codée côté client.

---

## V2 envisagée — personnages et techniques

Le dépôt contient déjà 235 personnages et 304 techniques avec leurs relations
(`assets/data/personnages.json`, `techniques.json`), qui ne sont affichés nulle
part. Piste : chaque joueur choisit un personnage avant le match, et sa
technique signature modifie la matrice.

- Drive Shoot (Tsubasa) — coûte 3 actions, traverse une défense
- Tigre Shoot (Hyuga) — coûte 2 actions, marque même sur un tir adverse
- Parade de Wakabayashi — la défense rapporte 2 actions au lieu d'1

Chaque personnage aurait une seule technique, utilisable une fois par match.
Ça transforme un pierre-feuille-ciseaux symétrique en jeu de bluff asymétrique,
et ça donne enfin un usage aux données de techniques.

**Prérequis technique** : ajouter un champ `personnage` par joueur dans l'état
serveur, et une phase `selection` avant `en-cours`. La matrice reste dans
`resoudreManche()`, avec les techniques appliquées en surcouche.
