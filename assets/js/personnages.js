const grid = document.querySelector("#characters-grid");
const template = document.querySelector("#character-card-template");
const positionFilter = document.querySelector("#filter-position");
const countryFilter = document.querySelector("#filter-country");
const searchInput = document.querySelector("#filter-search");
const resultsCount = document.querySelector("#results-count");
const emptyState = document.querySelector("#empty-state");
const resetFiltersButton = document.querySelector("#reset-filters");
const sortSelect = document.querySelector("#sort-select");

let charactersData = [];
let renderedCharacters = [];

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = "1";
        entry.target.style.transform = "translateY(0)";
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.15 }
);

const JAPANESE_NAME_ALLOWED_PREFIXES = [
  "Ryo",
  "Genzo",
  "Tsubasa",
  "Shingo",
  "Kojiro",
  "Jun",
  "Hikaru",
  "Taro",
  "Ken",
  "Sanae"
];

const POSITION_MAP = {
  goalkeeper: "Gardien",
  gk: "Gardien",
  gardien: "Gardien",
  defender: "Défenseur",
  df: "Défenseur",
  defenseur: "Défenseur",
  défenseur: "Défenseur",
  back: "Défenseur",
  midfielder: "Milieu",
  mf: "Milieu",
  milieu: "Milieu",
  forward: "Attaquant",
  fw: "Attaquant",
  striker: "Attaquant",
  attaquant: "Attaquant",
  coach: "Coach",
  manager: "Manager"
};

const NATIONALITY_MAP = {
  japan: "Japan",
  japanese: "Japan",
  japon: "Japan",
  brazil: "Brazil",
  brazilian: "Brazil",
  bresil: "Brazil",
  brésil: "Brazil",
  germany: "Germany",
  german: "Germany",
  allemagne: "Germany",
  france: "France",
  french: "France",
  italy: "Italy",
  italian: "Italy",
  spain: "Spain",
  spanish: "Spain",
  argentina: "Argentina",
  argentine: "Argentina",
  netherlands: "Netherlands",
  dutch: "Netherlands",
  "pays-bas": "Netherlands",
  sweden: "Sweden",
  swedish: "Sweden"
};

const FLAGS = {
  Japan: "🇯🇵",
  Brazil: "🇧🇷",
  Germany: "🇩🇪",
  France: "🇫🇷",
  Italy: "🇮🇹",
  Spain: "🇪🇸",
  Argentina: "🇦🇷",
  Netherlands: "🇳🇱",
  Sweden: "🇸🇪"
};

function toComparable(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function isSlugLike(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return false;
  }

  return trimmed.includes("-") || /^[a-z0-9]+$/.test(trimmed);
}

function formatSlugLikeValue(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }

  if (!isSlugLike(raw)) {
    return raw;
  }

  const beautified = raw
    .replace(/[-_]+/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1).toLowerCase())
    .join(" ")
    .trim();

  return /[A-ZÀ-ÖØ-Þ]/.test(beautified) ? beautified : "";
}

function normalizePosition(position) {
  const key = toComparable(position);
  return POSITION_MAP[key] || "Autre";
}

function normalizeNationality(nationality) {
  const key = toComparable(nationality);
  return NATIONALITY_MAP[key] || "";
}

function getInitials(name) {
  return (
    String(name || "?")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((chunk) => chunk[0].toUpperCase())
      .join("") || "?"
  );
}

function makePlaceholder(name) {
  const initials = getInitials(name);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640" role="img" aria-label="Portrait indisponible de ${name}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#16233f"/>
          <stop offset="100%" stop-color="#345da8"/>
        </linearGradient>
      </defs>
      <rect x="14" y="14" width="612" height="612" rx="72" fill="url(#bg)"/>
      <text x="320" y="332" text-anchor="middle" dominant-baseline="middle"
            font-family="Inter, Segoe UI, Roboto, Arial, sans-serif"
            font-size="168" font-weight="800" fill="#f5f7ff" letter-spacing="4">
        ${initials}
      </text>
    </svg>
  `;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function shouldShowJapaneseName(character) {
  return JAPANESE_NAME_ALLOWED_PREFIXES.some((prefix) => character.name.startsWith(prefix));
}

function normalizeCharacter(character) {
  const name = formatSlugLikeValue(character.name);
  const japaneseName = formatSlugLikeValue(character.japaneseName);
  const teams = Array.isArray(character.teams)
    ? character.teams.map(formatSlugLikeValue).filter(Boolean)
    : [];
  const description = String(character.description || "").trim();
  const normalizedPosition = normalizePosition(character.position);
  const normalizedNationality = normalizeNationality(character.nationality);

  const searchableText = toComparable(
    [
      name,
      japaneseName,
      normalizedPosition,
      normalizedNationality,
      teams.join(" "),
      description
    ].join(" ")
  );

  return {
    slug: String(character.slug || "").trim(),
    name,
    japaneseName,
    image: String(character.image || "").trim(),
    teams,
    description,
    normalizedPosition,
    normalizedNationality,
    flag: FLAGS[normalizedNationality] || "",
    searchableText,
    popularity: Number.isFinite(Number(character.popularity))
      ? Number(character.popularity)
      : Number.isFinite(Number(character.popularityRank))
      ? -Number(character.popularityRank)
      : 0,
    element: null
  };
}

function setText(element, value) {
  if (!element) {
    return;
  }

  if (value) {
    element.textContent = value;
    element.hidden = false;
  } else {
    element.textContent = "";
    element.hidden = true;
  }
}

function createCard(character, index) {
  const card = template.content.firstElementChild.cloneNode(true);
  const link = card.querySelector(".character-link");
  const image = card.querySelector(".character-image");
  const flag = card.querySelector(".character-flag");
  const name = card.querySelector(".character-name");
  const japaneseName = card.querySelector(".character-japanese-name");
  const position = card.querySelector(".character-position");
  const team = card.querySelector(".character-team");
  const description = card.querySelector(".character-description");

  link.href = `/univers/olive-et-tom/personnage.html?slug=${encodeURIComponent(character.slug)}`;

  const fallbackImage = makePlaceholder(character.name || "Personnage");
  image.onerror = () => {
    image.onerror = null;
    image.src = fallbackImage;
  };
  image.src = character.image || fallbackImage;
  image.alt = character.name ? `Portrait de ${character.name}` : "Portrait de personnage";
  image.loading = "lazy";

  if (character.flag) {
    flag.textContent = character.flag;
    flag.hidden = false;
    flag.setAttribute("aria-label", `Nationalité: ${character.normalizedNationality}`);
    flag.title = character.normalizedNationality;
  }

  setText(name, character.name);
  setText(
    japaneseName,
    shouldShowJapaneseName(character) && character.japaneseName ? character.japaneseName : ""
  );
  setText(position, character.normalizedPosition);
  setText(team, character.teams.length ? character.teams.join(" · ") : "");
  setText(description, character.description);

  card.style.setProperty("--card-index", String(index));

  return card;
}

function populateFilterOptions(characters) {
  const positions = [...new Set(characters.map((character) => character.normalizedPosition))].sort(
    (a, b) => a.localeCompare(b, "fr", { sensitivity: "base" })
  );

  const countries = [
    ...new Set(characters.map((character) => character.normalizedNationality).filter(Boolean))
  ].sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));

  positionFilter.insertAdjacentHTML(
    "beforeend",
    positions.map((position) => `<option value="${position}">${position}</option>`).join("")
  );

  countryFilter.insertAdjacentHTML(
    "beforeend",
    countries.map((country) => `<option value="${country}">${country}</option>`).join("")
  );
}

function debounce(callback, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}

function applyFilters(characters = renderedCharacters) {
  const selectedPosition = positionFilter.value;
  const selectedCountry = countryFilter.value;
  const query = toComparable(searchInput.value);

  let visibleCount = 0;

  characters.forEach((character) => {
    const matchesPosition = !selectedPosition || character.normalizedPosition === selectedPosition;
    const matchesCountry = !selectedCountry || character.normalizedNationality === selectedCountry;
    const matchesSearch = !query || character.searchableText.includes(query);

    const isVisible = matchesPosition && matchesCountry && matchesSearch;
    character.element.classList.toggle("is-hidden", !isVisible);

    if (isVisible) {
      visibleCount += 1;
    }
  });

  resultsCount.textContent = `${visibleCount} joueur${visibleCount > 1 ? "s" : ""} affiché${
    visibleCount > 1 ? "s" : ""
  }`;

  emptyState.hidden = visibleCount !== 0;
}

function resetFilters() {
  positionFilter.value = "";
  countryFilter.value = "";
  searchInput.value = "";
  applyFilters();
  searchInput.focus();
}

function renderCharacters(data) {
  renderedCharacters = data;
  grid.textContent = "";

  const fragment = document.createDocumentFragment();

  data.forEach((character, index) => {
    const card = createCard(character, index);
    character.element = card;
    observer.observe(card);
    fragment.appendChild(card);
  });

  grid.appendChild(fragment);

  applyFilters(data);
}

function sortCharacters(mode) {
  console.log("Sorting mode:", mode);

  const sortedCharacters = [...charactersData].sort((a, b) => {
    if (mode === "az") {
      return a.name.localeCompare(b.name, "fr", { sensitivity: "base" });
    }

    if (mode === "za") {
      return b.name.localeCompare(a.name, "fr", { sensitivity: "base" });
    }

    const aPopularity = Number.isFinite(Number(a.popularity)) ? Number(a.popularity) : 0;
    const bPopularity = Number.isFinite(Number(b.popularity)) ? Number(b.popularity) : 0;
    return bPopularity - aPopularity;
  });

  renderCharacters(sortedCharacters);
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

    const data = await response.json();
    charactersData = Array.isArray(data)
      ? data
          .map((character) => normalizeCharacter(character))
          .filter((character) => character.slug && character.name)
      : [];

    populateFilterOptions(charactersData);

    const debouncedApplyFilters = debounce(() => applyFilters(), 150);
    positionFilter.addEventListener("change", () => applyFilters());
    countryFilter.addEventListener("change", () => applyFilters());
    searchInput.addEventListener("input", debouncedApplyFilters);
    resetFiltersButton.addEventListener("click", () => resetFilters());
    if (sortSelect) {
      sortSelect.value = "popularity";
      sortSelect.addEventListener("change", (event) => {
        sortCharacters(event.target.value);
      });
    }

    sortCharacters(sortSelect?.value || "popularity");
  } catch (error) {
    console.error("Impossible de charger les personnages:", error);
  }
}

initCharacters();
