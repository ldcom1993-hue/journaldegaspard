# Duel — jeu en tour par tour à deux joueurs

Duel à distance inspiré du jeu de cour « 007 », transposé au football.
Deux joueurs rejoignent une même partie via un code à quatre caractères et
choisissent leur coup en secret à chaque manche. Premier à trois buts.

Deux modes : **Classique**, le duel d'origine, et **Équipe**, où chacun compose
trois personnages dont les techniques infléchissent le jeu.

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
| `api/partie.php` | API et moteur de règles (~900 l.) |
| `api/parties/` | État des parties, créé à l'exécution — **jamais versionné** |
| `univers/olive-et-tom/match.html` | Les cinq écrans du jeu |
| `assets/js/match.js` | Client : appels API, polling, rendu |
| `assets/css/match.css` | Styles, en extension de `style.css` |

---

## API

Tous les endpoints acceptent GET ou POST et répondent en JSON.
Toute erreur renvoie `{ "erreur": "message lisible" }` avec un code 4xx/5xx —
les messages sont rédigés pour être affichés tels quels au joueur.

| Action | Paramètres | Réponse |
|---|---|---|
| `creer` | `mode` (`classique` \| `equipe`) | `{ code, jeton, joueurId, etat }` |
| `rejoindre` | `code` | `{ code, jeton, joueurId, etat }` |
| `etat` | `code`, `jeton` | `{ etat }` |
| `jouer` | `code`, `jeton`, `coup` | `{ etat }` |
| `composer` | `code`, `jeton`, `tir`, `construction`, `defense` | `{ etat }` |
| `abandonner` | `code`, `jeton` | `{ etat }` |
| `rejouer` | `code`, `jeton` | `{ etat }` |

### Sécurité

- **Le coup adverse en attente n'est jamais sérialisé.** Tant que la manche
  n'est pas résolue, le client ne reçoit qu'un booléen `aJoue`. Sans ça, il
  suffirait d'ouvrir l'onglet réseau pour lire le choix d'en face. La cartouche
  engagée suit la même règle, et l'équipe adverse reste masquée pendant la
  phase `selection` — la connaître permettrait de composer en réaction.
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

### Abandon

Quitter une partie en cours passe par `abandonner` : le match s'achève et
l'adversaire l'emporte. Effacer la session côté client suffirait à s'en aller,
mais laisserait l'autre devant un écran d'attente que rien ne viendrait clore.

L'état porte un drapeau `abandon` avec l'index du joueur parti, pour que
l'écran de fin annonce un abandon plutôt qu'une victoire au score qui n'a pas
eu lieu. La revanche le remet à zéro.

Abandonner seul en salon est refusé : la partie n'a pas commencé, il n'y a rien
à concéder. Abandonner deux fois ne produit ni effet ni erreur.

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

## Le mode Équipe

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

**La technique dépend du poste auquel on aligne le personnage**, pas du
personnage seul. Un personnage est éligible à un poste s'il possède au moins
une technique de cette famille ; il y apporte alors sa technique la plus
personnelle dans cette famille — celle qui compte le moins d'utilisateurs.

Ce n'est pas un détail d'implémentation. Avec une signature fixe par
personnage, la sélection automatique range Wakabayashi en construction avec
« Birdcage », ce qui est un contresens pour le gardien le plus emblématique de
la série ; ici il défend avec « Uppercut Defense ». Les viviers passent au
passage de 32 / 18 / 10 à **54 / 40 / 28**, et 45 personnages sur 60 sont
éligibles à deux familles ou plus — le draft a de vrais arbitrages.

Un personnage ne peut occuper qu'**un seul poste** dans une équipe. La
polyvalence de Tsubasa, éligible partout, se paie donc en choix, jamais en
puissance brute.

Au moment de choisir son coup, un joueur peut y attacher une cartouche encore
disponible. L'effet découle de la sous-catégorie de la technique retenue :

| Sous-catégorie | Famille | Effet | Coût |
|---|---|---|---|
| Ground shots | Tir | Marque même si l'adversaire défend | 2 actions |
| Aerial shots | Tir | Tirer avec 0 action | — |
| Passes, Cooperative tactics, Tactics and skills | Construction | +2 actions au lieu de +1 | — |
| Dribbles and feints | Construction | Annule le tir adverse sans défendre | 1 action |
| Saves | Défense | La défense rapporte 2 actions | — |
| Defensive techniques | Défense | Lève l'interdit de défendre deux manches de suite | — |

### Information cachée

Le mode Classique ne laisse rien filtrer ; le mode Équipe doit tenir la même
ligne.

- Les deux équipes sont **publiques au coup d'envoi**. Sans ça, le draft n'a
  aucun enjeu de lecture.
- La cartouche attachée à un coup reste **secrète jusqu'à la résolution**,
  exactement comme le coup lui-même. Elle ne doit pas être sérialisée avant.
- Les cartouches dépensées deviennent **publiques**. Compter ce qu'il reste à
  l'adversaire fait partie du jeu.

### Mise en œuvre

**Données.** `techniques.json` porte `familles` et `effets`, déduits des
catégories qui servaient déjà à filtrer le catalogue : les retenir ne coûte
aucun appel supplémentaire. `assets/data/duel-roster.json` en dérive — le
vivier du mode, un objet par personnage éligible, avec sa technique et son
effet pour chaque famille. Ce fichier dédié évite au serveur de charger
`personnages.json` (330 Ko) et `techniques.json` à chaque composition.

**Serveur.** Un champ `mode` (`classique` | `equipe`) fixé à la création, un
statut `selection` entre `attente` et `en-cours`, une action `composer`, et par
joueur un champ `equipe` dont chaque carte porte son drapeau `utilisee`.

**La matrice de résolution ne bouge pas.** `resoudreManche()` est appelée telle
quelle ; `resoudreMancheEquipe()` l'enveloppe — surcoût prélevé en amont, issue
corrigée en aval. Une manche de mode Classique suit donc exactement le chemin
d'avant.

`cartouchesAutorisees` accompagne `coupsAutorises` dans la projection : le
client ne décide pas plus de la légalité d'une cartouche que de celle d'un coup.

**Récits.** En mode Équipe, un effet nomme le personnage qui le porte plutôt
que le joueur. Outre que c'est plus parlant, ça évite l'accord impossible des
marqueurs `{A}`/`{B}`, qui valent tantôt « Vous », tantôt « L'adversaire ».

**Revanche.** Elle rejoue avec les mêmes équipes et les cartouches refaites :
rouvrir un draft casserait l'élan entre deux manches, et les laisser dépensées
viderait le mode de sa substance.

### Ajouter un effet

1. `scripts/fandom/extract_techniques.py` → `CATEGORIE_FAMILLE`, puis régénérer
2. `api/partie.php` → `COUP_DE_L_EFFET`, `COUT_EFFET`, `SURCOUT_EFFET`, et le
   cas correspondant dans `appliquerEffet()`
3. `assets/js/match.js` → objet `EFFETS` (libellé et description)

Un effet qui lève une interdiction plutôt que de corriger une issue se traite
dans `coupsAutorises()`, comme `volee` et `repli` — pas dans `appliquerEffet()`.
