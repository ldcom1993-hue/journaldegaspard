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
 * Liste les coups légaux pour un joueur donné, dans l'état courant.
 * Le client s'en sert pour griser les boutons ; le serveur s'en sert pour
 * refuser un coup illégal. Une seule source de vérité, deux usages.
 */
function coupsAutorises(array $joueur): array
{
    $autorises = ['construire'];

    if ((int) $joueur['points'] >= 1) {
        $autorises[] = 'tirer';
    }

    // Anti-cadenas : on ne peut pas enchaîner deux défenses.
    if (($joueur['dernierCoup'] ?? null) !== 'defendre') {
        $autorises[] = 'defendre';
    }

    return $autorises;
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

    $vue = [
        'code' => $partie['code'],
        'version' => (int) $partie['version'],
        'statut' => $partie['statut'],
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
        ],
        'adversaire' => null,
        'derniereManche' => $partie['derniereManche'],
        'vainqueur' => $partie['vainqueur'],
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
        if (hash_equals((string) $joueur['jeton'], $jeton)) {
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
    $code = genererCode();
    $hote = nouveauJoueur('Joueur 1');

    $partie = [
        'code' => $code,
        'version' => 1,
        'creeLe' => time(),
        'majLe' => time(),
        'statut' => 'attente',
        'manche' => 1,
        'butsPourGagner' => BUTS_POUR_GAGNER,
        'joueurs' => [$hote],
        'derniereManche' => null,
        'vainqueur' => null,
    ];

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
        if (count($partie['joueurs']) >= 2) {
            echouer("Cette partie est déjà complète.", 409);
        }

        $partie['joueurs'][] = $invite;
        $partie['statut'] = 'en-cours';

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

function actionJouer(): void
{
    $code = strtoupper(parametre('code'));
    $jeton = parametre('jeton');
    $coup = parametre('coup');

    if (!in_array($coup, COUPS, true)) {
        echouer("Coup inconnu.");
    }

    $moiId = -1;

    $partie = modifierPartie($code, function (array $partie) use ($jeton, $coup, &$moiId): array {
        $moiId = identifierJoueur($partie, $jeton);

        if ($partie['statut'] === 'attente') {
            echouer("En attente d'un second joueur.", 409);
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

        $partie['joueurs'][$moiId]['coup'] = $coup;

        // Les deux coups sont posés : on résout et on ouvre la manche suivante.
        if ($partie['joueurs'][0]['coup'] !== null && $partie['joueurs'][1]['coup'] !== null) {
            $coupA = $partie['joueurs'][0]['coup'];
            $coupB = $partie['joueurs'][1]['coup'];

            list($a, $b, $recit) = resoudreManche($partie['joueurs'][0], $partie['joueurs'][1]);

            $partie['derniereManche'] = [
                'numero' => (int) $partie['manche'],
                'coups' => [$coupA, $coupB],
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

        // Les deux joueurs sont d'accord : on remet le score à zéro.
        if (!empty($partie['joueurs'][0]['revanche']) && !empty($partie['joueurs'][1]['revanche'])) {
            foreach ([0, 1] as $index) {
                $partie['joueurs'][$index]['points'] = 0;
                $partie['joueurs'][$index]['buts'] = 0;
                $partie['joueurs'][$index]['coup'] = null;
                $partie['joueurs'][$index]['dernierCoup'] = null;
                $partie['joueurs'][$index]['revanche'] = false;
            }

            $partie['statut'] = 'en-cours';
            $partie['manche'] = 1;
            $partie['derniereManche'] = null;
            $partie['vainqueur'] = null;
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
    case 'jouer':
        actionJouer();
        break;
    case 'rejouer':
        actionRejouer();
        break;
    default:
        echouer("Action inconnue.", 404);
}
