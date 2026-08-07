<?php
/**
 * Journal de Gaspard — API du duel "Match" (univers Olive et Tom).
 *
 * Serveur autoritatif minimaliste : aucune dépendance, aucun gestionnaire de
 * paquets, aucune base de données. L'état de chaque partie vit dans un fichier
 * JSON sous api/parties/, protégé par un verrou exclusif (flock) pour que deux
 * requêtes simultanées ne puissent pas se marcher dessus.
 *
 * Le client ne fait que déclarer une intention ("je joue tirer"). Toutes les
 * règles sont appliquées ici : impossible de tirer sans munition, de défendre
 * deux fois de suite, ou de jouer à la place de l'adversaire.
 *
 * Compatible PHP 7.4+.
 *
 * ---------------------------------------------------------------------------
 * ENDPOINTS (tous en GET ou POST, réponse JSON)
 *
 *   ?action=creer
 *       → { code, jeton, joueurId, etat }
 *
 *   ?action=rejoindre&code=XXXX
 *       → { code, jeton, joueurId, etat }
 *
 *   ?action=etat&code=XXXX&jeton=...
 *       → { etat }                      (appelé en boucle par le client)
 *
 *   ?action=jouer&code=XXXX&jeton=...&coup=construire|tirer|defendre
 *       → { etat }
 *
 *   ?action=rejouer&code=XXXX&jeton=...
 *       → { etat }
 *
 * Toute erreur renvoie { erreur: "message lisible" } avec un code HTTP 4xx/5xx.
 * ---------------------------------------------------------------------------
 */

declare(strict_types=1);

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Dossier de stockage des parties. Créé automatiquement au premier appel. */
const DOSSIER_PARTIES = __DIR__ . '/parties';

/** Nombre de buts à marquer pour gagner le match. */
const BUTS_POUR_GAGNER = 3;

/** Une partie inactive plus longtemps que ça est supprimée (secondes). */
const DUREE_DE_VIE = 6 * 3600;

/** Alphabet des codes de partie : ni O/0 ni I/1, illisibles à l'oral. */
const ALPHABET_CODE = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

/** Longueur du code de partie. 4 caractères = 1 048 576 combinaisons. */
const LONGUEUR_CODE = 4;

/** Coups autorisés. */
const COUPS = ['construire', 'tirer', 'defendre'];

/** Modes de jeu. Le mode classique est le jeu d'origine, inchangé. */
const MODES = ['classique', 'equipe'];

/** Les trois postes d'une équipe, en mode Équipe. Un personnage par poste. */
const FAMILLES = ['tir', 'construction', 'defense'];

/** Vivier des personnages jouables, généré par scripts/sync_entities.py. */
const FICHIER_ROSTER = __DIR__ . '/../assets/data/duel-roster.json';

/**
 * Coup auquel chaque effet s'attache. Une cartouche de tir se joue sur un tir,
 * une cartouche de défense sur une défense : la famille du poste et le coup se
 * correspondent, ce qui rend la règle explicable sans table de référence.
 */
const COUP_DE_L_EFFET = [
    'frappe' => 'tirer',
    'volee' => 'tirer',
    'une-deux' => 'construire',
    'crochet' => 'construire',
    'parade' => 'defendre',
    'repli' => 'defendre',
];

/**
 * Actions qu'un effet exige d'avoir en réserve pour être joué.
 * Les effets absents de cette table sont gratuits.
 */
const COUT_EFFET = [
    'frappe' => 2,
    'crochet' => 1,
];

/**
 * Actions prélevées en plus de ce que le coup retire déjà dans la matrice.
 * Tirer coûte déjà 1 : « frappe » n'en retire donc qu'une de plus pour ses 2.
 * Construire ne coûte rien : « crochet » prélève son action entière.
 */
const SURCOUT_EFFET = [
    'frappe' => 1,
    'crochet' => 1,
];

// ---------------------------------------------------------------------------
// Sortie HTTP
// ---------------------------------------------------------------------------

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate');

/**
 * Termine la requête en renvoyant du JSON.
 */
function repondre(array $donnees, int $statut = 200): void
{
    http_response_code($statut);
    echo json_encode($donnees, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/**
 * Termine la requête sur une erreur lisible par un humain.
 */
function echouer(string $message, int $statut = 400): void
{
    repondre(['erreur' => $message], $statut);
}

/**
 * Lit un paramètre de requête (GET ou POST), nettoyé.
 */
function parametre(string $nom, string $defaut = ''): string
{
    $valeur = $_POST[$nom] ?? $_GET[$nom] ?? $defaut;

    return is_string($valeur) ? trim($valeur) : $defaut;
}

// ---------------------------------------------------------------------------
// Stockage
// ---------------------------------------------------------------------------

/**
 * Garantit l'existence du dossier de parties et le rend non listable.
 */
function preparerDossier(): void
{
    if (!is_dir(DOSSIER_PARTIES)) {
        @mkdir(DOSSIER_PARTIES, 0775, true);
    }

    if (!is_dir(DOSSIER_PARTIES) || !is_writable(DOSSIER_PARTIES)) {
        echouer("Le serveur ne peut pas écrire dans api/parties/. Vérifiez les droits du dossier.", 500);
    }

    // Empêche la lecture directe des états de partie via le navigateur.
    $htaccess = DOSSIER_PARTIES . '/.htaccess';
    if (!file_exists($htaccess)) {
        @file_put_contents($htaccess, "Require all denied\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n");
    }
}

/**
 * Chemin du fichier d'état pour un code donné.
 */
function cheminPartie(string $code): string
{
    return DOSSIER_PARTIES . '/' . $code . '.json';
}

/**
 * Supprime les parties abandonnées. Déclenché au hasard (1 appel sur 25) pour
 * ne pas payer un parcours de dossier à chaque requête de polling.
 */
function nettoyerParties(): void
{
    if (random_int(1, 25) !== 1) {
        return;
    }

    $fichiers = glob(DOSSIER_PARTIES . '/*.json') ?: [];
    $limite = time() - DUREE_DE_VIE;

    foreach ($fichiers as $fichier) {
        if (@filemtime($fichier) < $limite) {
            @unlink($fichier);
        }
    }
}

/**
 * Ouvre une partie sous verrou exclusif, applique une transformation, et
 * réécrit le résultat. C'est le seul chemin d'écriture : tout passe par ici,
 * donc deux joueurs qui cliquent en même temps sont sérialisés proprement.
 *
 * @param callable $transformation fn(array $partie): array
 */
function modifierPartie(string $code, callable $transformation): array
{
    $chemin = cheminPartie($code);

    if (!file_exists($chemin)) {
        echouer("Cette partie n'existe pas ou a expiré.", 404);
    }

    $flux = fopen($chemin, 'c+');
    if ($flux === false) {
        echouer("Partie illisible.", 500);
    }

    if (!flock($flux, LOCK_EX)) {
        fclose($flux);
        echouer("Partie occupée, réessayez.", 503);
    }

    $brut = stream_get_contents($flux);
    $partie = json_decode($brut !== false ? $brut : '', true);

    if (!is_array($partie)) {
        flock($flux, LOCK_UN);
        fclose($flux);
        echouer("Données de partie corrompues.", 500);
    }

    $partie = $transformation($partie);
    $partie['majLe'] = time();
    $partie['version'] = (int) ($partie['version'] ?? 0) + 1;

    $encode = json_encode($partie, JSON_UNESCAPED_UNICODE);

    ftruncate($flux, 0);
    rewind($flux);
    fwrite($flux, $encode !== false ? $encode : '{}');
    fflush($flux);
    flock($flux, LOCK_UN);
    fclose($flux);

    return $partie;
}

/**
 * Lecture seule, sans verrou d'écriture (le polling n'a pas besoin de bloquer).
 */
function lirePartie(string $code): array
{
    $chemin = cheminPartie($code);

    if (!file_exists($chemin)) {
        echouer("Cette partie n'existe pas ou a expiré.", 404);
    }

    $brut = @file_get_contents($chemin);
    $partie = json_decode($brut !== false ? $brut : '', true);

    if (!is_array($partie)) {
        echouer("Données de partie corrompues.", 500);
    }

    return $partie;
}

// ---------------------------------------------------------------------------
// Vivier du mode Équipe
// ---------------------------------------------------------------------------

/**
 * Charge le vivier des personnages jouables, indexé par slug.
 *
 * Fichier dérivé et compact (~54 Ko) produit par le pipeline, précisément pour
 * n'avoir à charger ici ni personnages.json (330 Ko) ni techniques.json.
 */
function chargerRoster(): array
{
    static $roster = null;

    if ($roster !== null) {
        return $roster;
    }

    $brut = @file_get_contents(FICHIER_ROSTER);
    $donnees = json_decode($brut !== false ? $brut : '', true);

    if (!is_array($donnees) || $donnees === []) {
        echouer("Le vivier des personnages est indisponible.", 500);
    }

    $roster = [];
    foreach ($donnees as $entree) {
        if (isset($entree['slug'])) {
            $roster[(string) $entree['slug']] = $entree;
        }
    }

    return $roster;
}

/**
 * Valide une composition et la réduit à ce que la partie doit retenir.
 *
 * Trois personnages distincts, un par famille, chacun réellement éligible au
 * poste où on l'aligne. Le client propose, le serveur dispose : une équipe
 * fabriquée à la main dans la console est refusée ici.
 *
 * @param array $choix famille => slug
 */
function composerEquipe(array $choix): array
{
    $roster = chargerRoster();
    $equipe = [];
    $vus = [];

    foreach (FAMILLES as $famille) {
        $slug = trim((string) ($choix[$famille] ?? ''));

        if ($slug === '') {
            echouer("Il manque un joueur au poste « {$famille} ».");
        }

        if (isset($vus[$slug])) {
            echouer("Un même personnage ne peut occuper deux postes.");
        }

        $personnage = $roster[$slug] ?? null;

        if ($personnage === null) {
            echouer("Personnage inconnu : {$slug}.");
        }

        $capacite = $personnage['familles'][$famille] ?? null;

        if (!is_array($capacite)) {
            echouer("{$personnage['nom']} n'a aucune technique de « {$famille} ».");
        }

        $vus[$slug] = true;

        $equipe[$famille] = [
            'slug' => $slug,
            'nom' => (string) $personnage['nom'],
            'image' => (string) ($personnage['image'] ?? ''),
            'poste' => (string) ($personnage['poste'] ?? ''),
            'technique' => (string) ($capacite['technique'] ?? ''),
            'effet' => (string) ($capacite['effet'] ?? ''),
            'utilisee' => false,
        ];
    }

    return $equipe;
}

// ---------------------------------------------------------------------------
// Règles du jeu
// ---------------------------------------------------------------------------

/**
 * Résout une manche à partir des deux coups déclarés.
 *
 * Matrice (joueur A / joueur B) :
 *
 *   construire / construire  → chacun gagne 1 point d'action
 *   construire / tirer       → le tireur marque, le constructeur perd son action
 *   construire / défendre    → le constructeur gagne 1 point, le défenseur rien
 *   tirer      / tirer       → les deux frappes se neutralisent, 1 point perdu
 *   tirer      / défendre    → tir bloqué ; le défenseur récupère 1 point
 *   défendre   / défendre    → rien, manche blanche
 *
 * Le "contre-attaque" du défenseur (t/d) est ce qui empêche la défense d'être
 * un simple temps mort : elle rapporte, mais seulement face à un tir. Combiné
 * à l'interdiction de défendre deux fois d'affilée, ça force la prise de risque.
 *
 * @return array{0: array, 1: array, 2: string} [joueurA, joueurB, récit]
 */
function resoudreManche(array $a, array $b): array
{
    $coupA = $a['coup'];
    $coupB = $b['coup'];

    $a['buts'] = (int) $a['buts'];
    $b['buts'] = (int) $b['buts'];
    $a['points'] = (int) $a['points'];
    $b['points'] = (int) $b['points'];

    $recit = '';

    if ($coupA === 'construire' && $coupB === 'construire') {
        $a['points']++;
        $b['points']++;
        $recit = "Les deux équipes construisent tranquillement leur jeu.";
    } elseif ($coupA === 'construire' && $coupB === 'tirer') {
        $b['points']--;
        $b['buts']++;
        $recit = "Contre foudroyant : {B} frappe pendant que {A} relance. But !";
    } elseif ($coupA === 'tirer' && $coupB === 'construire') {
        $a['points']--;
        $a['buts']++;
        $recit = "Contre foudroyant : {A} frappe pendant que {B} relance. But !";
    } elseif ($coupA === 'construire' && $coupB === 'defendre') {
        $a['points']++;
        $recit = "{B} défend dans le vide, {A} en profite pour monter d'un cran.";
    } elseif ($coupA === 'defendre' && $coupB === 'construire') {
        $b['points']++;
        $recit = "{A} défend dans le vide, {B} en profite pour monter d'un cran.";
    } elseif ($coupA === 'tirer' && $coupB === 'tirer') {
        $a['points']--;
        $b['points']--;
        $recit = "Les deux frappes partent en même temps et se croisent. Rien à signaler.";
    } elseif ($coupA === 'tirer' && $coupB === 'defendre') {
        $a['points']--;
        $b['points']++;
        $recit = "{B} sort l'arrêt décisif et relance la contre-attaque.";
    } elseif ($coupA === 'defendre' && $coupB === 'tirer') {
        $b['points']--;
        $a['points']++;
        $recit = "{A} sort l'arrêt décisif et relance la contre-attaque.";
    } else {
        $recit = "Deux blocs bas. Le ballon ne circule pas.";
    }

    $a['points'] = max(0, $a['points']);
    $b['points'] = max(0, $b['points']);

    $a['dernierCoup'] = $coupA;
    $b['dernierCoup'] = $coupB;
    $a['coup'] = null;
    $b['coup'] = null;

    return [$a, $b, $recit];
}

/**
 * Effets encore disponibles pour un joueur, indexés par le coup qui les porte.
 * Une cartouche déjà dépensée ne réapparaît jamais.
 *
 * @return array coup => [effet, ...]
 */
function effetsDisponibles(array $joueur): array
{
    $parCoup = [];

    foreach ($joueur['equipe'] ?? [] as $carte) {
        if (!empty($carte['utilisee'])) {
            continue;
        }

        $effet = (string) ($carte['effet'] ?? '');
        $coup = COUP_DE_L_EFFET[$effet] ?? null;

        if ($coup !== null) {
            $parCoup[$coup][] = $effet;
        }
    }

    return $parCoup;
}

/**
 * Liste les coups légaux pour un joueur donné, dans l'état courant.
 * Le client s'en sert pour griser les boutons ; le serveur s'en sert pour
 * refuser un coup illégal. Une seule source de vérité, deux usages.
 *
 * Deux cartouches lèvent une interdiction plutôt que de modifier une issue :
 * « volee » autorise un tir sans munition, « repli » une seconde défense
 * consécutive. Elles élargissent donc cette liste.
 */
function coupsAutorises(array $joueur): array
{
    $disponibles = effetsDisponibles($joueur);
    $autorises = ['construire'];

    $peutTirer = (int) $joueur['points'] >= 1
        || in_array('volee', $disponibles['tirer'] ?? [], true);

    if ($peutTirer) {
        $autorises[] = 'tirer';
    }

    // Anti-cadenas : on ne peut pas enchaîner deux défenses.
    $peutDefendre = ($joueur['dernierCoup'] ?? null) !== 'defendre'
        || in_array('repli', $disponibles['defendre'] ?? [], true);

    if ($peutDefendre) {
        $autorises[] = 'defendre';
    }

    return $autorises;
}

/**
 * Effets jouables avec un coup donné, une fois leur coût vérifié.
 * Même logique que coupsAutorises : le serveur tranche, le client affiche.
 */
function cartouchesAutorisees(array $joueur, string $coup): array
{
    $points = (int) $joueur['points'];
    $jouables = [];

    foreach (effetsDisponibles($joueur)[$coup] ?? [] as $effet) {
        if ($points >= (COUT_EFFET[$effet] ?? 0)) {
            $jouables[] = $effet;
        }
    }

    return $jouables;
}

/**
 * Applique les effets des cartouches autour d'une manche déjà résolue.
 *
 * La matrice de resoudreManche() n'est jamais modifiée : le mode classique
 * emprunte exactement le même chemin qu'avant. Les effets se contentent de
 * prélever leur surcoût en amont, puis de corriger l'issue en aval.
 *
 * @return array{0: array, 1: array, 2: string}
 */
function resoudreMancheEquipe(array $a, array $b): array
{
    $coupA = (string) $a['coup'];
    $coupB = (string) $b['coup'];
    $effetA = (string) ($a['cartouche'] ?? '');
    $effetB = (string) ($b['cartouche'] ?? '');

    $a['points'] = max(0, (int) $a['points'] - (SURCOUT_EFFET[$effetA] ?? 0));
    $b['points'] = max(0, (int) $b['points'] - (SURCOUT_EFFET[$effetB] ?? 0));

    list($a, $b, $recit) = resoudreManche($a, $b);

    list($a, $b, $recit) = appliquerEffet($a, $b, $coupA, $coupB, $effetA, $recit, porteurDe($a, $effetA));
    list($b, $a, $recit) = appliquerEffet($b, $a, $coupB, $coupA, $effetB, $recit, porteurDe($b, $effetB));

    $a['points'] = max(0, (int) $a['points']);
    $b['points'] = max(0, (int) $b['points']);

    $a = marquerCartoucheUtilisee($a, $effetA);
    $b = marquerCartoucheUtilisee($b, $effetB);

    return [$a, $b, $recit];
}

/**
 * Nom du personnage porteur d'un effet, pour le récit.
 *
 * Les récits nomment le joueur du manga plutôt que « vous » ou « l'adversaire »
 * : outre que c'est plus parlant, ça évite l'accord impossible des marqueurs
 * {A}/{B}, qui deviennent tantôt « Vous », tantôt « L'adversaire ».
 */
function porteurDe(array $joueur, string $effet): string
{
    foreach ($joueur['equipe'] ?? [] as $carte) {
        if ((string) ($carte['effet'] ?? '') === $effet) {
            return (string) ($carte['nom'] ?? '');
        }
    }

    return '';
}

/**
 * Corrige l'issue d'une manche pour un joueur, selon la cartouche qu'il a
 * engagée. « volee » et « repli » n'apparaissent pas ici : elles ont déjà
 * produit leur effet en autorisant un coup autrement interdit.
 */
function appliquerEffet(
    array $moi,
    array $lui,
    string $monCoup,
    string $sonCoup,
    string $effet,
    string $recit,
    string $porteur
): array {
    if ($porteur === '') {
        $porteur = 'Le joueur';
    }

    if ($effet === 'frappe' && $monCoup === 'tirer' && $sonCoup === 'defendre') {
        // La frappe traverse : le but est accordé et la contre-attaque annulée.
        $moi['buts'] = (int) $moi['buts'] + 1;
        $lui['points'] = (int) $lui['points'] - 1;
        $recit = "{$porteur} arme une frappe que rien n'arrête. But !";
    } elseif ($effet === 'crochet' && $monCoup === 'construire' && $sonCoup === 'tirer') {
        // Le crochet efface la frappe adverse sans qu'on ait eu à défendre.
        $lui['buts'] = (int) $lui['buts'] - 1;
        $recit = "{$porteur} efface la frappe d'un crochet et poursuit sa montée.";
    } elseif ($effet === 'une-deux' && $monCoup === 'construire' && $sonCoup !== 'tirer') {
        // Le +1 de la matrice devient +2. Sans gain à doubler, l'effet est nul.
        $moi['points'] = (int) $moi['points'] + 1;
        $recit .= " {$porteur} enchaîne une-deux et prend deux temps d'avance.";
    } elseif ($effet === 'parade' && $monCoup === 'defendre' && $sonCoup === 'tirer') {
        $moi['points'] = (int) $moi['points'] + 1;
        $recit = "{$porteur} claque une parade et relance plein axe.";
    }

    return [$moi, $lui, $recit];
}

/**
 * Retire définitivement du jeu la cartouche engagée.
 */
function marquerCartoucheUtilisee(array $joueur, string $effet): array
{
    if ($effet === '') {
        return $joueur;
    }

    foreach ($joueur['equipe'] ?? [] as $famille => $carte) {
        if (empty($carte['utilisee']) && (string) ($carte['effet'] ?? '') === $effet) {
            $joueur['equipe'][$famille]['utilisee'] = true;
            break;
        }
    }

    $joueur['cartouche'] = null;

    return $joueur;
}

// ---------------------------------------------------------------------------
// Adversaire piloté par le serveur
// ---------------------------------------------------------------------------

/** Part de hasard selon la difficulté : 1 = joue toujours son calcul. */
const DIFFICULTES = [
    'facile' => 0.35,
    'normal' => 0.70,
    'difficile' => 1.0,
];

/** Itérations de regret matching. 300 suffisent amplement sur une 6×6. */
const ITERATIONS_REGRET = 300;

/** Équipes réelles que l'ordinateur peut aligner en mode Équipe. */
const FICHIER_ADVERSAIRES = __DIR__ . '/../assets/data/duel-adversaires.json';

/**
 * Compose l'équipe de l'ordinateur à partir d'une vraie équipe de la série.
 *
 * Affronter « le Japon olympique » ou « Nankatsu » donne un adversaire qui a
 * une identité, là où trois personnages tirés au hasard n'en ont aucune.
 *
 * @return array{0: array, 1: string} la composition, et le nom de l'équipe
 */
function composerEquipeBot(): array
{
    $brut = @file_get_contents(FICHIER_ADVERSAIRES);
    $adversaires = json_decode($brut !== false ? $brut : '', true);

    if (!is_array($adversaires) || $adversaires === []) {
        echouer("Le catalogue des adversaires est indisponible.", 500);
    }

    $equipe = $adversaires[random_int(0, count($adversaires) - 1)];
    $roster = chargerRoster();
    $effectif = $equipe['effectif'];
    shuffle($effectif);

    // Recherche exhaustive plutôt que gloutonne : prendre pour chaque poste le
    // premier joueur venu échouerait dès qu'un titulaire est le seul à couvrir
    // deux postes — cas courant sur les équipes à trois joueurs jouables. Un
    // effectif dépasse rarement vingt noms, le parcours complet est immédiat.
    // L'ordre étant mélangé, la première solution trouvée varie d'une partie
    // à l'autre.
    $choix = trouverComposition($effectif, $roster);

    if ($choix === null) {
        echouer("L'ordinateur n'a pas pu composer son équipe.", 500);
    }

    return [composerEquipe($choix), (string) $equipe['nom']];
}

/**
 * Cherche trois joueurs distincts couvrant les trois postes.
 *
 * @return array|null famille => slug, ou null si l'effectif ne le permet pas
 */
function trouverComposition(array $effectif, array $roster, array $choix = []): ?array
{
    $famille = FAMILLES[count($choix)] ?? null;

    if ($famille === null) {
        return $choix;
    }

    foreach ($effectif as $slug) {
        if (in_array($slug, $choix, true)) {
            continue;
        }

        if (!isset($roster[$slug]['familles'][$famille])) {
            continue;
        }

        $suite = trouverComposition($effectif, $roster, $choix + [$famille => $slug]);

        if ($suite !== null) {
            return $suite;
        }
    }

    return null;
}

/**
 * Note une position du point de vue de $moi. Seul endroit réglé à la main :
 * le bot ne sait pas quoi jouer, il sait seulement reconnaître une bonne
 * position — et laisse le moteur lui dire où chaque coup le mène.
 */
function evaluerEtat(array $moi, array $lui): float
{
    $mesButs = (int) $moi['buts'];
    $sesButs = (int) $lui['buts'];

    if ($mesButs >= BUTS_POUR_GAGNER) {
        return 10000.0;
    }

    if ($sesButs >= BUTS_POUR_GAGNER) {
        return -10000.0;
    }

    $note = 100.0 * ($mesButs - $sesButs);
    $note += 20.0 * ((int) $moi['points'] - (int) $lui['points']);

    // Une cartouche encore en main vaut quelque chose. Sans ce terme, un bot
    // qui ne voit qu'un coup devant lui brûlerait ses trois techniques dans
    // les trois premières manches, faute de raison de les garder.
    $note += 15.0 * (cartouchesRestantes($moi) - cartouchesRestantes($lui));

    // Être à sec juste après avoir défendu ne laisse qu'un coup légal :
    // l'adversaire le sait, la position est donc mauvaise.
    $note -= (int) $moi['points'] === 0 && ($moi['dernierCoup'] ?? null) === 'defendre' ? 20.0 : 0.0;
    $note += (int) $lui['points'] === 0 && ($lui['dernierCoup'] ?? null) === 'defendre' ? 20.0 : 0.0;

    return $note;
}

function cartouchesRestantes(array $joueur): int
{
    $restantes = 0;

    foreach ($joueur['equipe'] ?? [] as $carte) {
        if (empty($carte['utilisee'])) {
            $restantes++;
        }
    }

    return $restantes;
}

/**
 * Énumère les actions légales d'un joueur : un coup, éventuellement porteur
 * d'une cartouche. Réutilise les mêmes règles que le client, ce qui garantit
 * que le bot ne peut pas jouer ce qu'un humain ne pourrait pas jouer.
 *
 * @return array liste de ['coup' => string, 'cartouche' => string]
 */
function actionsPossibles(array $joueur, string $mode): array
{
    $actions = [];

    foreach (coupsAutorises($joueur) as $coup) {
        $actions[] = ['coup' => $coup, 'cartouche' => ''];

        if ($mode !== 'equipe') {
            continue;
        }

        foreach (cartouchesAutorisees($joueur, $coup) as $effet) {
            $actions[] = ['coup' => $coup, 'cartouche' => $effet];
        }
    }

    return $actions;
}

/**
 * Simule chaque paire d'actions et note l'état obtenu, du point de vue du bot.
 *
 * C'est le cœur de l'approche : plutôt que de coder une politique de jeu, on
 * appelle la vraie résolution — qui est pure — et on évalue le résultat. Le
 * mode Équipe ne demande donc aucun code de plus : l'ensemble des actions
 * grandit, la matrice avec.
 */
function matriceGains(array $bot, array $humain, array $sesActions, array $mesActions, string $mode): array
{
    $matrice = [];

    foreach ($mesActions as $i => $mien) {
        foreach ($sesActions as $j => $sien) {
            $a = $bot;
            $b = $humain;
            $a['coup'] = $mien['coup'];
            $a['cartouche'] = $mien['cartouche'] !== '' ? $mien['cartouche'] : null;
            $b['coup'] = $sien['coup'];
            $b['cartouche'] = $sien['cartouche'] !== '' ? $sien['cartouche'] : null;

            list($apresMoi, $apresLui) = $mode === 'equipe'
                ? resoudreMancheEquipe($a, $b)
                : resoudreManche($a, $b);

            $matrice[$i][$j] = evaluerEtat($apresMoi, $apresLui);
        }
    }

    return $matrice;
}

/**
 * Approche l'équilibre d'un jeu matriciel à somme nulle par regret matching.
 *
 * Le duel se joue à coups simultanés : toute stratégie déterministe y est
 * exploitable dès qu'on l'a repérée. Il faut donc une stratégie mixte, et
 * celle-ci se calcule sans dépendance ni solveur linéaire.
 *
 * @return array probabilités, une par action du bot
 */
function regretMatching(array $matrice): array
{
    $nbMiennes = count($matrice);
    $nbSiennes = count($matrice[0] ?? []);

    if ($nbMiennes === 0 || $nbSiennes === 0) {
        return [];
    }

    $regretsMoi = array_fill(0, $nbMiennes, 0.0);
    $regretsLui = array_fill(0, $nbSiennes, 0.0);
    $cumulMoi = array_fill(0, $nbMiennes, 0.0);

    for ($tour = 0; $tour < ITERATIONS_REGRET; $tour++) {
        $moi = strategieDepuisRegrets($regretsMoi);
        $lui = strategieDepuisRegrets($regretsLui);

        foreach ($moi as $i => $p) {
            $cumulMoi[$i] += $p;
        }

        // Valeur de chaque action si l'autre joue sa stratégie courante.
        $valeurMoi = array_fill(0, $nbMiennes, 0.0);
        $valeurLui = array_fill(0, $nbSiennes, 0.0);

        for ($i = 0; $i < $nbMiennes; $i++) {
            for ($j = 0; $j < $nbSiennes; $j++) {
                $valeurMoi[$i] += $lui[$j] * $matrice[$i][$j];
                $valeurLui[$j] -= $moi[$i] * $matrice[$i][$j];
            }
        }

        $attenduMoi = 0.0;
        foreach ($moi as $i => $p) {
            $attenduMoi += $p * $valeurMoi[$i];
        }

        $attenduLui = 0.0;
        foreach ($lui as $j => $p) {
            $attenduLui += $p * $valeurLui[$j];
        }

        for ($i = 0; $i < $nbMiennes; $i++) {
            $regretsMoi[$i] += $valeurMoi[$i] - $attenduMoi;
        }

        for ($j = 0; $j < $nbSiennes; $j++) {
            $regretsLui[$j] += $valeurLui[$j] - $attenduLui;
        }
    }

    // La moyenne des stratégies converge vers l'équilibre, pas la dernière.
    $total = array_sum($cumulMoi);

    if ($total <= 0.0) {
        return array_fill(0, $nbMiennes, 1.0 / $nbMiennes);
    }

    return array_map(static fn ($valeur) => $valeur / $total, $cumulMoi);
}

/** Regrets positifs normalisés, uniforme s'il n'y en a aucun. */
function strategieDepuisRegrets(array $regrets): array
{
    $positifs = array_map(static fn ($r) => max(0.0, $r), $regrets);
    $somme = array_sum($positifs);

    if ($somme <= 0.0) {
        return array_fill(0, count($regrets), 1.0 / max(1, count($regrets)));
    }

    return array_map(static fn ($r) => $r / $somme, $positifs);
}

/** Tire un index au hasard selon une distribution de probabilités. */
function tirerSelon(array $probabilites): int
{
    $seuil = random_int(0, PHP_INT_MAX - 1) / PHP_INT_MAX;
    $cumul = 0.0;

    foreach ($probabilites as $index => $p) {
        $cumul += $p;
        if ($seuil <= $cumul) {
            return (int) $index;
        }
    }

    return count($probabilites) - 1;
}

/**
 * Choisit le coup de l'ordinateur.
 *
 * ⚠️ À n'appeler qu'avec un état où le coup humain n'est PAS encore posé.
 * Le bot doit décider à l'aveugle, comme un joueur : lire le coup d'en face
 * serait indétectable de l'extérieur et rendrait le jeu sans intérêt.
 */
function coupDuBot(array $partie, int $botId): array
{
    $mode = $partie['mode'] ?? 'classique';
    $bot = $partie['joueurs'][$botId];
    $humain = $partie['joueurs'][1 - $botId];

    $mesActions = actionsPossibles($bot, $mode);
    $sesActions = actionsPossibles($humain, $mode);

    if ($mesActions === []) {
        return ['coup' => 'construire', 'cartouche' => ''];
    }

    $part = DIFFICULTES[$bot['difficulte'] ?? 'normal'] ?? DIFFICULTES['normal'];

    // La part de hasard est ce qui rend le bot abordable : au niveau facile,
    // deux coups sur trois sont tirés à l'aveugle.
    if ($sesActions === [] || (random_int(0, 999) / 1000) >= $part) {
        return $mesActions[random_int(0, count($mesActions) - 1)];
    }

    $probabilites = regretMatching(matriceGains($bot, $humain, $sesActions, $mesActions, $mode));

    if ($probabilites === []) {
        return $mesActions[random_int(0, count($mesActions) - 1)];
    }

    return $mesActions[tirerSelon($probabilites)];
}

// ---------------------------------------------------------------------------
// Sérialisation vers le client
// ---------------------------------------------------------------------------

/**
 * Projette l'état de la partie du point de vue d'un joueur.
 *
 * Point critique : tant que la manche n'est pas résolue, le coup en attente de
 * l'adversaire n'est JAMAIS envoyé — sinon il suffirait d'ouvrir l'onglet
 * réseau pour lire le choix d'en face. On n'expose qu'un booléen "a joué".
 * Les jetons des joueurs ne sortent jamais non plus.
 */
function projeter(array $partie, int $moiId): array
{
    $joueurs = $partie['joueurs'];
    $moi = $joueurs[$moiId];
    $adversaire = $joueurs[1 - $moiId] ?? null;

    $mode = $partie['mode'] ?? 'classique';

    // Cartouches jouables, par coup. Le client s'en sert pour proposer, jamais
    // pour décider : actionJouer revalide tout.
    $cartouches = [];
    foreach (COUPS as $coup) {
        $jouables = $mode === 'equipe' ? cartouchesAutorisees($moi, $coup) : [];
        if ($jouables !== []) {
            $cartouches[$coup] = $jouables;
        }
    }

    $vue = [
        'code' => $partie['code'],
        'version' => (int) $partie['version'],
        'statut' => $partie['statut'],
        'mode' => $mode,
        'solo' => !empty($partie['solo']),
        'manche' => (int) $partie['manche'],
        'butsPourGagner' => (int) $partie['butsPourGagner'],
        'joueurId' => $moiId,
        'moi' => [
            'nom' => $moi['nom'],
            'points' => (int) $moi['points'],
            'buts' => (int) $moi['buts'],
            'aJoue' => $moi['coup'] !== null,
            'dernierCoup' => $moi['dernierCoup'],
            'coupsAutorises' => coupsAutorises($moi),
            'cartouchesAutorisees' => $cartouches,
            'equipe' => $moi['equipe'],
            'aCompose' => $moi['equipe'] !== null,
        ],
        'adversaire' => null,
        'derniereManche' => $partie['derniereManche'],
        'vainqueur' => $partie['vainqueur'],
        // Qui a abandonné, le cas échéant : l'écran de fin doit pouvoir le dire
        // plutôt que d'annoncer une victoire au score qui n'a pas eu lieu.
        'abandon' => $partie['abandon'] ?? null,
        'revanche' => [
            'moi' => !empty($moi['revanche']),
            'adversaire' => $adversaire !== null && !empty($adversaire['revanche']),
        ],
    ];

    if ($adversaire !== null) {
        $vue['adversaire'] = [
            'nom' => $adversaire['nom'],
            'points' => (int) $adversaire['points'],
            'buts' => (int) $adversaire['buts'],
            'aJoue' => $adversaire['coup'] !== null,
            'dernierCoup' => $adversaire['dernierCoup'],
            'aCompose' => $adversaire['equipe'] !== null,
            // L'équipe adverse n'est révélée qu'au coup d'envoi : pendant la
            // sélection, la connaître permettrait de composer en réaction.
            // La cartouche qu'il vient d'engager n'est jamais exposée, au même
            // titre que son coup — seul le drapeau "utilisee", posé après
            // résolution, devient public.
            'equipe' => $partie['statut'] === 'selection' ? null : $adversaire['equipe'],
        ];
    }

    return $vue;
}

/**
 * Retrouve l'index du joueur à partir de son jeton secret.
 */
function identifierJoueur(array $partie, string $jeton): int
{
    if ($jeton === '') {
        echouer("Jeton manquant.", 401);
    }

    foreach ($partie['joueurs'] as $index => $joueur) {
        // Le jeton du bot ne sort jamais : personne ne peut donc le présenter,
        // et on l'écarte explicitement plutôt que de compter là-dessus.
        if (empty($joueur['bot']) && hash_equals((string) $joueur['jeton'], $jeton)) {
            return (int) $index;
        }
    }

    echouer("Vous ne faites pas partie de cette partie.", 403);
}

// ---------------------------------------------------------------------------
// Création / jonction
// ---------------------------------------------------------------------------

function genererJeton(): string
{
    return bin2hex(random_bytes(16));
}

function nouveauJoueur(string $nom): array
{
    return [
        'jeton' => genererJeton(),
        'nom' => $nom,
        'points' => 0,
        'buts' => 0,
        'coup' => null,
        'dernierCoup' => null,
        'revanche' => false,
        // Mode Équipe uniquement : composition, et cartouche engagée ce tour.
        'equipe' => null,
        'cartouche' => null,
    ];
}

/**
 * Tire un code libre. On retente tant qu'il y a collision, ce qui n'arrive
 * quasiment jamais avec 1 million de combinaisons et peu de parties actives.
 */
function genererCode(): string
{
    for ($essai = 0; $essai < 40; $essai++) {
        $code = '';
        for ($i = 0; $i < LONGUEUR_CODE; $i++) {
            $code .= ALPHABET_CODE[random_int(0, strlen(ALPHABET_CODE) - 1)];
        }

        if (!file_exists(cheminPartie($code))) {
            return $code;
        }
    }

    echouer("Impossible de générer un code de partie, réessayez.", 500);
}

function actionCreer(): void
{
    $mode = parametre('mode', 'classique');

    if (!in_array($mode, MODES, true)) {
        echouer("Mode de jeu inconnu.");
    }

    $adversaire = parametre('adversaire', 'humain');
    $difficulte = parametre('difficulte', 'normal');

    if (!in_array($adversaire, ['humain', 'ordinateur'], true)) {
        echouer("Type d'adversaire inconnu.");
    }

    if (!isset(DIFFICULTES[$difficulte])) {
        echouer("Difficulté inconnue.");
    }

    $code = genererCode();
    $hote = nouveauJoueur('Joueur 1');

    $partie = [
        'code' => $code,
        'version' => 1,
        'creeLe' => time(),
        'majLe' => time(),
        'statut' => 'attente',
        'mode' => $mode,
        'manche' => 1,
        'butsPourGagner' => BUTS_POUR_GAGNER,
        'joueurs' => [$hote],
        'solo' => $adversaire === 'ordinateur',
        'derniereManche' => null,
        'vainqueur' => null,
        'abandon' => null,
    ];

    // Partie solo : l'ordinateur prend la seconde place tout de suite, il n'y
    // a donc ni code à transmettre ni salon d'attente.
    if ($adversaire === 'ordinateur') {
        $bot = nouveauJoueur('Ordinateur');
        $bot['bot'] = true;
        $bot['difficulte'] = $difficulte;

        if ($mode === 'equipe') {
            list($equipeBot, $nomEquipe) = composerEquipeBot();
            $bot['equipe'] = $equipeBot;
            $bot['nom'] = $nomEquipe;
            $partie['statut'] = 'selection';
        } else {
            $partie['statut'] = 'en-cours';
        }

        $partie['joueurs'][] = $bot;
    }

    $encode = json_encode($partie, JSON_UNESCAPED_UNICODE);
    if (file_put_contents(cheminPartie($code), $encode, LOCK_EX) === false) {
        echouer("Impossible d'enregistrer la partie.", 500);
    }

    repondre([
        'code' => $code,
        'jeton' => $hote['jeton'],
        'joueurId' => 0,
        'etat' => projeter($partie, 0),
    ]);
}

function actionRejoindre(): void
{
    $code = strtoupper(parametre('code'));

    if (!preg_match('/^[A-Z0-9]{' . LONGUEUR_CODE . '}$/', $code)) {
        echouer("Code de partie invalide.");
    }

    $invite = nouveauJoueur('Joueur 2');

    $partie = modifierPartie($code, function (array $partie) use ($invite): array {
        if (!empty($partie['solo'])) {
            echouer("Cette partie se joue contre l'ordinateur.", 409);
        }

        if (count($partie['joueurs']) >= 2) {
            echouer("Cette partie est déjà complète.", 409);
        }

        $partie['joueurs'][] = $invite;

        // En mode Équipe, le match ne démarre qu'une fois les deux
        // compositions déposées.
        $partie['statut'] = ($partie['mode'] ?? 'classique') === 'equipe'
            ? 'selection'
            : 'en-cours';

        return $partie;
    });

    repondre([
        'code' => $code,
        'jeton' => $invite['jeton'],
        'joueurId' => 1,
        'etat' => projeter($partie, 1),
    ]);
}

// ---------------------------------------------------------------------------
// Déroulé du match
// ---------------------------------------------------------------------------

function actionEtat(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');

    $partie = lirePartie($code);
    $moiId = identifierJoueur($partie, $jeton);

    repondre(['etat' => projeter($partie, $moiId)]);
}

/**
 * Dépose la composition d'un joueur. Le match démarre quand les deux sont là.
 */
function actionComposer(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');

    $choix = [];
    foreach (FAMILLES as $famille) {
        $choix[$famille] = parametre($famille);
    }

    $moiId = -1;

    $partie = modifierPartie($code, function (array $partie) use ($jeton, $choix, &$moiId): array {
        $moiId = identifierJoueur($partie, $jeton);

        if (($partie['mode'] ?? 'classique') !== 'equipe') {
            echouer("Cette partie n'est pas en mode Équipe.", 409);
        }

        if ($partie['statut'] !== 'selection') {
            echouer("La composition n'est plus modifiable.", 409);
        }

        if ($partie['joueurs'][$moiId]['equipe'] !== null) {
            echouer("Votre équipe est déjà composée.", 409);
        }

        $partie['joueurs'][$moiId]['equipe'] = composerEquipe($choix);

        $pretes = true;
        foreach ($partie['joueurs'] as $joueur) {
            if ($joueur['equipe'] === null) {
                $pretes = false;
            }
        }

        if ($pretes && count($partie['joueurs']) === 2) {
            $partie['statut'] = 'en-cours';
        }

        return $partie;
    });

    repondre(['etat' => projeter($partie, $moiId)]);
}

function actionJouer(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');
    $coup = parametre('coup');
    $cartouche = parametre('cartouche');

    if (!in_array($coup, COUPS, true)) {
        echouer("Coup inconnu.");
    }

    $moiId = -1;

    $partie = modifierPartie($code, function (array $partie) use ($jeton, $coup, $cartouche, &$moiId): array {
        $moiId = identifierJoueur($partie, $jeton);

        if ($partie['statut'] === 'attente') {
            echouer("En attente d'un second joueur.", 409);
        }

        if ($partie['statut'] === 'selection') {
            echouer("Les équipes ne sont pas encore composées.", 409);
        }

        if ($partie['statut'] === 'termine') {
            echouer("Le match est terminé.", 409);
        }

        $moi = $partie['joueurs'][$moiId];

        if ($moi['coup'] !== null) {
            echouer("Vous avez déjà joué cette manche.", 409);
        }

        if (!in_array($coup, coupsAutorises($moi), true)) {
            echouer("Ce coup n'est pas disponible ce tour-ci.", 409);
        }

        if ($cartouche !== '') {
            if (($partie['mode'] ?? 'classique') !== 'equipe') {
                echouer("Les cartouches n'existent pas en mode classique.", 409);
            }

            if (!in_array($cartouche, cartouchesAutorisees($moi, $coup), true)) {
                echouer("Cette cartouche n'est pas jouable avec ce coup.", 409);
            }
        }

        // ⚠️ ORDRE CRITIQUE — l'ordinateur choisit AVANT que le coup humain ne
        // soit posé. Déplacer ce bloc sous l'affectation suivante lui donnerait
        // accès au coup d'en face : indétectable de l'extérieur, et le jeu
        // n'aurait plus aucun intérêt.
        $adverseId = 1 - $moiId;

        if (!empty($partie['joueurs'][$adverseId]['bot'])
            && $partie['joueurs'][$adverseId]['coup'] === null) {
            $sien = coupDuBot($partie, $adverseId);
            $partie['joueurs'][$adverseId]['coup'] = $sien['coup'];
            $partie['joueurs'][$adverseId]['cartouche'] = $sien['cartouche'] !== ''
                ? $sien['cartouche']
                : null;
        }

        $partie['joueurs'][$moiId]['coup'] = $coup;
        $partie['joueurs'][$moiId]['cartouche'] = $cartouche !== '' ? $cartouche : null;

        // Les deux coups sont posés : on résout et on ouvre la manche suivante.
        if ($partie['joueurs'][0]['coup'] !== null && $partie['joueurs'][1]['coup'] !== null) {
            $coupA = $partie['joueurs'][0]['coup'];
            $coupB = $partie['joueurs'][1]['coup'];
            $cartoucheA = $partie['joueurs'][0]['cartouche'] ?? null;
            $cartoucheB = $partie['joueurs'][1]['cartouche'] ?? null;

            if (($partie['mode'] ?? 'classique') === 'equipe') {
                list($a, $b, $recit) = resoudreMancheEquipe($partie['joueurs'][0], $partie['joueurs'][1]);
            } else {
                list($a, $b, $recit) = resoudreManche($partie['joueurs'][0], $partie['joueurs'][1]);
            }

            $partie['derniereManche'] = [
                'numero' => (int) $partie['manche'],
                'coups' => [$coupA, $coupB],
                'cartouches' => [$cartoucheA, $cartoucheB],
                'recit' => $recit,
                'buts' => [(int) $a['buts'], (int) $b['buts']],
            ];

            $partie['joueurs'][0] = $a;
            $partie['joueurs'][1] = $b;
            $partie['manche'] = (int) $partie['manche'] + 1;

            $objectif = (int) $partie['butsPourGagner'];

            if ((int) $a['buts'] >= $objectif || (int) $b['buts'] >= $objectif) {
                $partie['statut'] = 'termine';
                $partie['vainqueur'] = (int) $a['buts'] > (int) $b['buts'] ? 0 : 1;
            }
        }

        return $partie;
    });

    repondre(['etat' => projeter($partie, $moiId)]);
}

/**
 * Abandonne une partie en cours : l'adversaire l'emporte, le match s'arrête.
 *
 * Sans ça, quitter revenait à disparaître : l'autre restait devant un écran
 * d'attente que rien ne venait clore. Un abandon est donc une fin de match à
 * part entière, distinguée d'une victoire au score par le drapeau `abandon`.
 */
function actionAbandonner(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');
    $moiId = -1;

    $partie = modifierPartie($code, function (array $partie) use ($jeton, &$moiId): array {
        $moiId = identifierJoueur($partie, $jeton);

        if ($partie['statut'] === 'termine') {
            return $partie;
        }

        // Seul en salon : la partie n'a pas commencé, il n'y a rien à concéder.
        if (count($partie['joueurs']) < 2) {
            echouer("La partie n'a pas encore commencé.", 409);
        }

        $partie['statut'] = 'termine';
        $partie['vainqueur'] = 1 - $moiId;
        $partie['abandon'] = $moiId;

        foreach ([0, 1] as $index) {
            $partie['joueurs'][$index]['coup'] = null;
            $partie['joueurs'][$index]['cartouche'] = null;
        }

        return $partie;
    });

    repondre(['etat' => projeter($partie, $moiId)]);
}

function actionRejouer(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');
    $moiId = -1;

    $partie = modifierPartie($code, function (array $partie) use ($jeton, &$moiId): array {
        $moiId = identifierJoueur($partie, $jeton);

        if ($partie['statut'] !== 'termine') {
            echouer("Le match est encore en cours.", 409);
        }

        $partie['joueurs'][$moiId]['revanche'] = true;

        // L'ordinateur ne refuse jamais une revanche : attendre son accord
        // bloquerait la partie pour toujours.
        foreach ($partie['joueurs'] as $index => $joueur) {
            if (!empty($joueur['bot'])) {
                $partie['joueurs'][$index]['revanche'] = true;
            }
        }

        // Les deux joueurs sont d'accord : on remet le score à zéro.
        if (!empty($partie['joueurs'][0]['revanche']) && !empty($partie['joueurs'][1]['revanche'])) {
            foreach ([0, 1] as $index) {
                $partie['joueurs'][$index]['points'] = 0;
                $partie['joueurs'][$index]['buts'] = 0;
                $partie['joueurs'][$index]['coup'] = null;
                $partie['joueurs'][$index]['dernierCoup'] = null;
                $partie['joueurs'][$index]['revanche'] = false;
                $partie['joueurs'][$index]['cartouche'] = null;

                // La revanche se joue avec les mêmes équipes, cartouches
                // refaites. Rouvrir un draft casserait l'élan entre deux
                // manches, et laisser les cartouches dépensées viderait le
                // mode de sa substance.
                foreach ($partie['joueurs'][$index]['equipe'] ?? [] as $famille => $carte) {
                    $partie['joueurs'][$index]['equipe'][$famille]['utilisee'] = false;
                }
            }

            $partie['statut'] = 'en-cours';
            $partie['manche'] = 1;
            $partie['derniereManche'] = null;
            $partie['vainqueur'] = null;
            $partie['abandon'] = null;
        }

        return $partie;
    });

    repondre(['etat' => projeter($partie, $moiId)]);
}

// ---------------------------------------------------------------------------
// Routage
// ---------------------------------------------------------------------------

preparerDossier();
nettoyerParties();

switch (parametre('action')) {
    case 'creer':
        actionCreer();
        break;
    case 'rejoindre':
        actionRejoindre();
        break;
    case 'etat':
        actionEtat();
        break;
    case 'composer':
        actionComposer();
        break;
    case 'jouer':
        actionJouer();
        break;
    case 'abandonner':
        actionAbandonner();
        break;
    case 'rejouer':
        actionRejouer();
        break;
    default:
        echouer("Action inconnue.", 404);
}
