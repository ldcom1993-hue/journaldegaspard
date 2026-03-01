/**
 * Ajouter un personnage:
 * 1) Ajouter un nouvel objet dans le tableau `characters`.
 * 2) Renseigner tous les champs: name, japaneseName, role, team, description, image, link et order.
 * 3) Recommandé: placer l'image en local (ex: assets/images/olive-et-tom/olivier-atton.jpg)
 *    puis renseigner `image` avec un chemin relatif sans slash initial
 *    (ex: "assets/images/olive-et-tom/olivier-atton.jpg").
 * 4) Le tri se fait automatiquement selon `order`.
 */
const characters = [
  {
    name: "Olivier Atton",
    japaneseName: "Tsubasa Ozora",
    role: "Milieu offensif",
    team: "New Team",
    description: "Prodige du football japonais et meneur créatif de New Team.",
    image: "../../assets/images/olive-et-tom/olivier-atton.png",
    link: "/univers/olive-et-tom/personnages/olivier-atton.html",
    order: 1,
  },
  {
    name: "Thomas Price",
    japaneseName: "Genzo Wakabayashi",
    role: "Gardien",
    team: "New Team",
    description: "Gardien d'élite au sang-froid exceptionnel, pilier défensif de l'équipe.",
    image: "../../assets/images/olive-et-tom/thomas-price.png",
    link: "/univers/olive-et-tom/personnages/thomas-price.html",
    order: 2,
  },
  {
    name: "Ben Becker",
    japaneseName: "Taro Misaki",
    role: "Milieu offensif",
    team: "New Team",
    description: "Partenaire technique d'Olivier, célèbre pour leur duo offensif.",
    image: "../../assets/images/olive-et-tom/ben-becker.png",
    link: "/univers/olive-et-tom/personnages/ben-becker.html",
    order: 3,
  },
  {
    name: "Bruce Harper",
    japaneseName: "Ryo Ishizaki",
    role: "Défenseur",
    team: "New Team",
    description: "Défenseur combatif et courageux, prêt à se sacrifier pour son équipe.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/bruce-harper.html",
    order: 4,
  },
  {
    name: "Patty Gadsby",
    japaneseName: "Sanae Nakazawa",
    role: "Manager",
    team: "New Team",
    description: "Supporter et manager emblématique, soutien moral d'Olivier et de New Team.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/patty-gadsby.html",
    order: 5,
  },
  {
    name: "Mark Landers",
    japaneseName: "Kojiro Hyuga",
    role: "Attaquant",
    team: "Toho",
    description: "Avant-centre puissant et rival historique d'Olivier Atton.",
    image: "../../assets/images/olive-et-tom/mark-landers.png",
    link: "/univers/olive-et-tom/personnages/mark-landers.html",
    order: 6,
  },
  {
    name: "Ed Warner",
    japaneseName: "Ken Wakashimazu",
    role: "Gardien",
    team: "Toho",
    description: "Gardien-acrobate de Toho, polyvalent et spectaculaire.",
    image: "../../assets/images/olive-et-tom/ed-warner.png",
    link: "/univers/olive-et-tom/personnages/ed-warner.html",
    order: 7,
  },
  {
    name: "Julian Ross",
    japaneseName: "Jun Misugi",
    role: "Milieu offensif",
    team: "Musashi",
    description: "Stratège raffiné au grand talent technique, capitaine de Musashi.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/julian-ross.html",
    order: 8,
  },
  {
    name: "Philip Callahan",
    japaneseName: "Hikaru Matsuyama",
    role: "Milieu",
    team: "Furano",
    description: "Joueur endurant et discipliné, leader charismatique de Furano.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/philip-callahan.html",
    order: 9,
  },
  {
    name: "Shun Nitta",
    japaneseName: "Shun Nitta",
    role: "Attaquant",
    team: "Otomo",
    description: "Attaquant rapide spécialisé dans les courses et les frappes explosives.",
    image: "https://via.placeholder.com/300x400?text=Shun+Nitta",
    link: "/univers/olive-et-tom/personnages/shun-nitta.html",
    order: 10,
  },
  {
    name: "Hiroshi Jito",
    japaneseName: "Hiroshi Jito",
    role: "Défenseur",
    team: "Hirado",
    description: "Défenseur central imposant, redoutable dans les duels physiques.",
    image: "https://via.placeholder.com/300x400?text=Hiroshi+Jito",
    link: "/univers/olive-et-tom/personnages/hiroshi-jito.html",
    order: 11,
  },
  {
    name: "Makoto Soda",
    japaneseName: "Makoto Soda",
    role: "Défenseur",
    team: "Tatsunami",
    description: "Arrière agressif connu pour son pressing intense et ses tacles tranchants.",
    image: "https://via.placeholder.com/300x400?text=Makoto+Soda",
    link: "/univers/olive-et-tom/personnages/makoto-soda.html",
    order: 12,
  },
  {
    name: "Hanji Urabe",
    japaneseName: "Hanji Urabe",
    role: "Défenseur",
    team: "New Team",
    description: "Défenseur rugueux passé par Shutetsu puis intégré au collectif de New Team.",
    image: "https://via.placeholder.com/300x400?text=Hanji+Urabe",
    link: "/univers/olive-et-tom/personnages/hanji-urabe.html",
    order: 13,
  },
  {
    name: "Kazuo Tachibana",
    japaneseName: "Kazuo Tachibana",
    role: "Attaquant",
    team: "Hanawa",
    description: "Jumeau acrobatique, spécialiste des combinaisons aériennes avec son frère.",
    image: "https://via.placeholder.com/300x400?text=Kazuo+Tachibana",
    link: "/univers/olive-et-tom/personnages/kazuo-tachibana.html",
    order: 14,
  },
  {
    name: "Masao Tachibana",
    japaneseName: "Masao Tachibana",
    role: "Attaquant",
    team: "Hanawa",
    description: "Jumeau de Kazuo, connu pour les techniques synchronisées spectaculaires.",
    image: "https://via.placeholder.com/300x400?text=Masao+Tachibana",
    link: "/univers/olive-et-tom/personnages/masao-tachibana.html",
    order: 15,
  },
  {
    name: "Roberto Sedinho",
    japaneseName: "Roberto Hongo",
    role: "Coach",
    team: "New Team",
    description: "Mentor brésilien d'Olivier, figure clé de sa progression.",
    image: "https://via.placeholder.com/300x400?text=Roberto+Sedinho",
    link: "/univers/olive-et-tom/personnages/roberto-sedinho.html",
    order: 16,
  },
  {
    name: "Karl Heinz Schneider",
    japaneseName: "Karl Heinz Schneider",
    role: "Attaquant",
    team: "Allemagne",
    description: "Buteur vedette allemand, réputé pour sa puissance de frappe.",
    image: "https://via.placeholder.com/300x400?text=Karl+Heinz+Schneider",
    link: "/univers/olive-et-tom/personnages/karl-heinz-schneider.html",
    order: 17,
  },
  {
    name: "Juan Diaz",
    japaneseName: "Juan Diaz",
    role: "Milieu offensif",
    team: "Argentine",
    description: "Créateur argentin technique, souvent comparé à un maestro du dribble.",
    image: "https://via.placeholder.com/300x400?text=Juan+Diaz",
    link: "/univers/olive-et-tom/personnages/juan-diaz.html",
    order: 18,
  },
  {
    name: "Natureza",
    japaneseName: "Natureza",
    role: "Attaquant",
    team: "Brésil",
    description: "Phénomène offensif brésilien doté d'une technique instinctive.",
    image: "https://via.placeholder.com/300x400?text=Natureza",
    link: "/univers/olive-et-tom/personnages/natureza.html",
    order: 19,
  },
  {
    name: "Rivaul",
    japaneseName: "Rivaul",
    role: "Milieu offensif",
    team: "Brésil",
    description: "Milieu offensif d'exception, modèle technique pour de nombreux joueurs.",
    image: "https://via.placeholder.com/300x400?text=Rivaul",
    link: "/univers/olive-et-tom/personnages/rivaul.html",
    order: 20,
  },
];

const grid = document.querySelector("#characters-grid");
const template = document.querySelector("#character-card-template");

function getInitials(name) {
  const cleaned = (name || "").trim();
  if (!cleaned) {
    return "?";
  }

  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }

  return `${words[0][0] || ""}${words[1][0] || ""}`.toUpperCase();
}

/**
 * Crée un placeholder SVG en data URI pour éviter toute image cassée.
 *
 * Pour remplacer ce placeholder par une vraie image locale:
 * 1) Ajouter le fichier dans le repo, par exemple:
 *    assets/images/olive-et-tom/olivier-atton.jpg
 * 2) Définir `image` dans l'objet personnage avec un chemin relatif
 *    (sans slash initial), par ex:
 *    image: "assets/images/olive-et-tom/olivier-atton.jpg"
 * 3) En cas d'échec de chargement, le fallback placeholder reste automatique.
 */
function makePlaceholder(name) {
  const initials = getInitials(name);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="800" viewBox="0 0 640 800" role="img" aria-label="Portrait indisponible de ${name}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#14213d"/>
          <stop offset="100%" stop-color="#1f3b73"/>
        </linearGradient>
        <linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(255,255,255,0.22)"/>
          <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
        </linearGradient>
      </defs>
      <rect x="24" y="24" width="592" height="752" rx="36" fill="url(#bg)"/>
      <rect x="24" y="24" width="592" height="260" rx="36" fill="url(#gloss)"/>
      <text x="320" y="430" text-anchor="middle" dominant-baseline="middle"
            font-family="Inter, Segoe UI, Roboto, Arial, sans-serif"
            font-size="180" font-weight="800" fill="#f5f7ff" letter-spacing="4">
        ${initials}
      </text>
    </svg>
  `;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function isAbsoluteUrl(value) {
  return /^https?:\/\//i.test(value);
}

if (grid && template) {
  const sortedCharacters = [...characters].sort((a, b) => a.order - b.order);

  sortedCharacters.forEach((character) => {
    const card = template.content.firstElementChild.cloneNode(true);
    const link = card.querySelector(".character-link");
    const image = card.querySelector(".character-image");
    const name = card.querySelector(".character-name");
    const team = card.querySelector(".character-team");
    const description = card.querySelector(".character-description");

    link.href = character.link;

    const fallbackImage = makePlaceholder(character.name);
    const providedImage = (character.image || "").trim();

    // Sécurise l'affichage: aucune icône d'image cassée.
    image.onerror = () => {
      image.onerror = null;
      image.src = fallbackImage;
    };

    if (!providedImage) {
      image.src = fallbackImage;
    } else if (isAbsoluteUrl(providedImage)) {
      image.src = providedImage;
    } else {
      // Chemin local/relatif: on le tente d'abord (préféré), puis fallback auto si introuvable.
      image.src = providedImage;
    }

    image.alt = `Portrait de ${character.name}`;
    name.textContent = character.name;
    team.textContent = character.team;
    description.textContent = character.description;

    grid.appendChild(card);
  });
}
