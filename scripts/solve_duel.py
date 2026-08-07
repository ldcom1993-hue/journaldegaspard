#!/usr/bin/env python3
"""
Étalon de qualité pour l'adversaire du duel — mode classique.

Ce script ne fait pas partie du site : `scripts/` est exclu du déploiement.
Il ne sert qu'à répondre à une question qu'aucune observation ne tranche —
« le bot joue-t-il bien ? » — par un chiffre plutôt qu'une impression.

Le mode classique est assez petit pour être résolu exactement : quelques
milliers d'états seulement. On calcule donc l'équilibre du jeu par itération
de valeur, puis on fait jouer le bot de production contre ce joueur parfait.

Un bot qui perd de peu est bon : contre un adversaire optimal, personne ne
gagne. C'est l'ampleur de l'écart qui renseigne, et comme le mode Équipe
emploie exactement le même algorithme, ce qui vaut ici vaut là-bas.

    python scripts/solve_duel.py            # résout et mesure
    python scripts/solve_duel.py --parties 200

Le serveur doit tourner : php -S localhost:8100
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

COUPS = ("construire", "tirer", "defendre")
BUTS_POUR_GAGNER = 3

# Au-delà, une action de plus ne change plus rien à la conduite du jeu : le
# plafond garde l'espace d'états fini sans fausser la solution.
PLAFOND_ACTIONS = 6


# ---------------------------------------------------------------------------
# Les règles, transcrites depuis api/partie.php
# ---------------------------------------------------------------------------

def coups_legaux(points: int, a_defendu: bool) -> tuple[str, ...]:
    legaux = ["construire"]
    if points >= 1:
        legaux.append("tirer")
    if not a_defendu:
        legaux.append("defendre")
    return tuple(legaux)


def resoudre(etat: tuple, coup_a: str, coup_b: str) -> tuple:
    """Miroir exact de resoudreManche(). Renvoie l'état suivant."""
    pa, pb, ba, bb, _, _ = etat

    if coup_a == "construire" and coup_b == "construire":
        pa, pb = pa + 1, pb + 1
    elif coup_a == "construire" and coup_b == "tirer":
        pb, bb = pb - 1, bb + 1
    elif coup_a == "tirer" and coup_b == "construire":
        pa, ba = pa - 1, ba + 1
    elif coup_a == "construire" and coup_b == "defendre":
        pa += 1
    elif coup_a == "defendre" and coup_b == "construire":
        pb += 1
    elif coup_a == "tirer" and coup_b == "tirer":
        pa, pb = pa - 1, pb - 1
    elif coup_a == "tirer" and coup_b == "defendre":
        pa, pb = pa - 1, pb + 1
    elif coup_a == "defendre" and coup_b == "tirer":
        pb, pa = pb - 1, pa + 1

    return (
        min(PLAFOND_ACTIONS, max(0, pa)),
        min(PLAFOND_ACTIONS, max(0, pb)),
        min(BUTS_POUR_GAGNER, ba),
        min(BUTS_POUR_GAGNER, bb),
        coup_a == "defendre",
        coup_b == "defendre",
    )


def termine(etat: tuple) -> int | None:
    """+1 si A a gagné, -1 si B a gagné, None sinon."""
    _, _, ba, bb, _, _ = etat
    if ba >= BUTS_POUR_GAGNER:
        return 1
    if bb >= BUTS_POUR_GAGNER:
        return -1
    return None


def tous_les_etats() -> list[tuple]:
    return [
        (pa, pb, ba, bb, da, db)
        for pa in range(PLAFOND_ACTIONS + 1)
        for pb in range(PLAFOND_ACTIONS + 1)
        for ba in range(BUTS_POUR_GAGNER)
        for bb in range(BUTS_POUR_GAGNER)
        for da in (False, True)
        for db in (False, True)
    ]


# ---------------------------------------------------------------------------
# Résolution
# ---------------------------------------------------------------------------

def valeur_du_jeu_matriciel(matrice: list[list[float]], iterations: int = 800):
    """
    Équilibre d'un jeu matriciel à somme nulle, par regret matching.

    Même méthode que le bot de production, poussée bien plus loin en
    itérations : ici on cherche la précision, pas la vitesse.
    """
    n, m = len(matrice), len(matrice[0])
    regrets_a = [0.0] * n
    regrets_b = [0.0] * m
    cumul_a = [0.0] * n
    valeur = 0.0

    def strategie(regrets):
        positifs = [max(0.0, r) for r in regrets]
        somme = sum(positifs)
        return [p / somme for p in positifs] if somme > 0 else [1.0 / len(regrets)] * len(regrets)

    for _ in range(iterations):
        sa, sb = strategie(regrets_a), strategie(regrets_b)
        for i in range(n):
            cumul_a[i] += sa[i]

        val_a = [sum(sb[j] * matrice[i][j] for j in range(m)) for i in range(n)]
        val_b = [-sum(sa[i] * matrice[i][j] for i in range(n)) for j in range(m)]
        att_a = sum(sa[i] * val_a[i] for i in range(n))
        att_b = sum(sb[j] * val_b[j] for j in range(m))
        valeur = att_a

        for i in range(n):
            regrets_a[i] += val_a[i] - att_a
        for j in range(m):
            regrets_b[j] += val_b[j] - att_b

    total = sum(cumul_a)
    politique = [c / total for c in cumul_a] if total > 0 else [1.0 / n] * n
    return valeur, politique


def resoudre_le_jeu(passes: int = 12) -> dict[tuple, list[float]]:
    """
    Itération de valeur. Chaque passe résout le petit jeu matriciel de chaque
    état, en s'appuyant sur les valeurs de la passe précédente.
    """
    etats = tous_les_etats()
    valeurs = {e: 0.0 for e in etats}
    politiques: dict[tuple, list[float]] = {}

    for passe in range(passes):
        nouvelles = {}
        for etat in etats:
            pa, pb, _, _, da, db = etat
            mes_coups = coups_legaux(pa, da)
            ses_coups = coups_legaux(pb, db)

            matrice = []
            for ca in mes_coups:
                ligne = []
                for cb in ses_coups:
                    suivant = resoudre(etat, ca, cb)
                    fin = termine(suivant)
                    # Un léger amortissement empêche les parties infinies de
                    # faire diverger la valeur quand personne ne prend de risque.
                    ligne.append(float(fin) if fin is not None else 0.98 * valeurs[suivant])
                matrice.append(ligne)

            valeur, politique = valeur_du_jeu_matriciel(matrice, iterations=200 if passe else 60)
            nouvelles[etat] = valeur
            politiques[etat] = list(zip(mes_coups, politique))

        valeurs = nouvelles
        print(f"  passe {passe + 1}/{passes} terminée")

    return politiques


# ---------------------------------------------------------------------------
# Confrontation avec le bot de production
# ---------------------------------------------------------------------------

BASE = "http://localhost:8100/api/partie.php"


def api(action: str, **params):
    url = f"{BASE}?{urllib.parse.urlencode({'action': action, **params})}"
    try:
        with urllib.request.urlopen(url, timeout=20) as reponse:
            return json.loads(reponse.read().decode())
    except urllib.error.HTTPError as erreur:
        return json.loads(erreur.read().decode())


def coup_optimal(politiques, etat, legaux):
    distribution = [(c, p) for c, p in politiques.get(etat, []) if c in legaux]
    if not distribution:
        return random.choice(legaux)

    total = sum(p for _, p in distribution) or 1.0
    seuil, cumul = random.random(), 0.0
    for coup, p in distribution:
        cumul += p / total
        if seuil <= cumul:
            return coup
    return distribution[-1][0]


def confronter(politiques, parties: int, difficulte: str) -> tuple[int, int]:
    """Le joueur parfait (nous) contre le bot de production. → (nos victoires, les siennes)"""
    nous = lui = 0

    for _ in range(parties):
        jeu = api("creer", adversaire="ordinateur", difficulte=difficulte)
        code, jeton = jeu["code"], jeu["jeton"]
        etat = jeu["etat"]

        for _ in range(200):
            if etat["statut"] == "termine":
                break

            cle = (
                min(PLAFOND_ACTIONS, etat["moi"]["points"]),
                min(PLAFOND_ACTIONS, etat["adversaire"]["points"]),
                etat["moi"]["buts"],
                etat["adversaire"]["buts"],
                etat["moi"]["dernierCoup"] == "defendre",
                etat["adversaire"]["dernierCoup"] == "defendre",
            )
            coup = coup_optimal(politiques, cle, tuple(etat["moi"]["coupsAutorises"]))
            reponse = api("jouer", code=code, jeton=jeton, coup=coup)
            if "erreur" in reponse:
                break
            etat = reponse["etat"]

        if etat.get("vainqueur") == etat.get("joueurId"):
            nous += 1
        elif etat.get("vainqueur") is not None:
            lui += 1

    return nous, lui


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--parties", type=int, default=150)
    parseur.add_argument("--difficulte", default="difficile")
    parseur.add_argument(
        "--cache",
        default="",
        help="fichier de politique : réutilisé s'il existe, écrit sinon. "
             "Permet de comparer plusieurs réglages d'evaluerEtat() sans "
             "repayer la résolution à chaque fois.",
    )
    options = parseur.parse_args()

    cache = Path(options.cache) if options.cache else None

    if cache and cache.exists():
        print(f"Politique relue depuis {cache}")
        politiques = {
            tuple(json.loads(cle)): [tuple(x) for x in valeur]
            for cle, valeur in json.loads(cache.read_text()).items()
        }
    else:
        print(f"Résolution du mode classique ({len(tous_les_etats())} états)…")
        politiques = resoudre_le_jeu()
        if cache:
            cache.write_text(json.dumps(
                {json.dumps(list(k)): v for k, v in politiques.items()}
            ))
            print(f"Politique enregistrée dans {cache}")

    print(f"\nConfrontation : joueur parfait contre bot « {options.difficulte} », "
          f"{options.parties} parties…")
    nous, lui = confronter(politiques, options.parties, options.difficulte)

    total = nous + lui
    part = 100 * lui / total if total else 0
    print(f"\n  joueur parfait : {nous}")
    print(f"  bot            : {lui}   ({part:.0f} % des parties décidées)")
    print()
    if part >= 40:
        print("  → le bot tient tête à un joueur parfait. Rien à revoir.")
    elif part >= 25:
        print("  → honorable. La fonction d'évaluation peut encore se resserrer.")
    else:
        print("  → trop faible : revoir evaluerEtat() avant d'aller plus loin.")


if __name__ == "__main__":
    main()
