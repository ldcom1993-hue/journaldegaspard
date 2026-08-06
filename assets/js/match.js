/* ===========================================================================
   Duel "Match" — client
   ---------------------------------------------------------------------------
   Le serveur (api/partie.php) détient toutes les règles. Ce fichier ne fait
   que trois choses :
     1. envoyer l'intention du joueur,
     2. interroger l'état à intervalle régulier,
     3. peindre cet état à l'écran.

   Il ne calcule jamais un score ni la légalité d'un coup — il se contente
   d'obéir au champ `coupsAutorises` renvoyé par le serveur. Toute règle
   ajoutée plus tard (techniques, personnages) se code côté PHP, pas ici.

   Pour ajouter un coup : l'ajouter dans COUPS ci-dessous, dans la constante
   COUPS du PHP, dans resoudreManche(), et poser un bouton [data-coup] dans
   match.html. Le reste suit automatiquement.
   =========================================================================== */

import { makePlaceholder, safeText } from "/assets/js/entites.js";

(() => {
  "use strict";

  const API = "/api/partie.php";
  const CLE_SESSION = "jdg.match.session";
  const DELAI_POLLING = 1500;
  const ROSTER = "/assets/data/duel-roster.json";

  /** Libellés et icônes, alignés sur les couleurs de match.css. */
  const COUPS = {
    construire: { nom: "Construit", icone: "⚽" },
    tirer: { nom: "Tire au but", icone: "💥" },
    defendre: { nom: "Défend", icone: "🧤" }
  };

  /** Les trois postes d'une équipe, dans l'ordre d'affichage du draft. */
  const POSTES = [
    { cle: "tir", nom: "Attaque", detail: "Sa technique s'engage sur un tir." },
    { cle: "construction", nom: "Milieu", detail: "Sa technique s'engage sur une construction." },
    { cle: "defense", nom: "Défense", detail: "Sa technique s'engage sur une défense." }
  ];

  /**
   * Ce que fait chaque effet, pour l'afficher au joueur. La règle elle-même
   * vit dans api/partie.php : ces libellés ne servent qu'à la décrire.
   */
  const EFFETS = {
    frappe: { nom: "Frappe", detail: "Marque même si l'adversaire défend", cout: 2 },
    volee: { nom: "Volée", detail: "Tirer sans aucune action en réserve", cout: 0 },
    "une-deux": { nom: "Une-deux", detail: "Deux actions au lieu d'une", cout: 0 },
    crochet: { nom: "Crochet", detail: "Annule le tir adverse sans défendre", cout: 1 },
    parade: { nom: "Parade", detail: "La défense rapporte deux actions", cout: 0 },
    repli: { nom: "Repli", detail: "Défendre deux manches de suite", cout: 0 }
  };

  // -------------------------------------------------------------------------
  // Références DOM
  // -------------------------------------------------------------------------

  const $ = (selecteur) => document.querySelector(selecteur);

  const ecrans = {
    accueil: $("#ecran-accueil"),
    salon: $("#ecran-salon"),
    selection: $("#ecran-selection"),
    match: $("#ecran-match"),
    fin: $("#ecran-fin")
  };

  const dom = {
    btnCreer: $("#btn-creer"),
    btnRejoindre: $("#btn-rejoindre"),
    champCode: $("#champ-code"),
    accueilErreur: $("#accueil-erreur"),

    codeAffiche: $("#code-affiche"),
    btnCopier: $("#btn-copier"),
    btnQuitterSalon: $("#btn-quitter-salon"),

    nomMoi: $("#score-nom-moi"),
    nomAdversaire: $("#score-nom-adversaire"),
    butsMoi: $("#score-buts-moi"),
    butsAdversaire: $("#score-buts-adversaire"),
    manche: $("#score-manche"),
    objectif: $("#score-objectif"),

    revelationMoi: $("#revelation-moi"),
    revelationAdversaire: $("#revelation-adversaire"),
    jaugeMoi: $("#jauge-moi"),
    jaugeAdversaire: $("#jauge-adversaire"),
    recit: $("#recit"),
    matchErreur: $("#match-erreur"),
    boutonsCoup: Array.from(document.querySelectorAll("[data-coup]")),
    cartouches: $("#cartouches"),

    postes: $("#postes"),
    btnValiderEquipe: $("#btn-valider-equipe"),
    btnQuitterSelection: $("#btn-quitter-selection"),
    selectionErreur: $("#selection-erreur"),
    selectionAttente: $("#selection-attente"),

    finVerdict: $("#fin-verdict"),
    finScore: $("#fin-score"),
    btnRevanche: $("#btn-revanche"),
    finAttente: $("#fin-attente"),
    btnNouveau: $("#btn-nouveau")
  };

  // -------------------------------------------------------------------------
  // État local
  // -------------------------------------------------------------------------

  /** Identité du joueur dans la partie courante : { code, jeton }. */
  let session = null;

  /** Dernier état reçu du serveur. */
  let etat = null;

  /** Coup posé par le joueur, en attente de résolution. */
  let coupEnAttente = null;

  /** Numéro de la dernière manche déjà affichée, pour ne pas rejouer l'anim. */
  let mancheAffichee = 0;

  let minuteur = null;
  let requeteEnCours = false;

  // -------------------------------------------------------------------------
  // Persistance : survivre à un rafraîchissement de page
  // -------------------------------------------------------------------------

  function chargerSession() {
    try {
      const brut = localStorage.getItem(CLE_SESSION);
      return brut ? JSON.parse(brut) : null;
    } catch (erreur) {
      return null;
    }
  }

  function enregistrerSession(valeur) {
    session = valeur;
    try {
      if (valeur) {
        localStorage.setItem(CLE_SESSION, JSON.stringify(valeur));
      } else {
        localStorage.removeItem(CLE_SESSION);
      }
    } catch (erreur) {
      /* Navigation privée : on continue sans persistance. */
    }
  }

  // -------------------------------------------------------------------------
  // Appels API
  // -------------------------------------------------------------------------

  /**
   * Appelle l'API et renvoie le JSON. Lève une Error portant le message
   * renvoyé par le serveur, qui est déjà rédigé pour être lu par un joueur.
   */
  async function appeler(action, parametres = {}) {
    const corps = new URLSearchParams({ action, ...parametres });

    const reponse = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: corps.toString()
    });

    let donnees = null;
    try {
      donnees = await reponse.json();
    } catch (erreur) {
      throw new Error("Réponse illisible du serveur.");
    }

    if (!reponse.ok || donnees.erreur) {
      const echec = new Error(donnees.erreur || `Erreur ${reponse.status}.`);
      echec.statut = reponse.status;
      throw echec;
    }

    return donnees;
  }

  // -------------------------------------------------------------------------
  // Navigation entre écrans
  // -------------------------------------------------------------------------

  function afficherEcran(nom) {
    Object.entries(ecrans).forEach(([cle, element]) => {
      element.hidden = cle !== nom;
    });
  }

  function afficherErreur(element, message) {
    if (!element) {
      return;
    }
    element.textContent = message;
    element.hidden = !message;
  }

  // -------------------------------------------------------------------------
  // Rendu
  // -------------------------------------------------------------------------

  /**
   * Peint la jauge d'actions disponibles sous forme de ballons.
   */
  function peindreJauge(liste, points) {
    liste.textContent = "";

    if (points <= 0) {
      const vide = document.createElement("li");
      vide.className = "jauge-vide";
      vide.textContent = "aucune action";
      liste.appendChild(vide);
      return;
    }

    for (let i = 0; i < points; i += 1) {
      liste.appendChild(document.createElement("li"));
    }
  }

  /**
   * Peint une carte de révélation dans l'un de ses trois états :
   * en attente d'un choix, choix verrouillé mais secret, ou coup révélé.
   */
  function peindreRevelation(carte, { coup, verrouille }) {
    const icone = carte.querySelector(".revelation-icone");
    const nom = carte.querySelector(".revelation-nom");

    if (coup && COUPS[coup]) {
      carte.dataset.etat = "revele";
      carte.dataset.coup = coup;
      icone.textContent = COUPS[coup].icone;
      nom.textContent = COUPS[coup].nom;
      return;
    }

    delete carte.dataset.coup;
    icone.textContent = "";

    if (verrouille) {
      carte.dataset.etat = "verrouille";
      nom.textContent = "Coup verrouillé";
    } else {
      carte.dataset.etat = "attente";
      nom.textContent = "Réfléchit…";
    }
  }

  /**
   * Anime un score qui vient de bouger.
   */
  function signalerBut(element) {
    element.classList.remove("vient-de-marquer");
    // Forcer un reflow pour pouvoir rejouer l'animation.
    void element.offsetWidth;
    element.classList.add("vient-de-marquer");
  }

  /**
   * Remplace les marqueurs {A} / {B} du récit serveur par des noms lisibles
   * du point de vue du joueur courant.
   */
  function formulerRecit(recit, joueurId) {
    const moi = "Vous";
    const lui = "L'adversaire";

    return recit
      .replace(/\{A\}/g, joueurId === 0 ? moi : lui)
      .replace(/\{B\}/g, joueurId === 1 ? moi : lui);
  }

  function peindreMatch(nouvelEtat) {
    const moi = nouvelEtat.moi;
    const adversaire = nouvelEtat.adversaire;
    const derniere = nouvelEtat.derniereManche;

    dom.nomMoi.textContent = "Vous";
    dom.nomAdversaire.textContent = "Adversaire";
    dom.manche.textContent = String(nouvelEtat.manche);
    dom.objectif.textContent = `${nouvelEtat.butsPourGagner} buts pour gagner`;

    // Score, avec un flash quand un but vient de tomber.
    const butsAvant = {
      moi: Number(dom.butsMoi.textContent),
      adversaire: Number(dom.butsAdversaire.textContent)
    };

    dom.butsMoi.textContent = String(moi.buts);
    dom.butsAdversaire.textContent = String(adversaire ? adversaire.buts : 0);

    if (moi.buts > butsAvant.moi) {
      signalerBut(dom.butsMoi);
    }
    if (adversaire && adversaire.buts > butsAvant.adversaire) {
      signalerBut(dom.butsAdversaire);
    }

    peindreJauge(dom.jaugeMoi, moi.points);
    peindreJauge(dom.jaugeAdversaire, adversaire ? adversaire.points : 0);

    // La manche vient d'être résolue : on retourne les deux cartes.
    const manchResolue = derniere && derniere.numero > mancheAffichee;

    if (manchResolue) {
      mancheAffichee = derniere.numero;
      coupEnAttente = null;

      const coupMoi = derniere.coups[nouvelEtat.joueurId];
      const coupAdversaire = derniere.coups[1 - nouvelEtat.joueurId];

      peindreRevelation(dom.revelationMoi, { coup: coupMoi });
      peindreRevelation(dom.revelationAdversaire, { coup: coupAdversaire });
      dom.recit.textContent = formulerRecit(derniere.recit, nouvelEtat.joueurId);
    } else if (moi.aJoue || coupEnAttente) {
      // Le joueur a posé son coup : on masque le sien et on montre si l'autre suit.
      peindreRevelation(dom.revelationMoi, { verrouille: true });
      peindreRevelation(dom.revelationAdversaire, {
        verrouille: Boolean(adversaire && adversaire.aJoue)
      });
      dom.recit.textContent = "Coup verrouillé. En attente de l'adversaire…";
    } else if (adversaire && adversaire.aJoue) {
      peindreRevelation(dom.revelationMoi, { verrouille: false });
      peindreRevelation(dom.revelationAdversaire, { verrouille: true });
      dom.recit.textContent = "L'adversaire a choisi. À vous.";
    }

    // Boutons : le serveur seul décide de ce qui est jouable.
    const autorises = moi.coupsAutorises || [];
    const gele = moi.aJoue || Boolean(coupEnAttente) || nouvelEtat.statut !== "en-cours";

    dom.boutonsCoup.forEach((bouton) => {
      const coup = bouton.dataset.coup;
      bouton.disabled = gele || !autorises.includes(coup);
      bouton.classList.toggle("est-choisi", coupEnAttente === coup);

      // Expliquer pourquoi un coup est indisponible, plutôt que de le griser sec.
      if (!gele && !autorises.includes(coup)) {
        bouton.title =
          coup === "tirer"
            ? "Il vous faut au moins une action construite."
            : "Impossible de défendre deux manches de suite.";
      } else {
        bouton.removeAttribute("title");
      }
    });

    peindreCartouches(nouvelEtat);
  }

  function peindreFin(nouvelEtat) {
    const jaiGagne = nouvelEtat.vainqueur === nouvelEtat.joueurId;

    dom.finVerdict.textContent = jaiGagne ? "🏆" : "😤";
    $("#fin-titre").textContent = jaiGagne ? "Vous avez gagné" : "Vous avez perdu";
    dom.finScore.textContent = `${nouvelEtat.moi.buts} — ${
      nouvelEtat.adversaire ? nouvelEtat.adversaire.buts : 0
    }`;

    const jaiDemande = nouvelEtat.revanche.moi;
    const ilADemande = nouvelEtat.revanche.adversaire;

    dom.btnRevanche.hidden = jaiDemande;
    dom.finAttente.hidden = !jaiDemande;

    if (!jaiDemande && ilADemande) {
      dom.btnRevanche.textContent = "L'adversaire veut sa revanche — accepter";
    } else {
      dom.btnRevanche.textContent = "Demander la revanche";
    }
  }

  /**
   * Point d'entrée unique du rendu : reçoit un état serveur, choisit l'écran
   * et le peint. Tout passe par ici, donc l'affichage ne peut pas diverger.
   */
  // -------------------------------------------------------------------------
  // Composition d'équipe (mode Équipe)
  // -------------------------------------------------------------------------

  let roster = null;
  let choix = {};
  let draftPeint = false;

  async function chargerRoster() {
    if (roster) {
      return roster;
    }

    const reponse = await fetch(ROSTER);

    if (!reponse.ok) {
      throw new Error(`HTTP ${reponse.status}`);
    }

    roster = await reponse.json();

    return roster;
  }

  /**
   * Une carte de personnage pour un poste donné. Le même personnage peut
   * apparaître à plusieurs postes : c'est au joueur d'arbitrer, puisqu'il ne
   * peut en aligner qu'un seul par poste.
   */
  function carteDraft(personnage, poste) {
    const capacite = personnage.familles[poste];
    const effet = EFFETS[capacite.effet] || { nom: capacite.effet, detail: "" };

    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "draft-carte";
    bouton.dataset.poste = poste;
    bouton.dataset.slug = personnage.slug;

    const image = document.createElement("img");
    image.className = "draft-portrait";
    image.loading = "lazy";
    image.alt = "";
    const repli = makePlaceholder(personnage.nom);
    image.addEventListener("error", () => { image.src = repli; }, { once: true });
    image.src = safeText(personnage.image) || repli;

    const corps = document.createElement("span");
    corps.className = "draft-corps";

    const nom = document.createElement("span");
    nom.className = "draft-nom";
    nom.textContent = personnage.nom;

    const technique = document.createElement("span");
    technique.className = "draft-technique";
    technique.textContent = capacite.technique;

    const detail = document.createElement("span");
    detail.className = "draft-effet";
    detail.textContent = effet.cout
      ? `${effet.detail} · ${effet.cout} action${effet.cout > 1 ? "s" : ""}`
      : effet.detail;

    corps.append(nom, technique, detail);
    bouton.append(image, corps);

    bouton.addEventListener("click", () => {
      choix[poste] = choix[poste] === personnage.slug ? null : personnage.slug;
      rafraichirDraft();
    });

    return bouton;
  }

  /** Reflète la sélection courante : cartes actives, doublons, bouton final. */
  function rafraichirDraft() {
    const retenus = POSTES.map((p) => choix[p.cle]).filter(Boolean);

    dom.postes.querySelectorAll(".draft-carte").forEach((carte) => {
      const { poste, slug } = carte.dataset;
      const retenu = choix[poste] === slug;
      // Déjà aligné ailleurs : on le montre pris plutôt que de le masquer,
      // sinon la liste se réorganise sous les doigts du joueur.
      const prisAilleurs = !retenu && retenus.includes(slug);

      carte.classList.toggle("est-retenu", retenu);
      carte.classList.toggle("est-pris", prisAilleurs);
      carte.disabled = prisAilleurs;
      carte.setAttribute("aria-pressed", String(retenu));
    });

    dom.btnValiderEquipe.disabled = retenus.length !== POSTES.length;
  }

  async function peindreSelection(nouvelEtat) {
    if (nouvelEtat.moi.aCompose) {
      dom.postes.hidden = true;
      dom.btnValiderEquipe.hidden = true;
      dom.selectionAttente.hidden = false;
      return;
    }

    if (draftPeint) {
      return;
    }

    draftPeint = true;

    let vivier;

    try {
      vivier = await chargerRoster();
    } catch (erreur) {
      draftPeint = false;
      afficherErreur(dom.selectionErreur, "Impossible de charger les personnages.");
      return;
    }

    dom.postes.textContent = "";

    POSTES.forEach((poste) => {
      const bloc = document.createElement("section");
      bloc.className = "poste";

      const titre = document.createElement("h3");
      titre.className = "poste-titre";
      titre.textContent = poste.nom;

      const detail = document.createElement("p");
      detail.className = "poste-detail";
      detail.textContent = poste.detail;

      const liste = document.createElement("div");
      liste.className = "poste-liste";

      vivier
        .filter((personnage) => personnage.familles[poste.cle])
        .forEach((personnage) => liste.appendChild(carteDraft(personnage, poste.cle)));

      bloc.append(titre, detail, liste);
      dom.postes.appendChild(bloc);
    });

    rafraichirDraft();
  }

  async function validerEquipe() {
    dom.selectionErreur.hidden = true;
    dom.btnValiderEquipe.disabled = true;

    try {
      const donnees = await appeler("composer", {
        code: session.code,
        jeton: session.jeton,
        tir: choix.tir,
        construction: choix.construction,
        defense: choix.defense
      });

      appliquerEtat(donnees.etat);
    } catch (erreur) {
      afficherErreur(dom.selectionErreur, erreur.message);
      dom.btnValiderEquipe.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // Cartouches
  // -------------------------------------------------------------------------

  let cartoucheChoisie = null;

  /**
   * Peint les techniques encore en main. Une cartouche n'est proposée que si
   * le serveur la déclare jouable — `cartouchesAutorisees` est calculé côté
   * PHP, comme `coupsAutorises`.
   */
  function peindreCartouches(nouvelEtat) {
    if (nouvelEtat.mode !== "equipe" || !nouvelEtat.moi.equipe) {
      dom.cartouches.hidden = true;
      return;
    }

    const jouables = new Set(
      Object.values(nouvelEtat.moi.cartouchesAutorisees || {}).flat()
    );

    dom.cartouches.hidden = false;
    dom.cartouches.textContent = "";

    POSTES.forEach((poste) => {
      const carte = nouvelEtat.moi.equipe[poste.cle];

      if (!carte) {
        return;
      }

      const effet = EFFETS[carte.effet] || { nom: carte.effet, detail: "" };
      const epuisee = Boolean(carte.utilisee);
      const disponible = !epuisee && jouables.has(carte.effet) && !nouvelEtat.moi.aJoue;

      const bouton = document.createElement("button");
      bouton.type = "button";
      bouton.className = "cartouche";
      bouton.disabled = !disponible;
      bouton.classList.toggle("est-epuisee", epuisee);
      bouton.classList.toggle("est-armee", cartoucheChoisie === carte.effet);
      bouton.setAttribute("aria-pressed", String(cartoucheChoisie === carte.effet));
      bouton.title = `${carte.nom} — ${carte.technique} : ${effet.detail}`;

      const nom = document.createElement("span");
      nom.className = "cartouche-nom";
      nom.textContent = effet.nom;

      const porteur = document.createElement("span");
      porteur.className = "cartouche-porteur";
      porteur.textContent = epuisee ? "déjà jouée" : carte.nom;

      bouton.append(nom, porteur);

      bouton.addEventListener("click", () => {
        cartoucheChoisie = cartoucheChoisie === carte.effet ? null : carte.effet;
        peindreCartouches(etat);
      });

      dom.cartouches.appendChild(bouton);
    });
  }

  function appliquerEtat(nouvelEtat) {
    const precedent = etat;
    etat = nouvelEtat;

    // Une revanche a été acceptée : on repart d'une feuille blanche.
    if (precedent && precedent.statut === "termine" && nouvelEtat.statut === "en-cours") {
      mancheAffichee = 0;
      coupEnAttente = null;
      dom.butsMoi.textContent = "0";
      dom.butsAdversaire.textContent = "0";
      peindreRevelation(dom.revelationMoi, {});
      peindreRevelation(dom.revelationAdversaire, {});
      dom.recit.textContent = "Nouveau match. Choisissez votre coup.";
    }

    if (nouvelEtat.statut === "attente") {
      dom.codeAffiche.textContent = nouvelEtat.code;
      afficherEcran("salon");
      return;
    }

    if (nouvelEtat.statut === "selection") {
      peindreSelection(nouvelEtat);
      afficherEcran("selection");
      return;
    }

    if (nouvelEtat.statut === "termine") {
      peindreMatch(nouvelEtat);
      peindreFin(nouvelEtat);
      afficherEcran("fin");
      return;
    }

    peindreMatch(nouvelEtat);
    afficherEcran("match");
  }

  // -------------------------------------------------------------------------
  // Polling
  // -------------------------------------------------------------------------

  /**
   * Interroge le serveur. On ne poll pas quand l'onglet est en arrière-plan :
   * inutile de réveiller l'hébergement mutualisé pour rien.
   */
  async function rafraichir() {
    if (!session || requeteEnCours || document.hidden) {
      return;
    }

    requeteEnCours = true;

    try {
      const donnees = await appeler("etat", session);
      appliquerEtat(donnees.etat);
      afficherErreur(dom.matchErreur, "");
    } catch (erreur) {
      if (erreur.statut === 404 || erreur.statut === 403) {
        quitter(erreur.message);
      }
      // Une coupure réseau passagère ne doit pas casser la partie :
      // on retentera au prochain tour de boucle.
    } finally {
      requeteEnCours = false;
    }
  }

  function demarrerPolling() {
    arreterPolling();
    minuteur = setInterval(rafraichir, DELAI_POLLING);
  }

  function arreterPolling() {
    if (minuteur !== null) {
      clearInterval(minuteur);
      minuteur = null;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && session) {
      rafraichir();
    }
  });

  // -------------------------------------------------------------------------
  // Actions du joueur
  // -------------------------------------------------------------------------

  function entrerEnPartie(donnees) {
    enregistrerSession({ code: donnees.code, jeton: donnees.jeton });
    mancheAffichee = 0;
    coupEnAttente = null;
    etat = null;
    appliquerEtat(donnees.etat);
    demarrerPolling();
  }

  function quitter(message = "") {
    arreterPolling();
    enregistrerSession(null);
    etat = null;
    coupEnAttente = null;
    mancheAffichee = 0;

    // Le draft doit repartir vierge : sans ça, une seconde partie réafficherait
    // la sélection précédente, voire l'écran d'attente d'un match abandonné.
    choix = {};
    draftPeint = false;
    cartoucheChoisie = null;
    dom.postes.hidden = false;
    dom.btnValiderEquipe.hidden = false;
    dom.selectionAttente.hidden = true;
    afficherErreur(dom.selectionErreur, "");

    afficherErreur(dom.accueilErreur, message);
    afficherEcran("accueil");
  }

  async function creerPartie() {
    dom.btnCreer.disabled = true;
    afficherErreur(dom.accueilErreur, "");

    const modeChoisi = document.querySelector('input[name="mode"]:checked');

    try {
      entrerEnPartie(await appeler("creer", { mode: modeChoisi ? modeChoisi.value : "classique" }));
    } catch (erreur) {
      afficherErreur(dom.accueilErreur, erreur.message);
    } finally {
      dom.btnCreer.disabled = false;
    }
  }

  async function rejoindrePartie(codeDemande) {
    const code = String(codeDemande || dom.champCode.value)
      .trim()
      .toUpperCase();

    if (code.length !== 4) {
      afficherErreur(dom.accueilErreur, "Un code de match fait quatre caractères.");
      dom.champCode.focus();
      return;
    }

    dom.btnRejoindre.disabled = true;
    afficherErreur(dom.accueilErreur, "");

    try {
      entrerEnPartie(await appeler("rejoindre", { code }));
    } catch (erreur) {
      afficherErreur(dom.accueilErreur, erreur.message);
    } finally {
      dom.btnRejoindre.disabled = false;
    }
  }

  async function jouerCoup(coup) {
    if (!session || coupEnAttente) {
      return;
    }

    // Verrouillage optimiste : le bouton réagit tout de suite, sans attendre
    // l'aller-retour réseau. En cas de refus serveur, on rend la main.
    coupEnAttente = coup;
    if (etat) {
      peindreMatch(etat);
    }

    try {
      const donnees = await appeler("jouer", {
        ...session,
        coup,
        cartouche: cartoucheChoisie || ""
      });
      cartoucheChoisie = null;
      appliquerEtat(donnees.etat);
      afficherErreur(dom.matchErreur, "");
    } catch (erreur) {
      coupEnAttente = null;
      if (erreur.statut === 404 || erreur.statut === 403) {
        quitter(erreur.message);
        return;
      }
      afficherErreur(dom.matchErreur, erreur.message);
      rafraichir();
    }
  }

  async function demanderRevanche() {
    if (!session) {
      return;
    }

    dom.btnRevanche.disabled = true;

    try {
      const donnees = await appeler("rejouer", session);
      appliquerEtat(donnees.etat);
    } catch (erreur) {
      afficherErreur(dom.matchErreur, erreur.message);
    } finally {
      dom.btnRevanche.disabled = false;
    }
  }

  async function copierLien() {
    if (!etat) {
      return;
    }

    const lien = `${location.origin}${location.pathname}?code=${etat.code}`;
    const original = dom.btnCopier.textContent;

    try {
      await navigator.clipboard.writeText(lien);
      dom.btnCopier.textContent = "Lien copié";
    } catch (erreur) {
      // clipboard indisponible (http, vieux navigateur) : on montre le lien.
      dom.btnCopier.textContent = lien;
    }

    setTimeout(() => {
      dom.btnCopier.textContent = original;
    }, 2500);
  }

  // -------------------------------------------------------------------------
  // Branchements
  // -------------------------------------------------------------------------

  dom.btnCreer.addEventListener("click", creerPartie);
  dom.btnRejoindre.addEventListener("click", () => rejoindrePartie());
  dom.btnCopier.addEventListener("click", copierLien);
  dom.btnQuitterSalon.addEventListener("click", () => quitter());
  dom.btnValiderEquipe.addEventListener("click", validerEquipe);
  dom.btnQuitterSelection.addEventListener("click", () => quitter());
  dom.btnNouveau.addEventListener("click", () => quitter());
  dom.btnRevanche.addEventListener("click", demanderRevanche);

  dom.champCode.addEventListener("keydown", (evenement) => {
    if (evenement.key === "Enter") {
      rejoindrePartie();
    }
  });

  dom.champCode.addEventListener("input", () => {
    dom.champCode.value = dom.champCode.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  });

  dom.boutonsCoup.forEach((bouton) => {
    bouton.addEventListener("click", () => jouerCoup(bouton.dataset.coup));
  });

  // -------------------------------------------------------------------------
  // Démarrage
  // -------------------------------------------------------------------------

  async function demarrer() {
    const codeUrl = new URLSearchParams(location.search).get("code");
    const sauvegarde = chargerSession();

    // Reprise d'une partie en cours après un rafraîchissement.
    if (sauvegarde && (!codeUrl || codeUrl.toUpperCase() === sauvegarde.code)) {
      session = sauvegarde;
      try {
        const donnees = await appeler("etat", session);
        appliquerEtat(donnees.etat);
        demarrerPolling();
        return;
      } catch (erreur) {
        enregistrerSession(null);
        session = null;
      }
    }

    afficherEcran("accueil");

    // Lien d'invitation : on pré-remplit et on tente de rejoindre directement.
    if (codeUrl) {
      dom.champCode.value = codeUrl.toUpperCase().slice(0, 4);
      rejoindrePartie(dom.champCode.value);
    }
  }

  demarrer();
})();
