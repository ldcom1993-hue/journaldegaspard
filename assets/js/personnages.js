/**
 * Ajouter un personnage:
 * 1) Ajouter un nouvel objet dans le tableau `characters`.
 * 2) Renseigner name, team, description, image, link et order.
 * 3) Le tri se fait automatiquement selon `order`.
 */
const characters = [
  {
    name: "Olivier Atton",
    team: "New Team",
    description: "Attaquant et passionné de football, capitaine au talent exceptionnel.",
    image: "/assets/images/olive-et-tom/olivier-atton.svg",
    link: "/univers/olive-et-tom/personnages/olivier-atton.html",
    order: 1,
  },
  {
    name: "Thomas Price",
    team: "New Team",
    description: "Gardien courageux et agile, prêt à tout pour protéger ses cages.",
    image: "/assets/images/olive-et-tom/thomas-price.svg",
    link: "/univers/olive-et-tom/personnages/thomas-price.html",
    order: 2,
  },
  {
    name: "Ben Becker",
    team: "Muppet FC",
    description: "Défenseur physique et déterminé, spécialiste des duels intenses.",
    image: "/assets/images/olive-et-tom/ben-becker.svg",
    link: "/univers/olive-et-tom/personnages/ben-becker.html",
    order: 3,
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
