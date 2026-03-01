/**
 * Ajouter un personnage:
 * 1) Ajouter un nouvel objet dans le tableau `characters`.
 * 2) Renseigner tous les champs: name, japaneseName, role, team, description, image, link et order.
 * 3) Utiliser une image sûre (Wikimedia `https://upload.wikimedia.org/`) ou le placeholder si indisponible.
 * 4) Le tri se fait automatiquement selon `order`.
 */
const characters = [
  {
    name: "Olivier Atton",
    japaneseName: "Tsubasa Ozora",
    role: "Milieu offensif",
    team: "New Team",
    description: "Prodige du football japonais et meneur créatif de New Team.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/olivier-atton.html",
    order: 1,
  },
  {
    name: "Thomas Price",
    japaneseName: "Genzo Wakabayashi",
    role: "Gardien",
    team: "New Team",
    description: "Gardien d'élite au sang-froid exceptionnel, pilier défensif de l'équipe.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/thomas-price.html",
    order: 2,
  },
  {
    name: "Ben Becker",
    japaneseName: "Taro Misaki",
    role: "Milieu offensif",
    team: "New Team",
    description: "Partenaire technique d'Olivier, célèbre pour leur duo offensif.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
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
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/mark-landers.html",
    order: 6,
  },
  {
    name: "Ed Warner",
    japaneseName: "Ken Wakashimazu",
    role: "Gardien",
    team: "Toho",
    description: "Gardien-acrobate de Toho, polyvalent et spectaculaire.",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
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
    image.src = character.image;
    image.alt = `Portrait de ${character.name}`;
    name.textContent = character.name;
    team.textContent = character.team;
    description.textContent = character.description;

    grid.appendChild(card);
  });
}
