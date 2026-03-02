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
    \1\"/assets/images/olive-et-tom/olivier-atton.png\",
    link: "/univers/olive-et-tom/personnages/olivier-atton.html",
    description: "",
    image: "https://upload.wikimedia.org/wikipedia/en/5/54/Captain_Tsubasa_vol_1.png",
    link: "/univers/olive-et-tom/personnages/patty-gadsby.html",
    description: "",
    image: "../../assets/images/olive-et-tom/hikaru-matsuyama.png",
    link: "/univers/olive-et-tom/personnages/philip-callahan.html",
    description: "",
    image: "https://via.placeholder.com/300x400?text=Masao+Tachibana",
    link: "/univers/olive-et-tom/personnages/masao-tachibana.html",
    description: "",
    \1\"/assets/images/olive-et-tom/karl-heinz-schneider.png\",
    link: "/univers/olive-et-tom/personnages/karl-heinz-schneider.html",
    image: "/assets/images/olive-et-tom/karl-heinz-schneider.png"
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
