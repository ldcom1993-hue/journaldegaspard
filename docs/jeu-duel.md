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

## V2 conçue — le mode Équipe

Le mode actuel devient **Classique** et ne bouge pas. À côté, un mode **Équipe**
où chaque joueur compose une équipe de trois personnages avant le coup d'envoi,
et où les techniques de ces personnages infléchissent le déroulement.

### Les trois familles

Les catégories du wiki, qui servent déjà à constituer le catalogue de
techniques (voir `entities-sync.md`), se projettent directement sur les trois
coups du jeu :

| Catégories wiki | Famille |
|---|---|
| Ground shots, Aerial shots | **Tir** |
| Passes, Dribbles and feints, Cooperative tactics, Tactics and skills | **Construction** |
| Saves, Defensive techniques | **Défense** |

### Composition

**Trois personnages, un par famille.** La contrainte n'est pas cosmétique :
sur les 155 techniques, 101 relèvent du tir contre 16 de la défense. Sans elle,
personne ne prendrait jamais de défenseur et le mode se réduirait à une course
au tir. Elle transforme la faiblesse du corpus en décision de jeu.

Le vivier est de **60 personnages** — ceux qui ont au moins une technique. Les
175 autres n'apporteraient qu'un nom.

Aucune contrainte de poste pour l'instant : un gardien n'est pas obligatoire.
Les postes restent affichés, à titre indicatif.

**Draft simultané et secret, doublons autorisés entre les deux joueurs.** Trois
raisons : tout est déjà simultané et caché dans ce jeu ; il n'y a pas d'ordre de
tour à gérer ; et surtout, avec une dizaine de personnages défensifs jouables,
l'exclusivité rendrait la contrainte de composition intenable à deux.

### Les techniques en jeu

**Chaque personnage est une cartouche, utilisable une fois par match.** Une
équipe de trois donne donc trois techniques sur l'ensemble de la partie.

Un personnage n'apporte qu'**une seule technique**, sa signature, quel que soit
son arsenal. C'est ce qui empêche Tsubasa et ses 38 techniques d'être un choix
automatique. Sa polyvalence peut se traduire autrement — sa carte jouable dans
deux familles, par exemple — mais jamais en volume.

Au moment de choisir son coup, un joueur peut y attacher une cartouche encore
disponible.

| Famille | Effet | Coût |
|---|---|---|
| **Tir** | Marque même si l'adversaire défend | 2 actions |
| **Tir** | Tirer avec 0 action | — |
| **Construction** | +2 actions au lieu de +1 | — |
| **Construction** | Esquive : annule le tir adverse sans défendre | 1 action |
| **Défense** | Lève l'interdit de défendre deux manches de suite | — |
| **Défense** | La défense rapporte 2 actions | — |

### Information cachée

Le mode Classique ne laisse rien filtrer ; le mode Équipe doit tenir la même
ligne.

- Les deux équipes sont **publiques au coup d'envoi**. Sans ça, le draft n'a
  aucun enjeu de lecture.
- La cartouche attachée à un coup reste **secrète jusqu'à la résolution**,
  exactement comme le coup lui-même. Elle ne doit pas être sérialisée avant.
- Les cartouches dépensées deviennent **publiques**. Compter ce qu'il reste à
  l'adversaire fait partie du jeu.

### Prérequis

**Côté données** — deux champs manquent aujourd'hui à `techniques.json` :

- `famille` : les catégories ont servi à filtrer le catalogue, puis ont été
  jetées. Il faut les conserver.
- la **technique signature** d'un personnage. Le wiki la marque via une
  catégorie `<Personnage> pages` (`Tiger Shot` → `Kojiro Hyuga pages`), mais
  seulement pour 28 personnages. Repli pour les autres : la technique ayant le
  moins d'utilisateurs, donc la plus personnelle. Le champ `users` fournit au
  passage une courbe de puissance gratuite — une technique partagée par vingt
  personnages est banale, une exclusive est forte.

**Côté serveur** — un champ `mode` (`classique` | `equipe`) dans l'état, fixé à
la création et affiché dans le salon ; une phase `selection` entre `salon` et
`en-cours` ; un champ `equipe` et un champ `cartouchesDepensees` par joueur.

**La matrice de résolution ne bouge pas.** Les techniques s'appliquent en
surcouche, après elle, dans `resoudreManche()`. C'est ce qui garantit que le
mode Classique reste littéralement le code d'aujourd'hui.

Enfin, `techniquesAutorisees` doit accompagner `coupsAutorises` dans la
projection d'état : le client ne doit pas plus décider de la légalité d'une
cartouche que de celle d'un coup.
