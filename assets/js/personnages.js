const grid = document.querySelector("#characters-grid");
const template = document.querySelector("#character-card-template");

function getInitials(name) {
  return String(name || "?")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((chunk) => chunk[0].toUpperCase())
    .join("") || "?";
}

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

function stripHtml(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function toDisplayCharacter(character) {
  const name = stripHtml(character.name);

  return {
    name,
    team: Array.isArray(character.teams) ? character.teams.join(", ") : "",
    description: character.description || "",
    image: character.image || "",
    link: `/univers/olive-et-tom/personnages/${character.slug}.html`
  };
}

function renderCharacters(characters) {
  const sortedCharacters = [...characters].sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

  sortedCharacters.forEach((character) => {
    const card = template.content.firstElementChild.cloneNode(true);
    const link = card.querySelector(".character-link");
    const image = card.querySelector(".character-image");
    const name = card.querySelector(".character-name");
    const team = card.querySelector(".character-team");
    const description = card.querySelector(".character-description");

    link.href = character.link;

    const fallbackImage = makePlaceholder(character.name);
    const providedImage = String(character.image || "").trim();

    image.onerror = () => {
      image.onerror = null;
      image.src = fallbackImage;
    };

    image.src = providedImage || fallbackImage;
    image.alt = `Portrait de ${character.name}`;
    name.textContent = character.name;
    team.textContent = character.team;
    description.textContent = character.description;

    grid.appendChild(card);
  });
}

async function initCharacters() {
  if (!grid || !template) {
    return;
  }

  try {
    const response = await fetch("/assets/data/personnages.json");

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const rawCharacters = await response.json();
    const displayCharacters = Array.isArray(rawCharacters) ? rawCharacters.map(toDisplayCharacter) : [];

    renderCharacters(displayCharacters);
  } catch (error) {
    console.error("Impossible de charger les personnages:", error);
  }
}

initCharacters();
